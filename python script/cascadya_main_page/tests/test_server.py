from __future__ import annotations

import unittest

from portal_hub.config import Settings
from portal_hub.server import create_app


class PortalServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            app_name="Portal Test",
            environment_label="TEST",
            app_host="127.0.0.1",
            app_port=9999,
            public_base_url="http://127.0.0.1:9999",
            session_secret="test-secret",
            session_cookie_name="portal_test",
            secure_cookies=False,
            same_site="Lax",
            session_ttl_seconds=3600,
            oidc_enabled=False,
            oidc_issuer_url=None,
            oidc_discovery_url=None,
            oidc_client_id="cascadya-portal-web",
            oidc_client_secret=None,
            oidc_internal_base_url=None,
            oidc_verify_tls=True,
            oidc_ca_cert_path=None,
            oidc_scopes=("openid", "profile", "email"),
            required_tags=("portal-access",),
            enable_dev_login=True,
            default_next_path="/",
            control_panel_url="https://control-panel.cascadya.internal",
            features_url="https://features.cascadya.internal",
            grafana_url="https://grafana.cascadya.internal",
            wazuh_url="https://wazuh.cascadya.internal",
            mimir_url="https://grafana.cascadya.internal/dashboards",
            keycloak_admin_url="https://auth.cascadya.internal/admin/",
            docs_url=None,
        )
        self.app = create_app(self.settings)
        self.app.testing = True
        self.client = self.app.test_client()

    def _login(self, *tags: str) -> None:
        with self.client.session_transaction() as client_session:
            client_session["user"] = {
                "sub": "test-user",
                "username": "operator",
                "display_name": "Operator",
                "email": "operator@cascadya.internal",
                "roles": list(tags),
                "groups": [],
                "tags": list(tags),
                "auth_source": "dev",
                "id_token": None,
            }

    def test_home_redirects_to_login_without_session(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 303)
        self.assertIn("/auth/login?next=%2F", response.headers["Location"])

    def test_monitoring_page_shows_only_accessible_cards(self) -> None:
        self._login("portal-access", "monitoring-user")
        response = self.client.get("/monitoring")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Grafana", body)
        self.assertIn("Mimir", body)
        self.assertIn("Grafana-backed", body)
        self.assertIn("https://grafana.cascadya.internal/dashboards", body)
        self.assertNotIn("Wazuh", body)

    def test_forbidden_page_when_required_portal_tag_is_missing(self) -> None:
        self._login("monitoring-user")
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 403)
        self.assertIn("restricted to users carrying one of the access tags", body)


if __name__ == "__main__":
    unittest.main()
