from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "src/main.rs").read_text(encoding="utf-8")
MIGRATION = (ROOT / "migrations/0001_initial.sql").read_text(encoding="utf-8")
NODE = (ROOT.parents[1] / "atlas-rust-desktop/src-tauri/src/atlas_node.rs").read_text(encoding="utf-8")

class ControlPlaneContractTests(unittest.TestCase):
    def test_desktop_registration_routes_match(self):
        for route in ("/v1/nodes/challenge", "/v1/nodes/register", "/v1/nodes/heartbeat"):
            self.assertIn(route, SERVER)
            self.assertIn(route, NODE)

    def test_signed_node_workload_routes_match(self):
        for route in ("/v1/workloads/claim", "/v1/workloads/complete"):
            self.assertIn(route, SERVER)
            self.assertIn(route, NODE)

    def test_signed_request_replay_protection(self):
        self.assertIn("timestamp outside allowed clock skew", SERVER)
        self.assertIn("request_replays", SERVER)
        self.assertIn("sha256(raw_body)", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_workload_is_digest_pinned_and_scheduler_signed(self):
        self.assertIn("@sha256:", SERVER)
        self.assertIn("scheduler_sign", SERVER)
        self.assertIn("trusted_scheduler_key_hex", NODE)

    def test_owner_consent_and_node_freshness_are_required(self):
        self.assertIn("enabled AND remote_workloads_allowed", SERVER)
        self.assertIn("last_seen >", SERVER)
        self.assertIn("allow_remote_workloads", NODE)

    def test_receipt_is_not_automatically_billable(self):
        self.assertIn("independently_verified BOOLEAN NOT NULL DEFAULT FALSE", MIGRATION)
        self.assertIn("billable_units BIGINT NOT NULL DEFAULT 0", MIGRATION)
        self.assertIn("FALSE,0", SERVER)

    def test_network_inference_consent_is_heartbeat_reported(self):
        self.assertIn("network_inference_allowed", NODE)
        self.assertIn("network_inference_allowed", SERVER)

    def test_private_service_binds_to_loopback_by_default(self):
        self.assertIn('"127.0.0.1:8181"', SERVER)
        self.assertIn('127.0.0.1:8181:8181', (ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    def test_customer_billing_and_payments_are_not_falsely_claimed(self):
        readme=(ROOT / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("no customer auth/api key", readme)
        self.assertIn("payment", readme)
        self.assertNotIn('route("/v1/payments"', SERVER)

if __name__ == "__main__":
    unittest.main(verbosity=2)
