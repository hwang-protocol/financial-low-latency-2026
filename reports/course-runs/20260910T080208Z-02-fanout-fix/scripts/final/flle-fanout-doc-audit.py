import collections
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

root = Path('/financial-low-latency')
docs = root / 'Documents/newDoc'
out = root / 'Documents/reports/course-runs/20260910T080208Z-02-fanout-fix/raw'
sys.path.insert(0, '/tmp/flle-review-python')
sys.path.insert(0, str(docs / 'assets/03-live-traffic'))
from markdown_it import MarkdownIt
from pcap_tools import read_pcap, parse_ethernet_ipv4, parse_udp

md = MarkdownIt('commonmark', {'html': True}).enable('table')
result = {'documents': {}, 'samples': {}, 'navigation': {}, 'checksums': {}}
executed = json.loads((root/'Documents/reports/run-state/00-03-fanout-replay.json').read_text())
assert all(card['status'] == 'PASS' and card['exit_code'] == 0 for card in executed['cards'])
for path in sorted(docs.glob('0[0-3]-*.md')):
    text = path.read_text()
    cards = list(re.finditer(r'<div style="border-left:6px solid (#[a-fA-F0-9]+);[^\n]*</div>', text))
    hashes = []
    for index, card in enumerate(cards):
        if card[1].lower() != '#15803d' or '需要运行' not in card[0]:
            continue
        end = cards[index+1].start() if index+1 < len(cards) else len(text)
        blocks = re.findall(r'^```bash\n(.*?)^```', text[card.end():end], re.M | re.S)
        assert len(blocks) == 1
        hashes.append(hashlib.sha256(blocks[0].encode()).hexdigest())
    assert hashes == [card['sha256'] for card in executed['cards'] if card['chapter'] == path.name[:2]]
result['executed_21_green_cards_match_final_documents'] = True
namespace = {'__file__': str(docs / 'assets/common/verify-filter-course-cards.py')}
source = Path(namespace['__file__']).read_text().split('def check():')[0]
exec(compile(source, namespace['__file__'], 'exec'), namespace)
for path in sorted(docs.glob('[01][0-9]-*.md')):
    result['navigation'][path.name] = namespace['check_navigation'](path.read_text(), path.name)


class CheckHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []
    def handle_starttag(self, tag, attrs):
        if tag not in ['img', 'hr', 'br', 'input', 'meta', 'link']:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, tag


for path in sorted(docs.glob('0[0-3]-*.md')):
    text = path.read_text()
    tokens = md.parse(text)
    html = CheckHTML(); html.feed(md.render(text)); assert not html.stack
    fences = [token for token in tokens if token.type == 'fence']
    bash = [token.content for token in fences if token.info == 'bash']
    for block in bash:
        subprocess.run(['bash', '-n'], input=block, text=True, check=True)
    for token in fences:
        if path.name.startswith(('02', '03')):
            assert '\n'.join(text.splitlines()[:token.map[0]]).rstrip().endswith('</div>'), (path, token.map)
    for match in re.finditer(r'\]\(([^)]+)\)|src="([^"]+)"', text):
        link = match[1] or match[2]
        if '://' not in link and not link.startswith('#'):
            assert (docs / link.split('#')[0]).exists(), (path, link)
    if path.name.startswith('03'):
        scripts = [docs/'assets/03-live-traffic'/name for name in
                   ['01-capture-live-market.sh', '02-compare-market-transports.sh', '03-capture-live-order.sh']]
        assert bash == [p.read_text() for p in scripts]
        assert max(map(lambda s: len(s.splitlines()), bash)) <= 50
        paragraphs = [tokens[i+1].content for i,t in enumerate(tokens[:-1]) if t.type == 'paragraph_open']
        repeated = [p for p,c in collections.Counter(paragraphs).items() if c > 1 and len(p) > 40]
        assert not repeated, repeated
    if path.name.startswith('02'):
        for script in (docs/'assets/02-trading-baseline').glob('*.sh'):
            if script.name.startswith(('00c-', '01a-', '01b-', '01c-', '03-')):
                assert script.read_text() in bash, script
    result['documents'][path.name] = dict(bash_lines=[len(block.splitlines()) for block in bash],
                                        tables=sum(t.type=='table_open' for t in tokens))


def short(text):
    text = re.sub(r'/financial-low-latency/Documents/reports/course-runs/[^/\s]+/raw/', '…/', text)
    text = re.sub(r'/var/tmp/\d{8}T\d{6}Z-03-[^\s\']+\.pcap', '…/capture.pcap', text)
    return re.sub(r'/var/tmp/flle-trading-lab-\d{8}T\d{6}Z-02-trading-platform/', '…/', text)


chapter = (docs/'03-live-trading-traffic-and-protocols.md').read_text()
runs = root/'Documents/reports/course-runs'
mapping = [('行情输出', '20260910T085538Z-03-live-market'),
           ('三模式输出', '20260910T085544Z-03-market-paths'),
           ('订单输出', '20260910T085551Z-03-live-order')]
