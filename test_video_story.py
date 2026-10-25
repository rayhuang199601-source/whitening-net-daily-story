"""Focused checks for afternoon video selection and URL safety."""
import importlib.util
import random
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# Load the pure selection logic without replacing cloud modules for other tests.
requests_stub = types.ModuleType("requests")
story_stub = types.ModuleType("story")
story_stub.TZ = None
workflow_stub = types.ModuleType("workflow")
for name in ("TOKEN_STATE", "gh_file", "gh_write", "graph", "notify", "public_video_url", "publish_story"):
    setattr(workflow_stub, name, "state/meta-token.json" if name == "TOKEN_STATE" else lambda *a, **kw: None)
spec = importlib.util.spec_from_file_location("video_story_selection_test", Path(__file__).with_name("video_story.py"))
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"requests": requests_stub, "story": story_stub, "workflow": workflow_stub}):
    spec.loader.exec_module(module)


class VideoStoryTests(unittest.TestCase):
    def setUp(self):
        self.videos = [{"id": str(i)} for i in range(1, 5)]

    def test_unused_videos_come_first(self):
        result = module.ordered_candidates(self.videos, {"used_ids": ["1", "2"], "last_id": "2"}, random.Random(3))
        self.assertEqual({v["id"] for v in result[:2]}, {"3", "4"})

    def test_fallback_after_ineligible_unused(self):
        result = module.ordered_candidates(self.videos, {"used_ids": ["1", "2"], "last_id": "2"}, random.Random(3))
        self.assertEqual({v["id"] for v in result[2:]}, {"1", "2"})
        self.assertEqual(result[-1]["id"], "2")

    def test_creator_collaborations_precede_self_owned_videos(self):
        videos = [{"id": "1", "source_kind": "own"},
            {"id": "2", "source_kind": "collaboration"},
            {"id": "3", "source_kind": "collaboration"}]
        result = module.ordered_candidates(videos, {"used_ids": ["2"]}, random.Random(3))
        self.assertEqual([v["id"] for v in result], ["3", "1", "2"])

    def test_collaboration_list_skips_media_without_reusable_video(self):
        page = {"instagram_business_account": {"id": "123", "username": "wntw_shida"}}
        media = {"data": [
            {"id": "1", "media_type": "VIDEO", "media_product_type": "REELS",
                "media_url": "https://scontent.cdninstagram.com/1.mp4"},
            {"id": "2", "media_type": "VIDEO", "media_product_type": "REELS"},
            {"id": "3", "media_type": "IMAGE", "media_product_type": "FEED",
                "media_url": "https://scontent.cdninstagram.com/3.jpg"}]}
        with patch.object(module, "facebook_get", side_effect=[page, media]) as get:
            result = module.list_collaborative_reels("test-token")
        self.assertEqual([item["id"] for item in result], ["1"])
        self.assertEqual(result[0]["source_kind"], "collaboration")
        self.assertEqual(get.call_count, 2)

    def test_only_instagram_cdn_urls(self):
        self.assertTrue(module.allowed_video_url("https://scontent.cdninstagram.com/abc.mp4"))
        self.assertTrue(module.allowed_video_url("https://scontent.xx.fbcdn.net/abc.mp4"))
        self.assertFalse(module.allowed_video_url("https://fbcdn.net.evil.example/abc.mp4"))
        self.assertFalse(module.allowed_video_url("http://scontent.xx.fbcdn.net/abc.mp4"))

    def test_rotation_resets_after_cycle(self):
        rotation = module.update_rotation({"used_ids": ["1", "2"], "last_id": "2"}, "1", ["1", "2"], "2026-10-20")
        self.assertEqual(rotation, {"used_ids": ["1"], "last_id": "1", "last_date": "2026-10-20"})


if __name__ == "__main__":
    unittest.main()
