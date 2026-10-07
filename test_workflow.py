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

    def test_initial_token_is_stored_only_as_ciphertext(self):
        writes = []
        with patch.dict(os.environ, {"META_IG_ACCESS_TOKEN": "initial-secret"}), \
             patch.object(workflow, "gh_file", return_value=None), \
             patch.object(workflow, "gh_write", side_effect=lambda path, data, message: writes.append((path, data))):
            workflow.refresh_meta_token()
        self.assertEqual(writes[0][0], workflow.TOKEN_STATE)
        self.assertNotIn(b"initial-secret", writes[0][1])

    def test_old_token_refreshes_and_remains_encrypted(self):
        old_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
        with patch.dict(os.environ, {"META_IG_ACCESS_TOKEN": "initial-secret"}):
            old_ciphertext = workflow.token_cipher().encrypt(b"current-secret").decode()
            saved = {"content": base64.b64encode(json.dumps({
                "ciphertext": old_ciphertext, "refreshed_at": old_time}).encode()).decode()}
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


if __name__ == "__main__":
    unittest.main()
