from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CloudflareMiddlewareTests(unittest.TestCase):
    def test_public_mode_has_no_basic_auth_gate(self):
        source = (ROOT / "functions" / "_middleware.js").read_text(encoding="utf-8")
        self.assertNotIn("APP_USERNAME", source)
        self.assertNotIn("APP_PASSWORD", source)
        self.assertNotIn("WWW-Authenticate", source)
        self.assertNotIn("Authentication required", source)

    def test_same_origin_write_guard_remains(self):
        source = (ROOT / "functions" / "_middleware.js").read_text(encoding="utf-8")
        self.assertIn('request.headers.get("Origin")', source)
        self.assertIn('request.headers.get("Sec-Fetch-Site")', source)
        self.assertIn("Cross-site requests are not allowed", source)
        self.assertIn("return next()", source)


if __name__ == "__main__":
    unittest.main()
