from pathlib import Path
import re,sys,json
R=Path('/financial-low-latency');chapter=sys.argv[1];run=sys.argv[2];p=next((R/'Documents/newDoc').glob(chapter+'-*.md'));s=p.read_text();raw=R/'Documents/reports/course-runs'/run/'raw'
if chapter=='09':
 pairs=[('configure','[1/4'),('inspect','[2/4'),('drop','[3/4'),('restore','[4/4')]
else:
 pairs=[('prepare','vm-2522-02 / build\n===== 查构建自测'),('arm','vm-2522-02 / control'),('verify','vm-2522-02 / verify\n===== 查丢弃'),('restore','vm-2522-02 / restore')]
for name,marker in pairs:
 data=(raw/(name+'-display.txt')).read_text().rstrip('\n');a=s.index('```text\n'+marker);b=s.index('\n```',a);s=s[:a]+'```text\n'+data+s[b:]
if chapter=='09':
 s=s.replace('20260907T151801Z-09-p4-drop-live',run).replace('20260908T101323Z-09-p4-drop-live',run)
 seq=re.search(r'dropped_sequence\[0\]= (\d+)',(raw/'drop-display.txt').read_text()).group(1)
 s=s.replace('177 / 177',seq+' / '+seq).replace('当次序号不必是 177','当次序号不必是 '+seq)
 position=re.search(r'AAPL持仓：(\d+) → (\d+)',(raw/'restore-display.txt').read_text()).groups();s=s.replace('HEALTHY；两笔 ORDER_EXECUTED；1 → 1','HEALTHY；两笔 ORDER_EXECUTED；'+' → '.join(position))
else:
 s=s.replace('20260907T152509Z-10-rtl-stages',run)
 seq=re.search(r'rtl_drop sequence=(\d+)',(raw/'verify-display.txt').read_text()).group(1);s=s.replace('本次实际序号是 220','本次实际序号是 '+seq).replace('220 / 220',seq+' / '+seq)
p.write_text(s)
for name,marker in pairs:
 data=(raw/(name+'-display.txt')).read_text().rstrip('\n');assert '```text\n'+data+'\n```' in s
print('PASS refreshed four exact stage display excerpts',chapter,run,'sequence',seq)
