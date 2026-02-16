import json
import stat
import tempfile
import unittest
from pathlib import Path

from llm_router.headless_import import import_codex_headless_auth


class HeadlessImportTests(unittest.TestCase):
    def test_import_codex_headless_auth(self):
        root = Path(tempfile.mkdtemp())
        source = root / "auth.json"
        source.write_text(
            json.dumps(
                {
                    "auth_mode": "oauth",
                    "tokens": {
                        "access_token": "access-token",
                        "refresh_token": "refresh-token",
                        "id_token": "id-token",
                        "account_id": "acc-1",
                    },
                }
            ),
            encoding="utf-8",
        )

        dest = root / "auths"
        out = import_codex_headless_auth(source, dest)

        self.assertTrue(out.exists())
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["type"], "codex")
        self.assertEqual(payload["access_token"], "access-token")
        self.assertEqual(payload["refresh_token"], "refresh-token")

        mode = stat.S_IMODE(out.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_import_rejects_missing_tokens(self):
        root = Path(tempfile.mkdtemp())
        source = root / "auth.json"
        source.write_text(json.dumps({"tokens": {}}), encoding="utf-8")

        with self.assertRaises(ValueError):
            import_codex_headless_auth(source, root / "auths")


if __name__ == "__main__":
    unittest.main()
