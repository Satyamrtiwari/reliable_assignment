"""Automated unit tests for Task 2 (AI copywriter, Pillow flyer layouts, & compliant social distribution)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP_DIR = tempfile.TemporaryDirectory()
os.environ["DB_PATH"] = str(Path(_TMP_DIR.name) / "test_task2.db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image  # noqa: E402
from shared import database  # noqa: E402
from task2_ai_flyer import ai_copywriter, flyer_generator, social_distributor  # noqa: E402


class TestTask2FlyerGeneration(unittest.TestCase):
    def setUp(self) -> None:
        if database.DB_PATH.exists():
            database.DB_PATH.unlink()
        database.init_db()
        database.seed_sample_data()

    def test_fallback_copy_includes_accurate_item_prices(self) -> None:
        items = database.get_in_stock_items()
        with patch.object(ai_copywriter, "GROQ_API_KEY", ""):
            copy = ai_copywriter.generate_flyer_copy(items, campaign_theme="Monsoon Paper Deals")
        self.assertEqual(copy["ai_source"], "FALLBACK")
        self.assertEqual(copy["headline"], "Stock Up. Stay Ready.")
        self.assertIn("245.00", copy["social_caption"])

    def test_groq_copy_parses_json_response(self) -> None:
        items = database.get_in_stock_items()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "headline": "Fresh Paper Stock In",
                                "subheadline": "Wholesale rates ready for immediate dispatch",
                                "offer_badge": "WEEKLY SPECIAL",
                                "cta_text": "Call now for bulk pricing",
                                "social_caption": "Reliable Paper Mart weekly deals!",
                            }
                        )
                    }
                }
            ]
        }
        with patch.object(ai_copywriter, "GROQ_API_KEY", "gsk_test_key"), patch(
            "task2_ai_flyer.ai_copywriter.requests.post", return_value=mock_resp
        ):
            copy = ai_copywriter.generate_flyer_copy(items, campaign_theme="Weekly Restock")
        self.assertIn("GROQ", copy["ai_source"])
        self.assertEqual(copy["headline"], "Fresh Paper Stock In")
        self.assertEqual(copy["offer_badge"], "WEEKLY SPECIAL")

    def test_generate_flyer_creates_1080x1350_png_and_logs(self) -> None:
        items = database.get_in_stock_items()
        tmp_flyers = Path(_TMP_DIR.name) / "flyers"
        with patch.object(flyer_generator, "GENERATED_FLYERS_DIR", tmp_flyers), patch.object(
            ai_copywriter, "GROQ_API_KEY", ""
        ):
            res = flyer_generator.generate_flyer_image(
                stock_items=items,
                style="Fresh",
                layout="Card List",
                campaign_theme="Eco Paper Week",
            )
        img_path = Path(res["image_path"])
        self.assertTrue(img_path.exists())
        with Image.open(img_path) as im:
            self.assertEqual(im.size, (1080, 1350))

        logged = database.get_recent_flyers(limit=5)
        self.assertEqual(len(logged), 1)
        self.assertEqual(logged[0]["style"], "Fresh")
        self.assertEqual(logged[0]["layout"], "Card List")
        self.assertEqual(logged[0]["item_count"], len(items))

    def test_auto_rotate_cycles_all_three_layouts(self) -> None:
        items = database.get_in_stock_items()
        tmp_flyers = Path(_TMP_DIR.name) / "flyers_rot"
        seen_layouts = []
        with patch.object(flyer_generator, "GENERATED_FLYERS_DIR", tmp_flyers), patch.object(
            ai_copywriter, "GROQ_API_KEY", ""
        ):
            for _ in range(3):
                res = flyer_generator.generate_flyer_image(
                    stock_items=items,
                    style="Minimal",
                    layout="Auto-Rotate",
                )
                seen_layouts.append(res["layout"])
                self.assertTrue(Path(res["image_path"]).exists())
        self.assertEqual(seen_layouts, ["Card List", "2-Column Grid", "Featured Spotlight"])

    def test_generate_flyer_requires_in_stock_items(self) -> None:
        with self.assertRaises(ValueError):
            flyer_generator.generate_flyer_image(stock_items=[])

    def test_facebook_page_dry_run_and_live_mock(self) -> None:
        sample_img = Path(_TMP_DIR.name) / "sample_fb.png"
        Image.new("RGB", (100, 100), "#ffffff").save(sample_img)

        dry = social_distributor.post_to_facebook_page(sample_img, "Test caption", dry_run=True)
        self.assertTrue(dry["ok"])
        self.assertEqual(dry["status"], "SIMULATED")

        mock_resp = MagicMock(ok=True, status_code=200)
        mock_resp.json.return_value = {"id": "111", "post_id": "147701_999"}
        with patch.object(social_distributor, "FB_PAGE_ID", "147701"), patch.object(
            social_distributor, "FB_PAGE_ACCESS_TOKEN", "tok_live"
        ), patch("task2_ai_flyer.social_distributor.requests.post", return_value=mock_resp):
            live = social_distributor.post_to_facebook_page(sample_img, "Live caption", dry_run=False)
        self.assertTrue(live["ok"])
        self.assertEqual(live["status"], "SUCCESS")
        self.assertEqual(live["external_id"], "147701_999")
        self.assertIn("https://www.facebook.com/147701_999", live["post_url"])

    def test_whatsapp_opt_in_filtering_and_live_mock(self) -> None:
        sample_img = Path(_TMP_DIR.name) / "sample_wa.png"
        Image.new("RGB", (100, 100), "#ffffff").save(sample_img)

        c1 = database.add_whatsapp_contact("Opted In", "+91 98200 11111", opted_in=True)
        c2 = database.add_whatsapp_contact("Opted Out", "+91 98200 22222", opted_in=False)
        self.assertEqual(c1["phone_e164"], "919820011111")
        self.assertEqual(c2["opted_in"], 0)

        media_resp = MagicMock(ok=True, status_code=200)
        media_resp.json.return_value = {"id": "media_123"}
        msg_resp = MagicMock(ok=True, status_code=200)
        msg_resp.json.return_value = {"messages": [{"id": "wamid.abc"}]}

        with patch.object(social_distributor, "WHATSAPP_PHONE_NUMBER_ID", "12345"), patch.object(
            social_distributor, "WHATSAPP_ACCESS_TOKEN", "wa_tok"
        ), patch(
            "task2_ai_flyer.social_distributor.requests.post",
            side_effect=[media_resp, msg_resp],
        ) as mock_post:
            res = social_distributor.send_whatsapp_flyer_broadcast(
                sample_img, "Weekly WA flyer", dry_run=False
            )
        # Only c1 (opted-in) should be sent to (1 media call + 1 message call = 2 calls)
        self.assertTrue(res["ok"])
        self.assertEqual(res["sent"], 1)
        self.assertEqual(mock_post.call_count, 2)

    def test_group_share_pack_creates_wa_me_link_and_files(self) -> None:
        sample_img = Path(_TMP_DIR.name) / "sample_pack.png"
        Image.new("RGB", (100, 100), "#ffffff").save(sample_img)
        pack_root = Path(_TMP_DIR.name) / "share_packs"

        with patch.object(social_distributor, "SHARE_PACKS_DIR", pack_root):
            pack = social_distributor.create_group_share_pack(
                sample_img,
                "Reliable Paper Mart Deal!",
                fb_post_url="https://www.facebook.com/147701_999",
            )
        self.assertTrue(pack["wa_share_url"].startswith("https://wa.me/?text="))
        self.assertTrue((Path(pack["pack_dir"]) / "whatsapp_group_caption.txt").exists())
        self.assertTrue((Path(pack["pack_dir"]) / "facebook_group_caption.txt").exists())
        self.assertTrue((Path(pack["pack_dir"]) / "share_manifest.json").exists())
        self.assertTrue(len(database.get_recent_social_logs()) >= 1)


if __name__ == "__main__":
    unittest.main()
