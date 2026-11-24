#!/usr/bin/env python3
"""Run the entry script with mocked HTTP; no order before readiness."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('04-socket-real-order.sh')

class ReadinessTest(unittest.TestCase):
    def invoke(self, profile, locked=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'reports/run-state'
            state.mkdir(parents=True)
            (state/'02-trading-baseline.env').write_text('RUN_ID=unit-02-trading-platform\n')
            (root/'state.json').write_text(json.dumps({'experiment_profile':profile}))
            (root/'lab.json').write_text(json.dumps({'mode':'SFC','transition':'READY','owner':'sfc','clients':{'trader_manual':{'health':{'status':'ONLINE'},'software':{'queue_locked':locked,'queue_mode':'DEQUE_CV','network_engine':'KERNEL_SOCKET'}}}}))
            mocks=root/'mocks.sh'
            mocks.write_text('''curl(){
case " $* " in
  *" -X POST "*) touch post-attempted; return 77;;
  *"/api/transport-lab"*) cat lab.json;;
  *"/api/state"*) cat state.json;;
  *) return 99;;
esac
}
''')
            script=root/'entry.sh'
            script.write_text(SCRIPT.read_text().replace('cd /qyt-fll','cd '+shlex.quote(tmp),1))
            result=subprocess.run(['bash',str(script)],env=dict(os.environ,BASH_ENV=str(mocks)),text=True,capture_output=True,timeout=5)
            return result,(root/'post-attempted').exists()

    def test_software_stops_before_order(self):
        result,posted=self.invoke('SOFTWARE',False)
        self.assertFalse(posted)
        self.assertEqual(result.returncode,2)
        self.assertIn('尚未下单',result.stderr)
        self.assertIn('03-four-path-lab-ready.sh',result.stderr)

    def test_unlocked_client_stops_before_order(self):
        result,posted=self.invoke('TRANSPORT',False)
        self.assertFalse(posted)
        self.assertEqual(result.returncode,2)

    def test_ready_reaches_submission_and_reports_http_failure(self):
        result,posted=self.invoke('TRANSPORT')
        self.assertTrue(posted)
        self.assertEqual(result.returncode,77)
        self.assertIn('提交订单并等待成交',result.stderr)

if __name__=='__main__':
    unittest.main()
