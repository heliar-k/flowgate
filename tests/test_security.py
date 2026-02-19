import os
import tempfile
import unittest
from pathlib import Path

from flowgate.security import check_secret_file_permissions

import pytest


@pytest.mark.unit
class SecurityTests(unittest.TestCase):
    def test_reports_insecure_secret_permissions(self):
        root = Path(tempfile.mkdtemp())
        secret = root / "token.json"
        secret.write_text("token")
        os.chmod(secret, 0o644)

        issues = check_secret_file_permissions([secret])
        self.assertEqual(len(issues), 1)

        os.chmod(secret, 0o600)
        issues = check_secret_file_permissions([secret])
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
