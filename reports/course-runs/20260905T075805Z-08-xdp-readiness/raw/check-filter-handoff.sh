#!/usr/bin/env bash
# Read-only identity/ownership gate shared by chapters 08-10.
# It does not erase unknown state or silently rebind a traffic generator's NIC.
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
scope="${1:?receiver or bridge}"
case "$scope" in receiver|bridge) ;; *) exit 2;; esac
state=Documents/reports/run-state/ch06-four-path.env
test -s "$state" || { echo '缺少第06章运行态；请先完成第07章章末交易验收。' >&2; exit 1; }
parent="$(sed -n 's/^RUN_ID=//p' "$state")"
printf '%s\n' '' '跳板机 / verify' '===== 查前章交接 =====' '[交易 profile] 对: SFC / READY / sfc  证: 第七章已归还交易驱动与可用状态' '$ transport_labctl.sh status <已保存的第06章 RUN>'
bash apps/flle-trading-lab/scripts/transport_labctl.sh status "$parent" | python3 -c '
import json,sys
x=json.load(sys.stdin)
print("trading_profile="+"/".join(str(x.get(k)) for k in ("mode","transition","owner")))
if (x.get("mode"),x.get("transition"),x.get("owner")) != ("SFC","READY","sfc"):
    sys.exit("第07章交接未完成：使用现有 07/13-trading-online-final.sh 归还 SFC，不手动 rebind。")'
ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 python3 - <<'REMOTE'
import json,pathlib,subprocess
dev=pathlib.Path('/sys/bus/pci/devices/0000:03:00.0')
assert (dev/'vendor').read_text().strip() == '0x1924', 'unexpected PCI vendor'
assert (dev/'device').read_text().strip() == '0x0b03', 'unexpected PCI device'
assert (dev/'driver').resolve().name == 'sfc', 'receiver must remain owned by sfc'
names=[p.name for p in (dev/'net').iterdir()]
assert len(names)==1, names
nic=names[0]
info=json.loads(subprocess.check_output(['ip','-j','-details','addr','show','dev',nic]))[0]
print(f'\nvm-2522-02 / verify\n===== 查接收口状态与地址 =====\n[{nic}] 对: UP / 原 MAC / 20.1.1.2  证: 接收口身份与地址保持前章状态\n$ ip -brief link show dev {nic}', flush=True)
subprocess.check_call(['ip','-brief','link','show','dev',nic])
print(f'$ ip -brief addr show dev {nic}', flush=True)
subprocess.check_call(['ip','-brief','addr','show','dev',nic])
print(f'\n===== 查接收口驱动 =====\n[{nic}] 对: sfc / 0000:03:00.0  证: X2522 仍由前章驱动管理\n$ ethtool -i {nic}', flush=True)
subprocess.check_call(['ethtool','-i',nic])
print(f'\n===== 查 XDP 挂载 =====\n[{nic}] 对: xdp: 段没有程序条目  证: 该接口没有已挂载的 XDP 程序\n$ bpftool net show dev {nic}', flush=True)
subprocess.check_call(['bpftool','net','show','dev',nic])
print("\n===== 查 RTL 适配器进程 =====\n[RTL] 对: 无匹配行且退出码为 1  证: 未找到本课 mold_filter_adapter 进程\n$ pgrep -af '[m]old_filter_adapter'", flush=True)
probe=subprocess.run(['pgrep','-af','[m]old_filter_adapter'])
print(f'pgrep exit_code={probe.returncode}', flush=True)
assert probe.returncode in (0,1), 'RTL process query failed'
print('\n===== 查 RTL 控制文件 =====\n[RTL] 对: No such file or directory  证: 本课控制文件不存在\n$ ls -ld -- /var/tmp/flle-market-filter.cmd', flush=True)
subprocess.run(['ls','-ld','--','/var/tmp/flle-market-filter.cmd'], stderr=subprocess.STDOUT)
assert info['address']=='00:0f:53:d3:af:21', info
assert any(a.get('local')=='20.1.1.2' for a in info['addr_info']), info
assert 'UP' in info['flags'] and info.get('operstate')=='UP', info
assert not info.get('master'), info
assert not info.get('xdp',{}).get('prog') and not info.get('xdp',{}).get('prog_id'), info
assert not pathlib.Path('/var/tmp/flle-market-filter.cmd').exists(), 'RTL control remains'
args=subprocess.check_output(['ps','-eo','args'],text=True)
assert 'mold_filter_adapter' not in args, 'previous RTL adapter still owns the receiver'
REMOTE
if test "$scope" = bridge; then
  ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 python3 - <<'REMOTE'
import json,pathlib,subprocess
for bdf,nic in [('0000:03:00.0','ens64f0np0'),('0000:03:00.1','ens64f1np1')]:
    dev=pathlib.Path('/sys/bus/pci/devices')/bdf
    assert (dev/'vendor').read_text().strip()=='0x14e4', bdf
    assert (dev/'device').read_text().strip()=='0x16d7', bdf
    assert (dev/'driver').resolve().name=='bnxt_en', '发包工具尚未归还 bnxt_en；不能强行覆盖'
    assert (dev/'net'/nic).exists(), bdf
    info=json.loads(subprocess.check_output(['ip','-j','-details','addr','show','dev',nic]))[0]
    assert 'UP' not in info['flags'] and not info['addr_info'], '工具口应 DOWN/无 IP'
    assert not info.get('master'), '工具口已有 Linux bridge/bond/VRF owner'
    assert not info.get('xdp',{}).get('prog') and not info.get('xdp',{}).get('prog_id'), info
    print('bridge_port='+nic+' BDF='+bdf+' bnxt_en/DOWN/no-IP/no-master/no-XDP')
args=subprocess.check_output(['ps','-eo','comm'],text=True)
assert not any(x in args for x in ('simple_switch','t-rex-64','testpmd')), '旧发包器/交换机进程尚未退出'
assert not subprocess.check_output(['ss','-ltnH','sport = :9090'],text=True).strip(), '9090 occupied'
REMOTE
  gate_tmp="$(mktemp -d /tmp/flle-filter-gate.XXXXXX)"
  trap 'rm -f -- "$gate_tmp/eos.txt"; rmdir "$gate_tmp"' EXIT
  python3 Documents/newDoc/assets/common/eos_cli.py \
    --plan Documents/newDoc/assets/09-p4/p4-trading-show.plan \
    --output "$gate_tmp/eos.txt" --mode show >/dev/null
  python3 - "$gate_tmp/eos.txt" <<'PY'
import pathlib,re,sys
text=pathlib.Path(sys.argv[1]).read_text()
assert 'VLAN 100 not found' in text and 'VLAN 200 not found' in text, '旧桥 VLAN 未归还'
for port in (1,2,11,12):
    section=text.split(f'$ show running-config interfaces Ethernet{port}\n',1)[1].split('\n$ ',1)[0]
    assert 'switchport access vlan 20' in section, section
    # EOS omits the default access mode from running-config.
    assert re.search(rf'^Et{port}\s+\S+\s+20\s+', text, re.M), '端口实际不在 VLAN20 access 状态'
    assert 'switchport mode trunk' not in section, section
    assert not re.search(r'^\s+shutdown\s*$',section,re.M), section
print('switch=Et1/Et2/Et11/Et12 access VLAN20; no VLAN100/200')
PY
fi
