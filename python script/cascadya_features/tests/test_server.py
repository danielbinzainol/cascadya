import os
import unittest

from cascadya_features.server import create_app


class ServerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_api_key = os.environ.get("TEST_PROVIDER_API_KEY")
        os.environ["TEST_PROVIDER_API_KEY"] = "secret-for-tests"
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        if self.previous_api_key is None:
            os.environ.pop("TEST_PROVIDER_API_KEY", None)
        else:
            os.environ["TEST_PROVIDER_API_KEY"] = self.previous_api_key

    def test_healthz_returns_ok(self) -> None:
        response = self.client.get("/api/healthz")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("TEST_PROVIDER_API_KEY", payload["status"]["configured_api_key_names"])

    def test_evaluate_endpoint_returns_result(self) -> None:
        response = self.client.post("/api/evaluate", json={"spec": "Objectif: tester l'endpoint."})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("result", payload)

    def test_index_serves_new_review_ui(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Review multi-agents", body)
        self.assertIn("Syntheses par modele", body)
        response.close()

    def test_keys_js_endpoint_returns_javascript(self) -> None:
        response = self.client.get("/keys.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.content_type)
        response.close()


if __name__ == "__main__":
    unittest.main()
