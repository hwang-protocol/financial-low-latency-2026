#!/usr/bin/env python3
"""Exercise restore state, lost replies and capture setup without lab hosts."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
HELPER=ROOT/'assets/06-arista-time/order-dscp-control.sh'

class ControlTest(unittest.TestCase):
    def run_startup(self, **flags):
        with tempfile.TemporaryDirectory() as tmp:
            script=r'''
set -Eeuo pipefail
RAW="$1"; PARENT_RUN_ID=unit-platform
source "$2"
bash(){
  printf '%s\n' "$2" >>"$RAW/calls"
  command python3 - "$2" <<'PY'
import json, os, sys
path = sys.argv[1] == 'attest'
receipt = {'launch_verified':True, 'verified':path and os.getenv('BAD_PATH') != '1',
           'pid':456 if path and os.getenv('CHANGED_PID') == '1' else 123}
print(json.dumps({'mode':'DPDK' if os.getenv('BAD_MODE') == '1' else 'SFC',
                  'transition':'READY', 'owner':'sfc', 'data_ip_present':True,
                  'hardware_receipts':{'socket':receipt, 'onload':receipt}}))
PY
}
python3(){
  if [[ "$1" = "$QOS_TOOL" ]]; then
    local port=0
    if test -f "$RAW/connected" || test "${CONNECTED:-0}" = 1; then port=40000; fi
    printf '{"ok":true,"dscp":0,"pid":123,"local_port":%s}\n' "$port"
  else command python3 "$@"; fi
}
qos_connect(){ printf 'connect\n' >>"$RAW/calls"; touch "$RAW/connected"; }
qos_check_platform
qos_preflight >"$RAW/preflight.txt"
qos_verify_path
'''
            result=subprocess.run(['bash','-c',script,'test',tmp,str(HELPER)],text=True,
                capture_output=True,env={'PATH':'/usr/bin:/bin',**flags},timeout=10)
            return result, (Path(tmp)/'calls').read_text().splitlines()

    def test_fresh_client_connects_before_attesting(self):
        result,calls=self.run_startup()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls,['status','connect','attest'])
        self.assertIn('[路径检查通过]',result.stdout)

    def test_existing_connection_is_attested_without_new_orders(self):
        result,calls=self.run_startup(CONNECTED='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls,['status','attest'])

    def test_onload_follows_same_startup_order(self):
        result,calls=self.run_startup(FLLE_QOS_TRANSPORT='OPENONLOAD')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls,['status','connect','attest'])
        self.assertIn('OPENONLOAD',result.stdout)

    def test_unready_platform_stops_before_warmup(self):
        result,calls=self.run_startup(BAD_MODE='1')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,['status'])
        self.assertIn('[平台未就绪]',result.stderr)

    def test_missing_path_receipt_is_still_rejected(self):
        result,_=self.run_startup(BAD_PATH='1')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('[路径未确认]',result.stderr)

    def test_new_pid_after_warmup_is_rejected(self):
        result,_=self.run_startup(CHANGED_PID='1')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('[客户端已变化]',result.stderr)

    def run_shell(self,lost=False):
        with tempfile.TemporaryDirectory() as tmp:
            script=r'''
set -Eeuo pipefail
RAW="$1"
source "$2"
python3(){
  if [[ "$1" = "$QOS_TOOL" ]]; then
    if [[ " $* " = *' 46 '* ]]; then
      printf '46\n' >"$RAW/actual"
      if [[ "$3" = broken ]]; then return 1; fi
      test "${LOST_REPLY:-0}" != 1 || return 1
    fi
    if [[ " $* " = *' 0 ' ]] && [[ "${*: -1}" = 0 ]]; then printf '0\n' >"$RAW/actual"; fi
    printf '{"ok":true,"dscp":0,"tos":0,"connected":true,"pid":123,"local_port":40000}\n'
  else command python3 "$@"; fi
}
qos_preflight >"$RAW/preflight.txt"
test "$QOS_PID" = 123
test "$SOURCE_PORT" = 40000
if qos_mark; then test "${LOST_REPLY:-0}" = 0; else test "$QOS_CHANGED" = 1; fi
qos_restore
test "$QOS_CHANGED" = 0
test "$(cat "$RAW/actual")" = 0
qos_verify_restored
'''
            result=subprocess.run(['bash','-c',script,'test',tmp,str(HELPER)],text=True,
                capture_output=True,env={'PATH':'/usr/bin:/bin','LOST_REPLY':str(int(lost))})
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_success_restores(self): self.run_shell()
    def test_lost_reply_still_restores(self): self.run_shell(lost=True)
    def test_entry_points_preserve_control_variables(self):
        for name in ('10-qos-real-order-live.sh','11-qos-real-order-contention-live.sh'):
            source=(HELPER.parent/name).read_text()
            self.assertNotIn('qos_preflight |',source)
            self.assertNotIn('iptables -t mangle -A',source)
            self.assertIn('qos_restore',source)
            self.assertLess(source.index('\nqos_check_platform\n'),source.index('\nqos_preflight >'))
            self.assertLess(source.index('\nqos_preflight >'),source.index('\nqos_verify_path\n'))
            self.assertIn('and src port $3',source)
            subprocess.run(['bash','-n',str(HELPER.parent/name)],check=True)

if __name__=='__main__': unittest.main()
