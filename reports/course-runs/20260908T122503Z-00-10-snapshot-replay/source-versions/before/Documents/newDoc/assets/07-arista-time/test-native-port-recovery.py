#!/usr/bin/env python3
"""Exercise the actual recovery function against an isolated udev rename race."""
from pathlib import Path
import os
import subprocess
import tempfile

source=(Path(__file__).parent/'live-support/lanz/remote-lanz-trex-control.sh').read_text()
function=source[source.index('recover_host()'):source.index('\ncase "${1:-}"')]
with tempfile.TemporaryDirectory(prefix='flle-udev-recovery-') as tmp:
    root=Path(tmp);sys=root/'sys'
    for bdf in ('0000:03:00.0','0000:03:00.1'):
        device=sys/'bus/pci/devices'/bdf;device.mkdir(parents=True)
        driver=sys/'bus/pci/drivers/bnxt_en';driver.mkdir(parents=True,exist_ok=True)
        (device/'driver').symlink_to(driver)
    pool=sys/'kernel/mm/hugepages/hugepages-2048kB';pool.mkdir(parents=True)
    (pool/'nr_hugepages').write_text('128')
    isolated=function.replace('/sys/',str(sys)+'/').replace('/var/run/dpdk/',str(root)+'/dpdk/')
    harness='''set -Eeuo pipefail
prefix=fixture
stop_server(){ :; }
modprobe(){ :; }
findmnt(){ :; }
udevadm(){ touch "$TEST_ROOT/settled"; }
resolve_iface(){ if test -f "$TEST_ROOT/settled"; then echo ens64f0np0; else echo eth0; fi; }
ip(){ case "$*" in *eth0*) echo 'stale interface name' >&2; return 1;; esac; }
'''+isolated+'\nrecover_host\n'
    env=dict(os.environ,TEST_ROOT=str(root))
    result=subprocess.run(['bash'],input=harness,text=True,env=env,capture_output=True)
    assert result.returncode==0,result.stderr
    assert (pool/'nr_hugepages').read_text()=='0\n'
    (root/'settled').unlink()
    old=harness.replace('    udevadm settle --timeout=20\n','')
    result=subprocess.run(['bash'],input=old,text=True,env=env,capture_output=True)
    assert result.returncode!=0 and 'stale interface name' in result.stderr
print('PASS native port recovery waits for udev rename; old ordering fails the race fixture')
