"""Gmail API OAuth2 authentication and email sending module."""

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from shared.config import CREDENTIALS_FILE, GMAIL_SCOPES, REPLY_TO_EMAIL, TOKEN_FILE


def get_gmail_service() -> Any:
    """Authenticate via OAuth2 and return an authorized Gmail API service client."""
    creds: Optional[Credentials] = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE}. Download OAuth2 Desktop credentials "
                    "from Google Cloud Console and place them at credentials.json."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def send_email(
    service: Any,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    unsubscribe_url: Optional[str] = None,
) -> str:
    """Build a MIME email with List-Unsubscribe headers and send via Gmail API."""
    message = MIMEMultipart("alternative")
    message["To"] = to_email
    message["Subject"] = subject
    if REPLY_TO_EMAIL:
        message["Reply-To"] = REPLY_TO_EMAIL

    # RFC 8058 / Gmail bulk-sender compliance headers
    if unsubscribe_url:
        message["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    raw_bytes = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw_bytes})
        .execute()
    )
    return str(result.get("id", ""))
