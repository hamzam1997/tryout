import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as flask_app


class TestSpaRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        dist = Path(self.tmp.name)
        (dist / "index.html").write_text("<html>app</html>")
        self.patch = patch.object(flask_app, "FRONTEND_DIST", dist)
        self.patch.start()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_page_urls_serve_the_app(self):
        for path in ("/ideas", "/attempts/42", "/bottlenecks"):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, path)
            self.assertIn(b"<html>app</html>", resp.data)

    def test_unknown_api_path_is_json_404(self):
        resp = self.client.get("/api/nope")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json(), {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
