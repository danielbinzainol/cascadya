from __future__ import annotations

import unittest

from portal_hub.auth import build_identity_from_claims, extract_role_names, safe_next_path


class AuthHelpersTests(unittest.TestCase):
    def test_safe_next_path_rejects_external_redirects(self) -> None:
        self.assertEqual(safe_next_path("https://example.com/evil"), "/")
        self.assertEqual(safe_next_path("//example.com/evil"), "/")
        self.assertEqual(safe_next_path("/monitoring?tab=latency"), "/monitoring?tab=latency")

    def test_extract_role_names_from_keycloak_shapes(self) -> None:
        claims = {
            "roles": ["portal-access"],
            "realm_access": {"roles": ["monitoring-user"]},
            "resource_access": {
                "grafana-monitoring": {"roles": ["grafana-user"]},
                "cascadya-portal-web": {"roles": ["portal-admin"]},
            },
        }
        roles = extract_role_names(claims, client_id="cascadya-portal-web")
        self.assertEqual(
            roles,
            ("grafana-user", "monitoring-user", "portal-access", "portal-admin"),
        )

    def test_build_identity_collects_group_tags(self) -> None:
        identity = build_identity_from_claims(
            {
                "sub": "123",
                "preferred_username": "daniel",
                "name": "Daniel Zainol",
                "groups": ["/platform/portal-admins"],
                "realm_access": {"roles": ["portal-access"]},
            },
            client_id="cascadya-portal-web",
            auth_source="oidc",
        )
        self.assertIn("portal-access", identity["tags"])
        self.assertIn("portal-admins", identity["tags"])
        self.assertEqual(identity["display_name"], "Daniel Zainol")


if __name__ == "__main__":
    unittest.main()
