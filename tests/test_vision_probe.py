import json, sys, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "atlas-rust-desktop" / "src-tauri" / "resources" / "atlas"))
import vision_probe as vp


def serve(status, body):
    seen = []
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(status); self.end_headers(); self.wfile.write(json.dumps(body).encode())
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


class VisionProbeTests(unittest.TestCase):
    def test_parse(self):
        self.assertIs(vp.parse_vision({"modalities": {"vision": True}}), True)
        self.assertIs(vp.parse_vision({"modalities": {"vision": False}}), False)
        self.assertIsNone(vp.parse_vision({}))
        self.assertIsNone(vp.parse_vision([]))

    def test_probe_asks_the_model_through_llama_swap(self):
        srv, seen = serve(200, {"modalities": {"vision": True}})
        try:
            self.assertIs(vp.probe_vision("127.0.0.1", srv.server_port, "my model", timeout=5), True)
        finally:
            srv.shutdown()
        self.assertEqual(seen, ["/upstream/my%20model/props"])

    def test_probe_unknown_on_error_status_or_dead_server(self):
        srv, _ = serve(500, {})
        try:
            self.assertIsNone(vp.probe_vision("127.0.0.1", srv.server_port, "m", timeout=5))
        finally:
            srv.shutdown()
        self.assertIsNone(vp.probe_vision("127.0.0.1", 1, "m", timeout=2))


if __name__ == "__main__":
    unittest.main()
