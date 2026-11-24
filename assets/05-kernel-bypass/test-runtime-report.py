#!/usr/bin/env python3
"""Test runtime report success/failure paths with mocked SSH and devices."""
from pathlib import Path
import tempfile,os,subprocess,hashlib,json,shlex
root=Path(__file__).resolve().parents[2]
script=root/'assets/05-kernel-bypass/01c-verify-runtime.sh'
archive=root/'reports/course-runs/20260907T145936.025447662Z-06-runtime-verify/raw/result.txt'
raw=archive.read_text();host1=raw.split('===== 已部署的 Onload 运行时 =====')[1]
version='\n'.join(line for line in host1.splitlines() if line.startswith(('Onload ','Copyright ','Built:','Build profile header:','Kernel module:')))+'\n'
results=[]
with tempfile.TemporaryDirectory(prefix='flle-runtime-report-test-') as dirname:
 work=Path(dirname);bin_dir=work/'bin';bin_dir.mkdir();fixture=work/'version.txt';fixture.write_text(version)
 envfile=work/'mock-env.sh';envfile.write_text('''hostname(){ case "$MOCK_HOST" in 10.1.1.1) echo vm-2522-01;; *) echo vm-2522-02;; esac; }
onload(){
  if [[ "$MOCK_HOST" = 10.1.1.2 ]]; then
    case "$MOCK_SCENARIO" in
      version-mismatch) sed 's/Kernel module: .*/Kernel module: other/' "$MOCK_FIXTURE"; return;;
      version-missing) sed '/Kernel module:/d' "$MOCK_FIXTURE"; return;;
      command-failed) echo 'onload: failed to query version' >&2; return 7;;
    esac
  fi
  command cat "$MOCK_FIXTURE"
  if [[ "$MOCK_SCENARIO" = extra-native-line ]]; then echo 'native diagnostic retained'; fi
}
cat(){ if [[ "$1" = /sys/module/sfc/version ]]; then echo 6.1.0.1009; else command cat "$@"; fi; }
modinfo(){
  if [[ "$MOCK_HOST" = 10.1.1.2 && "$MOCK_SCENARIO" = sfc-mismatch ]]; then echo other; else echo 6.1.0.1009; fi
}
test(){
  if [[ "$1" = -c && ( "$2" = /dev/onload || "$2" = /dev/sfc_char ) ]]; then
    if [[ "$MOCK_HOST" = 10.1.1.2 && "$MOCK_SCENARIO" = missing-onload && "$2" = /dev/onload ]]; then return 1; fi
    if [[ "$MOCK_HOST" = 10.1.1.2 && "$MOCK_SCENARIO" = missing-sfc-char && "$2" = /dev/sfc_char ]]; then return 1; fi
    return 0
  fi
  builtin test "$@"
}
ls(){
  case "$2" in
    /dev/onload) echo 'crw-rw-rw- 1 root root 237, 0 Sep  7 22:36 /dev/onload';;
    /dev/sfc_char) echo 'crw-rw-rw- 1 root root 238, 0 Sep  7 22:36 /dev/sfc_char';;
    *) command ls "$@";;
  esac
}
readlink(){
  if [[ "$1" = /sys/bus/pci/devices/0000:03:00.0/driver ]]; then
    if [[ "$MOCK_HOST" = 10.1.1.2 && "$MOCK_SCENARIO" = wrong-owner ]]; then echo /sys/bus/pci/drivers/vfio-pci; else echo /sys/bus/pci/drivers/sfc; fi
  else command readlink "$@"; fi
}
''')
 ssh=bin_dir/'ssh';ssh.write_text('''#!/usr/bin/env bash
for arg in "$@"; do case "$arg" in root@*) export MOCK_HOST="${arg#root@}";; esac; done
exec /bin/bash -s
''');ssh.chmod(0o755)
 for scenario in ['success','version-mismatch','version-missing','sfc-mismatch','missing-onload','missing-sfc-char','wrong-owner','command-failed','extra-native-line']:
  run=work/scenario;run.mkdir();copy=run/'check.sh';copy.write_text(script.read_text().replace('cd /qyt-fll','cd '+shlex.quote(str(run)),1))
  env=os.environ.copy();env.update(PATH=str(bin_dir)+os.pathsep+env['PATH'],BASH_ENV=str(envfile),MOCK_FIXTURE=str(fixture),MOCK_SCENARIO=scenario)
  r=subprocess.run(['bash',str(copy)],capture_output=True,text=True,env=env,timeout=10)
  success=scenario in ('success','extra-native-line');expected=0 if success else 7 if scenario=='command-failed' else 1
  assert r.returncode==expected,(scenario,r.returncode,r.stdout,r.stderr)
  reports=list((run/'reports/course-runs').iterdir());assert len(reports)==1
  report=reports[0];text=(report/'raw/result.txt').read_text()
  separator='\n'+'='*72+'\n'
  assert text.count(separator)==1
  host_sections=text.split(separator)
  assert 'vm-2522-01' in host_sections[0] and 'vm-2522-02' not in host_sections[0]
  assert 'vm-2522-02' in host_sections[1] and 'vm-2522-01' not in host_sections[1]
  for line in (report/'SHA256SUMS').read_text().splitlines():
   digest,name=line.split(None,1);assert hashlib.sha256((report/name).read_bytes()).hexdigest()==digest
  assert f'EXIT_CODE={expected}' in (report/'run.env').read_text()
  assert '# 两端均为 runtime=READY' in text if success else '# 两端均为 runtime=READY' not in text
  assert text.count('runtime=READY                     # 本机运行时检查通过')== (2 if success else 1)
  if success:
   for number in range(1,8):assert text.count(f'# {number}. ')==2
  elif scenario!='command-failed':assert 'runtime=NOT_READY' in text
  if scenario=='extra-native-line':assert text.count('native diagnostic retained')==2
  results.append({'scenario':scenario,'exit_code':r.returncode,'result':'PASS','receipt_sha_verified':True})
print(json.dumps(results,ensure_ascii=False,indent=2))
