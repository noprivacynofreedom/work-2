"""Bot Logs data: states, timeout detection, lead split, archive and category."""
import tempfile, unittest
from pathlib import Path
import atlas_observability as ops
import hw_proxy

class BotRunsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); ops.DB_PATH = Path(self.tmp.name) / 'test.sqlite3'
        a = ops.register({'name': 'w'}); self.aid, self.tok = a['agent_id'], a['token']
    def tearDown(self): self.tmp.cleanup()

    def _task(self, conv, bot, goal="write a python calculator"):
        return ops.submit_task({'type': 'swarm_' + conv, 'conversation_id': conv, 'bot_id': bot, 'payload': {'goal': goal, 'task': 'part'}})

    def test_timeout_and_lead(self):
        self._task('swA-1', '10x: SDE'); self._task('swA-lead', 'Swarm Lead')
        ops.claim_task(self.aid, self.tok, 60, ['swarm_swA-1'])
        ops.finish_task(self.aid, self.tok, ops.task_snapshot()['tasks'][-1]['task_id'],
                        {'status': 'failed', 'error': 'Cannot reach llama-swap at http://127.0.0.1:8080: timed out'})
        run = ops.bot_runs()['runs'][0]
        self.assertEqual(run['run_id'], 'swA')
        self.assertEqual(run['lead']['bot'], 'Swarm Lead')
        self.assertEqual(run['chats'][0]['state'], 'timeout')
        self.assertEqual(run['lead']['state'], 'queued')
        self.assertEqual(run['state'], 'queued')
        self.assertFalse(run['archived'])

    def test_done_run_is_archived_with_category(self):
        t = self._task('swB-1', 'Coder')
        ops.claim_task(self.aid, self.tok, 60, ['swarm_swB-1'])
        ops.finish_task(self.aid, self.tok, t['task_id'], {'status': 'completed', 'result': 'ok'})
        run = ops.bot_runs()['runs'][0]
        self.assertEqual((run['state'], run['archived'], run['category']), ('done', True, 'code'))

    def test_stalled_when_lease_expired(self):
        t = self._task('swC-1', 'Coder')
        ops.claim_task(self.aid, self.tok, 60, ['swarm_swC-1'])
        with ops._db() as c: c.execute("UPDATE tasks SET lease_until=1 WHERE task_id=?", (t['task_id'],))
        self.assertEqual(ops.bot_runs()['runs'][0]['state'], 'stalled')

    def test_proxy_serves_json_and_injects_once(self):
        self._task('swD-1', 'Coder')
        status, ctype, body = hw_proxy.atlas_route('/__atlas/bot-logs.json?limit=5')
        self.assertEqual((status, ctype), (200, 'application/json'))
        self.assertIn(b'swD', body)
        self.assertEqual(hw_proxy.inject(hw_proxy.inject(b'<html><body></body></html>')).count(b'bot-logs.js'), 1)

if __name__ == '__main__': unittest.main()
