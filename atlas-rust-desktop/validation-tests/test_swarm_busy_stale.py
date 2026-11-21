"""Night dev must not wait forever on /swarm rows that a crashed run left 'queued' (2026-11-18 on the PC)."""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src-tauri" / "resources" / "atlas"))
import atlas_observability as OPS  # noqa: E402
import headless_dev as HD  # noqa: E402


class SwarmBusy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = mock.patch.object(OPS, "DB_PATH", Path(self.tmp.name) / "obs.sqlite3")
        self.db.start()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def add(self, status, age):
        t = time.time() - age
        with OPS.LOCK, OPS._db() as c:
            c.execute("INSERT INTO tasks(task_id,created_at,updated_at,status,priority,task_type,payload) "
                      "VALUES(?,?,?,?,0,'swarm_x-1','{}')", (f"t{age}{status}", t, t, status))

    def test_fresh_queued_row_is_busy(self):
        self.add("queued", 60)
        self.assertTrue(HD._swarm_busy())

    def test_stale_rows_are_ignored(self):
        self.add("queued", 6 * 24 * 3600)
        self.add("claimed", 3 * 3600)
        self.assertFalse(HD._swarm_busy())

    def test_done_row_is_not_busy(self):
        self.add("completed", 60)
        self.assertFalse(HD._swarm_busy())


class PlainPath(unittest.TestCase):
    """The installed app can run from \\\\?\\D:\\... and git clone read that as a host name (2026-11-18)."""

    def test_long_path_prefix_is_dropped(self):
        self.assertEqual(str(HD.plain_path("\\\\?\\D:\\projects\\atlas-chat")), "D:\\projects\\atlas-chat")
        self.assertEqual(str(HD.plain_path("\\\\?\\UNC\\pc\\share\\repo")), "\\\\pc\\share\\repo")
        self.assertEqual(str(HD.plain_path("D:\\repo")), "D:\\repo")


if __name__ == "__main__":
    unittest.main()