for label, run in mapping:
    sample = re.search('仅供展示 · '+label+r'.*?```text\n(.*?)\n```', chapter, re.S)[1]
    lines = iter(short((runs/run/'classroom.txt').read_text()).splitlines())
    for line in sample.splitlines():
        if line:
            assert any(actual == line for actual in lines), (label, line)
    result['samples'][label] = dict(run=run, lines=len(sample.splitlines()), ordered_exact=True)
    for filename in ['SHA256SUMS', 'CLASSROOM_SHA256SUMS']:
        manifest = runs/run/filename
        check = subprocess.run(['sha256sum', '-c', str(manifest)], capture_output=True, text=True)
        assert check.returncode == 0, check.stdout + check.stderr
        result['checksums'][run+'/'+filename] = len(manifest.read_text().splitlines())

shared = 'images/course-visuals/03-diagrams/03-market-packet-fields.svg'
for chapter in ['03-live-trading-traffic-and-protocols.md', '08-ebpf-xdp-programmable-network.md',
                '09-p4-programmable-data-plane.md', '10-verilator-fpga-smartnic-simulation.md']:
    assert shared in (docs/chapter).read_text()
ns = {'s':'http://www.w3.org/2000/svg'}
svg = ET.parse(docs/shared).getroot()
fields = {node.attrib['data-field']:(int(node.attrib['data-offset']),int(node.attrib['data-width']))
          for node in svg.findall('s:g', ns) if 'data-field' in node.attrib}
assert fields == {'Message Type':(0,1),'Stock Locate':(1,2),'Tracking Number':(3,2),'Timestamp':(5,6),
                  'Order Reference Number':(11,8),'Buy/Sell Indicator':(19,1),'Shares':(20,4),
                  'Stock':(24,8),'Price':(32,4)}
_, _, packets = read_pcap(runs/mapping[0][1]/'raw/live-market.pcap')
frame = packets[8].data
udp = parse_udp(parse_ethernet_ipv4(frame))
assert len(frame) == 100 and struct.unpack_from('!QHH', udp.payload, 10) == (246208,1,36)
itch = udp.payload[22:]
assert itch[:1] == b'A' and int.from_bytes(itch[1:3],'big') == 8095 and itch[24:32] == b'NVDA    '
assert int.from_bytes(itch[20:24],'big') == 1 and int.from_bytes(itch[32:36],'big') == 1700000
chapter_text = (docs/'03-live-trading-traffic-and-protocols.md').read_text()
assert '本例 246200～246399 共 200 条' in chapter_text
assert '本例第 9 帧' in chapter_text and 'itch_types 中 A:180' in chapter_text
rtl = (docs/'assets/10-verilator/market_filter.sv').read_text()
for name,start,width in [('type',0,1),('locate',1,2),('stock',24,8)]:
    hi,lo=287-start*8,288-(start+width)*8
    assert f'in_{name} = s_itch[{hi}:{lo}]' in rtl
    assert (int.from_bytes(itch,'big')>>lo)&((1<<(hi-lo+1))-1) == int.from_bytes(itch[start:start+width],'big')
result['current_pcap_shared_fields_rtl'] = 'PASS'
chapter2 = (docs/'02-host-native-trading-system-baseline.md').read_text()
blocks = re.findall(r'```text\n(.*?)\n```', chapter2, re.S)
assert len(blocks) == 11
card_out = runs/'20260910T085246Z-00-03-fanout-replay/raw'
for index, card in [(0,'02-01'),(1,'02-02'),(3,'02-03'),(4,'02-04'),
                    (6,'02-05'),(7,'02-06'),(8,'02-07'),(9,'02-08'),(10,'02-09')]:
    actual = iter(line.strip() for line in (card_out/(card+'.txt')).read_text().splitlines())
    for line in blocks[index].splitlines():
        if line.strip():
            assert any(value == line.strip() for value in actual), (card, line)
    result['samples']['chapter02-'+card] = {'ordered_exact_ignoring_edge_whitespace': True}
plan = (docs/'assets/02-trading-baseline/igmp-configure.plan').read_text()
assert blocks[2].splitlines() == [line for line in plan.splitlines() if line and not line.startswith('#')]
command = next(line[2:] for line in (card_out/'02-05.txt').read_text().splitlines()
               if line.startswith('$ /var/tmp/flle-trading-lab-'))
assert shlex.split(blocks[5].replace('\\\n', ' ')) == shlex.split(command)
assert '`2956300` 是 `295.63`' in chapter2
result['samples']['chapter02-native-command-and-price'] = 'PASS'
for folder in [docs/'images/course-visuals/03-diagrams', docs/'images/course-visuals']:
    check = subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=folder,capture_output=True,text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    result['checksums'][str(folder.relative_to(root))] = len((folder/'SHA256SUMS').read_text().splitlines())
(out/'document-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
