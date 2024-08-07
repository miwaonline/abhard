import unittest
from unittest.mock import patch
from abhard import app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True

    def test_status_endpoint(self):
        response = self.app.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("rro_status", data)
        self.assertIn("scaner_status", data)
        self.assertIn("requests_served", data)

    @patch('requests.post')
    def test_rro_doc_endpoint(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"result": "success"}
        response = self.app.post(
            "/api/rro/doc/1/", json={"key": "value"}
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("result", data)
        self.assertNotIn("success", data)

    def tearDown(self):
        for thread in app.scaner_threads.values():
            thread.running = False
        for thread in app.tcpsocket_threads.values():
            thread.stop()
            thread.join()
        return super().tearDown()


if __name__ == "__main__":
    unittest.main()
