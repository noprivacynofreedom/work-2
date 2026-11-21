import no_real_keys  # noqa: F401  (must run before cloud_llm is imported)
"""/swarm lanes: bots on different machines run at the same time; a dead peer falls back to this PC."""
import os, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "atlas"
sys.path.insert(0, str(APP))
import atlas_observability as OPS  # noqa: E402
import compute_peers  # noqa: E402
import swarm_run  # noqa: E402

PM, SDE, CTO = "10x: Product Manager", "10x: SDE", "10x: CTO"   # aliases: tasks, coder, mentor


def fake_route(peer_aliases):
    def route(model):
        if model in peer_aliases:
            return "10.0.0.9", 8080, {"name": "Laptop", "models": list(peer_aliases)}
        return None, None, None
    return route


def wait_done(convs, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if all(OPS.swarm_log(c)["done"] for c in convs):
            return True
        time.sleep(0.05)
    return False


def text_of(conv):
    return " ".join(l["message"] for l in OPS.swarm_log(conv)["lines"])


class Lanes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old = OPS.DB_PATH
        OPS.DB_PATH = Path(tempfile.mkdtemp(prefix="atlas-lanes-")) / "obs.sqlite3"

    @classmethod
    def tearDownClass(cls):
        OPS.DB_PATH = cls._old

    def start(self, agents, llm):
        run = swarm_run.start("goal", [{"agent": a, "task": "t"} for a in agents], call_llm=llm)
        return [s["conversation_id"] for s in run["steps"]]

    def test_bots_on_two_machines_run_at_the_same_time(self):
        gate = threading.Barrier(2, timeout=5)  # both calls must be in flight together, or the barrier breaks

        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            gate.wait()
            return "ANSWER"
        with mock.patch.object(compute_peers, "route", fake_route({"tasks"})):
            convs = self.start([PM, SDE], llm)
            self.assertTrue(wait_done(convs))
        for c in convs:
            self.assertIn("Done. This is what I came up with", text_of(c))
        self.assertIn("runs on Laptop", text_of(convs[0]))
        self.assertNotIn("runs on", text_of(convs[1]))

    def test_dead_peer_falls_back_to_this_pc(self):
        seen = []

        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            seen.append((model, local_only))
            if model == "tasks" and not local_only:
                raise RuntimeError("Cannot reach llama-swap at http://10.0.0.9:8080")
            return "PC-ANSWER"
        with mock.patch.object(compute_peers, "route", fake_route({"tasks"})):
            convs = self.start([PM], llm)
            self.assertTrue(wait_done(convs))
        t = text_of(convs[0])
        self.assertIn("Laptop did not answer", t)
        self.assertIn("use this PC instead", t)
        self.assertIn("Done. This is what I came up with", t)
        self.assertEqual(seen, [("tasks", False), ("tasks", True)])

    def test_pc_failure_is_not_retried_and_is_reported(self):
        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            raise RuntimeError("model is offline")
        with mock.patch.object(compute_peers, "route", fake_route(set())):
            convs = self.start([SDE], llm)
            self.assertTrue(wait_done(convs))
        self.assertIn("Something went wrong", text_of(convs[0]))

    def test_pc_lane_groups_bots_by_model_alias(self):
        order = []

        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            order.append(model)
            return "ok"
        with mock.patch.object(compute_peers, "route", fake_route(set())):
            convs = self.start([SDE, CTO, SDE.replace("SDE", "QA Engineer")], llm)
            self.assertTrue(wait_done(convs))
        self.assertEqual(order, ["coder", "coder", "mentor"])  # no coder -> mentor -> coder reload

    def test_bots_of_one_alias_share_the_loaded_model_at_the_same_time(self):
        gate = threading.Barrier(3, timeout=5)  # all three coder bots must be in flight together

        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            gate.wait()
            return "ok"
        with mock.patch.object(compute_peers, "route", fake_route(set())):
            convs = self.start([SDE, "10x: QA Engineer", "10x: Senior Engineer"], llm)
            self.assertTrue(wait_done(convs))
        for c in convs:
            self.assertIn("Done.", text_of(c))

    def test_one_slot_keeps_the_old_one_at_a_time_lane(self):
        busy, peak, lock = [0], [0], threading.Lock()

        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            with lock:
                busy[0] += 1
                peak[0] = max(peak[0], busy[0])
            time.sleep(0.05)
            with lock:
                busy[0] -= 1
            return "ok"
        with mock.patch.object(compute_peers, "route", fake_route(set())), \
                mock.patch.dict(os.environ, {"ATLAS_SWARM_SLOTS": "1"}):
            convs = self.start([SDE, "10x: QA Engineer", "10x: Senior Engineer"], llm)
            self.assertTrue(wait_done(convs))
        self.assertEqual(peak[0], 1)

    def test_broken_routing_settings_do_not_stop_the_swarm(self):
        def llm(prompt, temperature=0, max_tokens=0, model=None, local_only=False):
            return "ok"
        with mock.patch.object(compute_peers, "route", side_effect=ValueError("bad settings")):
            convs = self.start([SDE], llm)
            self.assertTrue(wait_done(convs))
        self.assertIn("Done.", text_of(convs[0]))


class Placement(unittest.TestCase):
    """swarm_run._place with fake peers. Real two-machine runs are NOT tested here (no second PC)."""

    def place(self, agents, peer):
        steps = [{"agent": a, "task": "t" * (n + 1) * 100} for n, a in enumerate(agents)]
        route = (lambda m: ("10.0.0.9", 8080, peer) if m in peer["models"] else (None, None, None))
        with mock.patch.object(compute_peers, "route", route):
            lanes = swarm_run._place(steps)
        return {m: [s["agent"] for s in ss] for m, ss in lanes.items()}, steps

    def test_peer_without_share_gets_every_bot_of_its_alias(self):
        lanes, _ = self.place([SDE, "10x: QA Engineer"], {"name": "Laptop", "models": ["coder"], "share": False, "speed": 0.1})
        self.assertEqual(sorted(lanes["Laptop"]), sorted([SDE, "10x: QA Engineer"]))

    def test_shared_alias_heavy_bot_stays_on_the_faster_pc_and_light_bots_spill_to_the_peer(self):
        agents = [SDE, "10x: QA Engineer", "10x: Senior Engineer", "10x: DevOps Engineer"]  # all coder, task sizes grow
        lanes, steps = self.place(agents, {"name": "Laptop", "models": ["coder"], "share": True, "speed": 0.5})
        self.assertEqual(lanes[""][0], "10x: DevOps Engineer")  # the heaviest bot goes first, to this PC
        self.assertTrue(lanes.get("Laptop"))                   # the PC is busy, so a lighter bot goes to the peer
        self.assertTrue(all(s["_local"] for s in steps if s["agent"] in lanes[""]))  # PC bots skip the peer route

    def test_slow_shared_peer_gets_nothing(self):
        lanes, _ = self.place([SDE, "10x: QA Engineer"], {"name": "Laptop", "models": ["coder"], "share": True, "speed": 0.05})
        self.assertNotIn("Laptop", lanes)

    def test_bad_speed_in_settings_falls_back_to_half(self):
        with mock.patch.object(compute_peers, "_read_settings", return_value={"compute_peers": [
                {"name": "Laptop", "url": "http://10.0.0.9:8080", "models": ["coder"], "share": True, "speed": "fast"}]}):
            peer = compute_peers.load_peers()[0][0]
        self.assertEqual((peer["share"], peer["speed"]), (True, 0.5))



if __name__ == "__main__":
    unittest.main()
