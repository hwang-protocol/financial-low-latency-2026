#!/usr/bin/env python3
"""Exercise the actual classroom scripts with local command fixtures, never a VM."""
from pathlib import Path
import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path('assets/02-trading-baseline')
CAPTURE = ROOT/'reports/20260908T124946Z-03-market-paths/raw/switch-igmp.txt'
spec = importlib.util.spec_from_file_location('inspect_igmp', ROOT/ASSETS/'inspect-igmp.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class IgmpLessons(unittest.TestCase):
    def test_vlan20_and_group_checks(self):
        text = CAPTURE.read_text()
        with contextlib.redirect_stdout(io.StringIO()):
            inspector.inspect(text, True)
            inspector.inspect(text.replace('   : True', '\t:\tTrue').replace('       : False', ' : False'), True)
            for bad in [text.replace('Vlan 20 :', 'Vlan 21 :'),
                        text.replace('pruning active   : True', 'pruning active   : False').replace('pruning active   : False', 'pruning active   : True', 1),
                        text.replace('pruning active   : True', 'pruning active   : False'),
                        text.replace('20    20.1.1.254', '21    20.1.1.254'),
                        text.replace('Dynamic  -                      Et2', 'Static   -                      Et2'),
                        text.replace('Dynamic  -                      Et2', 'Dynamic  -                      Et2, Et11'),
                        text.replace('20    233.74.125.32', '21    233.74.125.32')]:
                with self.subTest(bad=bad[-100:]), self.assertRaises(ValueError):
                    inspector.inspect(bad, True)

    def test_ab_requires_both_dynamic_members(self):
        text = CAPTURE.read_text()
        row = next(line for line in text.splitlines() if line.startswith('20    233.74.125.32'))
        ab = text + row.replace('233.74.125.32', '233.74.125.33') + '\n'
        with contextlib.redirect_stdout(io.StringIO()):
            inspector.inspect(ab, True, ab=True)
            with self.assertRaises(ValueError): inspector.inspect(text, True, ab=True)
            with self.assertRaises(ValueError):
                inspector.inspect(ab.replace('233.74.125.33', '233.74.125.34'), True, ab=True)

    def test_display_preserves_bad_or_missing_values(self):
        text = CAPTURE.read_text().replace('pruning active   : True', 'pruning active   : False').replace('Dynamic  -                      Et2', 'Dynamic  -                      Et2, Et11')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            inspector.inspect(text, True, check=False)
        self.assertIn('pruning active   : False', out.getvalue())
        self.assertIn('Et2, Et11', out.getvalue())
        for missing in ['', '$ show igmp snooping querier\n20 \n$ show ip igmp snooping groups\n20 233.74.125.32 \n']:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                inspector.inspect(missing, True, check=False)
            self.assertIn('未找到字段', output.getvalue())

    def run_script(self, name, **extra):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def put(path, text, executable=False):
                f = root/path; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)
                if executable: f.chmod(0o755)
                return f
            for path in (ROOT/ASSETS).glob('*'):
                if path.is_file(): put(ASSETS/path.name, path.read_text().replace('/qyt-fll', td))
            put(Path('reports/run-state/02-trading-baseline.env'), 'RUN_ID=FIXTURE-02-trading-platform\nRUN_DIR=/var/tmp/flle-trading-lab-FIXTURE-02-trading-platform\nWEB_URL=http://fixture.invalid/\n')
            put(Path('apps/flle-trading-lab/scripts/transport_labctl.sh'), '''printf '%s\\n' "$*" >>"$CALLS"
if test "$1" = verify; then echo "exchange=ONLINE"; exit "${VERIFY_RC:-0}"; fi
if test "$1" = status; then printf '{"mode":"%s","transition":"READY","owner":"sfc"}\\n' "${PLANE:-SFC}"; fi
''')
            if not extra.get('MISSING_RECEIPT'):
                put(Path('reports/course-runs/FIXTURE-02-trading-platform/raw/first-trade.txt'), 'fixture_previous_order=42\n')
            put(Path('mode'), 'UNICAST')
            put(Path('eos.txt'), CAPTURE.read_text())
            put(Path('bin/ssh'), f'''#!{sys.executable}
import os,sys
from pathlib import Path
with open(os.environ['CALLS'],'a') as f:f.write('ssh '+ ' '.join(sys.argv[1:])+'\\n')
if 'ip maddr' in sys.argv[-1]:
 print('inet 233.74.125.32'+(' users 2' if os.environ.get('EXTRA_MEMBER') else ''))
 print('inet 233.74.125.33')
elif '/proc/net/mcfilter' in sys.argv[-1]:
 print('Idx Device MCA SRC INC EXC')
 if not os.environ.get('EMPTY_FILTER'):
  print('4 ens64n 0xe94a7d20 0x14010101 1 0')
  print('4 ens64n 0xe94a7d21 0x14010101 1 0')
elif '/sys/class/net/ens64np1/ifindex' in sys.argv[-1]: print('4')
else:
 for i in range(5):
  print('20.1.1.1.54321 > 233.74.125.32.31032: UDP, length 58')
  if not os.environ.get('MISSING_B'): print('20.1.1.1.54321 > 233.74.125.33.31033: UDP, length 58')
raise SystemExit(int(os.environ.get('SSH_RC','0')))
''', True)
            put(Path('bin/curl'), f'''#!{sys.executable}
import os,sys,json
from pathlib import Path
p=Path(os.environ['FIXTURE_ROOT'])/'mode'
with open(os.environ['CALLS'],'a') as f:f.write('curl '+ ' '.join(sys.argv[1:])+'\\n')
if os.environ.get('API_RC'):raise SystemExit(int(os.environ['API_RC']))
if '-d' in sys.argv:
 mode=json.loads(sys.argv[sys.argv.index('-d')+1])['market_mode']
 if mode=='UNICAST' and os.environ.get('RESTORE_FAIL'):raise SystemExit(29)
 if mode=='DUAL' and os.environ.get('SET_FAIL'):raise SystemExit(47)
 p.write_text(mode)
print(json.dumps({{'market_mode':p.read_text(), 'feed':{{'integrity':os.environ.get('BEFORE_INTEGRITY','HEALTHY'),'next_expected':100,'trading_gate':'fixture'}}}}))
''', True)
            put(Path('bin/python3'), f'''#!{sys.executable}
import os,sys,json
from pathlib import Path
if len(sys.argv)>1 and sys.argv[1].endswith('/eos_cli.py'):
 if os.environ.get('EOS_RC'):print('EOS fixture failure');raise SystemExit(int(os.environ['EOS_RC']))
 out=Path(sys.argv[sys.argv.index('--output')+1]);t=(Path(os.environ['FIXTURE_ROOT'])/'eos.txt').read_text();out.write_text(t);print(t)
elif len(sys.argv)>1 and sys.argv[1].endswith('/wait-feed-state.py'):
 if os.environ.get('HEALTH_RC'):
  print(json.dumps({{'market_mode':'MULTICAST','feed':{{'integrity':'GAP','next_expected':100}}}}))
  print('fixture health error',file=sys.stderr)
  raise SystemExit(int(os.environ['HEALTH_RC']))
 print(json.dumps({{'market_mode':'MULTICAST','feed':{{'integrity':'HEALTHY','next_expected':100}}}}))
else:os.execv({sys.executable!r},[{sys.executable!r}]+sys.argv[1:])
''', True)
            env=dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'], CALLS=str(root/'calls'), FIXTURE_ROOT=td, **extra)
            result=subprocess.run(['bash',str(root/ASSETS/name)],capture_output=True,text=True,env=env,timeout=15)
            calls=(root/'calls').read_text() if (root/'calls').exists() else ''
            return result.returncode,result.stdout+result.stderr,calls,(root/'mode').read_text()

    def test_configuration_and_query_scripts(self):
        for script in ['00c-igmp-configure.sh','01b-inspect-multicast.sh']:
            with self.subTest(script=script):
                rc,out,_,_=self.run_script(script)
                self.assertEqual(rc,0,out); self.assertIn('Vlan 20',out)
                rc,out,_,_=self.run_script(script,EOS_RC='37')
                self.assertEqual(rc,37,out);self.assertIn('EOS fixture failure',out)

    def test_configuration_prints_each_purpose_command_and_original_result(self):
        rc,out,_,_=self.run_script('00c-igmp-configure.sh')
        self.assertEqual(rc,0,out)
        commands=(ROOT/ASSETS/'igmp-configure.plan').read_text().splitlines()
        positions=[out.index('$ '+command+'\n') for command in commands]
        self.assertEqual(positions,sorted(positions))
        for number,position in enumerate(positions,1):
            self.assertLess(out.index(f'===== 第 {number} 条命令：'),position)
        self.assertEqual(len(re.findall(r'^===== 第 \d+ 条命令：',out,re.M)),9)
        self.assertNotRegex(out,re.compile(r'^===== [①②③④⑤⑥⑦⑧⑨]',re.M))
        self.assertIn('20.1.1.254 是查询报文的源 IP',out)
        self.assertIn('平台尚未启动时，目标行情组可能没有成员',out)
        self.assertNotIn('写入当前运行配置',out)
        command='ip igmp snooping vlan 20'
        transcript=CAPTURE.read_text().replace(command+'\n\n',command+'\nfixture diagnostic\n\n',1)
        with contextlib.redirect_stdout(io.StringIO()) as result:
            inspector.inspect(transcript,check=False,configuration=True)
        self.assertIn('fixture diagnostic',result.getvalue())
        transcript=transcript.replace('$ '+command+'\n'+command+'\nfixture diagnostic\n\n','')
        with contextlib.redirect_stdout(io.StringIO()) as result:
            inspector.inspect(transcript,check=False,configuration=True)
        self.assertNotIn('$ '+command+'\n',result.getvalue())

    def test_configuration_distinguishes_empty_members_from_missing_receipt(self):
        prefix = CAPTURE.read_text().split('$ show ip igmp snooping groups\n')[0]
        echo = 'show ip igmp snooping groups | no-more\n'
        for body in [echo, echo + '20 233.74.125.33 Dynamic - Et11\n']:
            with self.subTest(body=body), contextlib.redirect_stdout(io.StringIO()) as result:
                inspector.inspect(prefix + '$ show ip igmp snooping groups\n' + body,
                                  check=False, configuration=True)
            self.assertIn(body.rstrip('\n'), result.getvalue())
            self.assertIn('[成员说明] 当前回执未见 VLAN20 的 233.74.125.32 成员', result.getvalue())
            self.assertIn('运行 ①B 核对动态成员 Et2', result.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as result:
            inspector.inspect(prefix, check=False, configuration=True)
        self.assertIn('未找到组播成员表回执', result.getvalue())
        self.assertNotIn('[成员说明]', result.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as result:
            inspector.inspect(CAPTURE.read_text(), check=False, configuration=True)
        self.assertIn('Et2', result.getvalue())
        self.assertNotIn('[成员说明]', result.getvalue())

    def test_join_uses_existing_receiver_and_displays_subscription_count(self):
        rc,out,calls,_=self.run_script('01a-join-multicast.sh')
        self.assertEqual(rc,0,out);self.assertIn('feed-profile FIXTURE-02-trading-platform direct',calls)
        self.assertNotIn('unicast-only',calls)
        self.assertIn('cat /proc/net/mcfilter',calls)
        self.assertIn('cat /sys/class/net/ens64np1/ifindex',calls)
        for group in ('233.74.125.32','233.74.125.33'):
            self.assertIn(f'ens64np1 (Idx=4)  源 20.1.1.1 → 组 {group}  INC=1 EXC=0',out)
        self.assertIn('/var/tmp/flle-trading-lab-FIXTURE-02-trading-platform/flle-feed-receiver --data-ip 20.1.1.2 --unicast-port 42121 --multicast-group 233.74.125.32 --multicast-port 31032 --multicast-group-b 233.74.125.33 --multicast-port-b 31033 --multicast-source 20.1.1.1 --multicast-receiver 1 --receive-buffer-bytes 4194304 --client-queue-bytes 8388608 --client-queue-packets 32768 --telemetry-host 10.1.1.101 --socket /var/tmp/flle-trading-lab-FIXTURE-02-trading-platform/feed.sock',out)
        for fragment in ('[配置说明]', '[范围说明]', '--multicast-receiver 1',
                         '本步不切换 Exchange 的行情发送模式'):
            self.assertIn(fragment, out)
        self.assertNotIn('[加组说明]',out)
        self.assertNotIn('[内核说明]',out)
        rc,out,calls,_=self.run_script('01a-join-multicast.sh',PLANE='DPDK')
        self.assertNotEqual(rc,0);self.assertNotIn('feed-profile',calls)
        rc,out,_,_=self.run_script('01a-join-multicast.sh',EXTRA_MEMBER='1')
        self.assertEqual(rc,0,out);self.assertIn('users 2',out);self.assertNotIn('membership_users=',out)
        rc,out,_,_=self.run_script('01a-join-multicast.sh',SSH_RC='23')
        self.assertEqual(rc,23,out)

    def test_readonly_review_never_submits_or_changes_mode(self):
        for extra,expected in [({},0),({'EOS_RC':'37'},37),({'SSH_RC':'23'},23),({'VERIFY_RC':'41'},41),({'MISSING_RECEIPT':'1'},0),({'API_RC':'28'},28),({'BEFORE_INTEGRITY':'GAP'},0)]:
            with self.subTest(extra=extra):
                rc,out,calls,mode=self.run_script('03-readonly-review.sh',**extra)
                self.assertEqual(rc,expected,out)
                self.assertEqual(mode,'UNICAST')
                for mutation in ['-X POST', 'feed-profile', 'tcpdump', ' start ', ' deploy ']:
                    self.assertNotIn(mutation,calls)
                if expected==0:
                    self.assertIn('exchange=ONLINE',out)
                    self.assertNotIn('fixture_previous_order=42',out)
                    self.assertIn('integrity='+extra.get('BEFORE_INTEGRITY','HEALTHY'),out)
                    self.assertIn('233.74.125.32',out)

    def test_feed_capture_restores_mode_and_preserves_failure(self):
        for extra,expected in [({},0),({'SSH_RC':'42'},42),({'HEALTH_RC':'23'},23),({'SET_FAIL':'1'},47),({'RESTORE_FAIL':'1'},125),({'MISSING_B':'1'},1)]:
            with self.subTest(extra=extra):
                rc,out,calls,mode=self.run_script('01c-check-multicast-feed.sh',**extra)
                self.assertEqual(rc,expected,out)
                if expected!=125:self.assertEqual(mode,'UNICAST',out)
                if 'SET_FAIL' in extra:self.assertNotIn('ssh ',calls)
                if 'HEALTH_RC' in extra:
                    self.assertIn('应用接收检查失败，退出码 23',out)
                    self.assertIn('"integrity": "GAP"',out)
                    self.assertIn('fixture health error',out)
                self.assertIn('恢复检查前',out)
                if not extra:
                    captures=[line for line in calls.splitlines() if line.startswith('ssh ') and 'tcpdump' in line]
                    self.assertEqual(len(captures),1)
                    self.assertIn('-c 10',captures[0])
                    self.assertIn('dst host 233.74.125.32',captures[0])
                    self.assertIn('dst host 233.74.125.33',captures[0])
                    self.assertIn('A 路=5 包，B 路=5 包，共 10 包',out)

    def test_preparation_ab_mentions_b_and_reports_missing_b(self):
        with contextlib.redirect_stdout(io.StringIO()) as result:
            inspector.inspect(CAPTURE.read_text(),check=False,configuration=True,ab=True)
        self.assertIn('行情组播目的地址为 233.74.125.32 与 233.74.125.33',result.getvalue())
        self.assertIn('未见 VLAN20 的 233.74.125.33 成员',result.getvalue())

    def test_feed_rejects_unhealthy_baseline_before_any_mutation(self):
        for integrity in ['GAP', 'RECOVERING', '']:
            with self.subTest(integrity=integrity):
                rc,out,calls,mode=self.run_script('01c-check-multicast-feed.sh',BEFORE_INTEGRITY=integrity)
                self.assertEqual(rc,1,out)
                self.assertEqual(mode,'UNICAST')
                self.assertIn('检查前行情已非 HEALTHY',out)
                self.assertNotIn('-X POST',calls)
                self.assertNotIn('ssh ',calls)


if __name__ == '__main__': unittest.main()
