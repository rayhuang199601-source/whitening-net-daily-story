"""權杖續期不可把明文寫進公開儲存庫。"""
import base64
import datetime as dt
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = Mock()

import workflow


class TokenRefreshTest(unittest.TestCase):
    def setUp(self):
        workflow._meta_token = None

    def tearDown(self):
        workflow._meta_token = None

    def test_bootstrap_exchanges_code_and_stores_only_ciphertext(self):
        writes = []
        short = Mock(ok=True)
        short.json.return_value = {"access_token": "short-secret", "user_id": "2468013579",
                                   "permissions": "instagram_business_basic,instagram_business_content_publish"}
        profile = Mock(ok=True)
        profile.json.return_value = {"username": "wntw_shida"}
        long = Mock(ok=True)
        long.json.return_value = {"access_token": "long-secret", "expires_in": 60 * 86400}
        with patch.dict(os.environ, {"META_IG_APP_SECRET": "app-secret", "META_IG_AUTH_CODE": "one-time-code",
                                  "META_IG_USER_ID": "17841475612815491"}), \
             patch.object(workflow, "gh_file", return_value=None), \
             patch.object(workflow, "gh_write", side_effect=lambda path, data, message: writes.append((path, data))), \
             patch.object(workflow.requests, "post", return_value=short), \
             patch.object(workflow.requests, "get", side_effect=[profile, long]):
            workflow.bootstrap_meta_token()
        self.assertEqual(writes[0][0], workflow.TOKEN_STATE)
        self.assertNotIn(b"long-secret", writes[0][1])
        self.assertNotIn(b"one-time-code", writes[0][1])
        self.assertEqual(json.loads(writes[0][1])["user_id"], "2468013579")

    def test_bootstrap_rejects_another_instagram_account(self):
        short = Mock(ok=True)
        short.json.return_value = {"access_token": "short-secret", "user_id": "2468013579"}
        profile = Mock(ok=True)
        profile.json.return_value = {"username": "someone_else"}
        with patch.dict(os.environ, {"META_IG_APP_SECRET": "app-secret", "META_IG_AUTH_CODE": "one-time-code"}), \
             patch.object(workflow, "gh_file", return_value=None), \
             patch.object(workflow, "gh_write") as write, \
             patch.object(workflow.requests, "post", return_value=short), \
             patch.object(workflow.requests, "get", return_value=profile):
            with self.assertRaisesRegex(RuntimeError, "不是 @wntw_shida"):
                workflow.bootstrap_meta_token()
        write.assert_not_called()

    def test_old_token_refreshes_and_remains_encrypted(self):
        old_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
        with patch.dict(os.environ, {"META_IG_APP_SECRET": "app-secret"}):
            old_ciphertext = workflow.token_cipher().encrypt(b"current-secret").decode()
            saved = {"content": base64.b64encode(json.dumps({
                "ciphertext": old_ciphertext, "refreshed_at": old_time,
                "user_id": "2468013579", "username": "wntw_shida"}).encode()).decode()}
            response = Mock(ok=True)
            response.json.return_value = {"access_token": "next-secret", "expires_in": 60 * 86400}
            writes = []
            with patch.object(workflow, "gh_file", return_value=saved), \
                 patch.object(workflow, "gh_write", side_effect=lambda path, data, message: writes.append(data)), \
                 patch.object(workflow.requests, "get", return_value=response) as get:
                workflow.refresh_meta_token()
            self.assertEqual(get.call_args.args[0], "https://graph.instagram.com/refresh_access_token")
            self.assertNotIn(b"next-secret", writes[0])
            record = json.loads(writes[0])
            self.assertEqual(workflow.token_cipher().decrypt(record["ciphertext"].encode()), b"next-secret")
            self.assertEqual(record["user_id"], "2468013579")


if __name__ == "__main__":
    unittest.main()
