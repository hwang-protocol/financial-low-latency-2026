#!/usr/bin/env python3
"""Local Chapter 03 content contracts; requires markdown-it-py, never uses devices."""
import contextlib
import importlib.util
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

try:
    from markdown_it import MarkdownIt
except ModuleNotFoundError as error:
    if error.name != 'markdown_it':
        raise
    raise SystemExit('Missing markdown_it. On the course Ubuntu host run: '
                     'apt-get install --no-install-recommends python3-markdown-it; '
                     'see assets/03-live-traffic/README.md for verification setup.') from error

ASSETS = Path(__file__).resolve().parent
CHAPTER = ASSETS.parents[1] / '03-live-trading-traffic-and-protocols.md'


class DocumentFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHAPTER.read_text()
        cls.tokens = MarkdownIt('commonmark', {'html': True}).enable('table').parse(cls.text)

    def test_every_intended_bold_span_matches_actual_parser_output(self):
        for token in self.tokens:
            if token.type != 'inline' or '**' not in token.content:
                continue
            expected = re.findall(r'\*\*(.+?)\*\*', token.content)
            actual, opened = [], []
            for child in token.children:
                if child.type == 'strong_open':
                    opened.append('')
                elif child.type == 'strong_close':
                    actual.append(opened.pop())
                else:
                    for index in range(len(opened)):
                        opened[index] += child.content
                if child.type == 'text':
                    self.assertNotIn('**', child.content, token.map)
            self.assertEqual(actual, expected, token.map)

    def test_seven_affected_terms_are_bold_without_spilling_into_prose(self):
        rendered = MarkdownIt('commonmark').render(
            self.text + '\n' + (ASSETS / 'READING-NOTES.md').read_text())
        for term in ('载荷（payload）', '偏移（offset）', '大端（big-endian）',
                     'Unix Socket（同机进程通信通道）', '分帧（framing）',
                     'U（Unsequenced Data，未编号业务数据）',
                     'S（Sequenced Data，按会话顺序编号的业务数据）'):
            self.assertIn('<strong>' + term + '</strong>', rendered)
        self.assertIn('<strong>发送模式</strong>', rendered)
        self.assertNotIn('<strong>分发。', rendered)

    def test_itch_type_counts_match_the_explanation(self):
        summary = re.search(r'^sequence=.* itch_types=(.+)$', self.text, re.M)
        counts = dict((kind, int(count)) for kind, count in
                      (field.split(':') for field in summary[1].split(',')))
        # Explain capture-wide counts before switching to the single-frame diagram.
        explanation = self.text[summary.end():].split('<div ', 1)[0]
        for kind, count in counts.items():
            self.assertIn(f'{count} 条 {kind}', explanation)
        self.assertIn(f'合计 {sum(counts.values())} 条消息', explanation)

    def test_live_verification_is_scoped_to_the_measured_step(self):
        scope = next(line for line in self.text.splitlines() if line.startswith('**验证范围：**'))
        self.assertIn('运行 ② 已实测三种发送模式', scope)
        self.assertIn('运行 ① 保留历史', scope)
        self.assertIn('运行 ③ 保留历史', scope)
        self.assertNotRegex(scope, r'20\d{6}T\d{6}Z')
        self.assertIn('20260915T082055Z-03-live-market', (ASSETS / 'README.md').read_text())
        self.assertIn('均不作为新版平台的验收结果', scope)
        self.assertNotIn('下面是本次实际', self.text)

    def test_green_cards_and_asset_line_counts_match(self):
        blocks = [token.content for token in self.tokens
                  if token.type == 'fence' and token.info == 'bash']
        scripts = sorted(ASSETS.glob('0[1-3]-*.sh'))
        self.assertEqual(blocks, [scripts[0].read_text(), "cd /qyt-fll && bash assets/03-live-traffic/02-compare-market-transports.sh\n", scripts[2].read_text()])
        self.assertEqual([len(block.splitlines()) for block in blocks], [42, 1, 36])
        rows = re.findall(r'\| \[([^\]]+)\]\(assets/03-live-traffic/[^)]+\) \| (\d+) \|', self.text)
        self.assertEqual(len(rows), 8)
        for name, count in rows:
            self.assertEqual(len((ASSETS / name).read_text().splitlines()), int(count), name)

    def test_mode_specific_expectations_match_terminal_and_document(self):
        spec = importlib.util.spec_from_file_location('classroom', ASSETS / 'classroom-output.py')
        classroom = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(classroom)
        expected = ('仅 A 路组播 233.74.125.32:31032', '仅 B 路组播 233.74.125.33:31033',
                    'A 路 233.74.125.32:31032 与 B 路 233.74.125.33:31033 均有包')
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / 'raw'
            raw.mkdir()
            (raw / 'membership.txt').write_text('inet 233.74.125.32\n')
            with mock.patch.object(classroom, 'native') as native, contextlib.redirect_stdout(io.StringIO()):
                classroom.display('decode', 'transports', [temporary, '0', '1', '1', '1', '0', '0'])
            self.assertEqual([call.args[4] for call in native.call_args_list], list(expected))
        for mode in ('MULTICAST_A', 'MULTICAST_B', 'DUAL'):
            self.assertIn(f'mode={mode} captured=120 ', self.text)
        self.assertIn('三种模式实测结果', self.text)
        self.assertNotIn('双组播新版待实机运行', self.text)

    def test_each_itch_type_is_one_horizontal_message_in_the_shared_diagram(self):
        images = CHAPTER.parent / 'images/course-visuals/03-diagrams'
        common = [('Message Type', 1), ('Stock Locate', 2),
                  ('Tracking Number', 2), ('Timestamp', 6)]
        order = [('Order Reference Number', 8), ('Buy/Sell Indicator', 1),
                 ('Shares', 4), ('Stock', 8), ('Price', 4)]
        layouts = {
            'A': (36, order),
            'F': (40, order + [('Attribution', 4)]),
            'E': (31, [('Order Reference Number', 8), ('Executed Shares', 4), ('Match Number', 8)]),
            'D': (19, [('Order Reference Number', 8)]),
            'U': (35, [('Original Order Reference Number', 8), ('New Order Reference Number', 8),
                       ('Shares', 4), ('Price', 4)]),
            'P': (44, order + [('Match Number', 8)]),
        }
        name = '03-itch-type-strips.svg'
        self.assertEqual(self.text.count(f'src="images/course-visuals/03-diagrams/{name}"'), 1)
        svg = ET.parse(images / name).getroot()
        rows = svg.findall(".//*[@data-message-strip='true']")
        self.assertEqual([row.attrib['data-itch-type'] for row in rows], list(layouts))
        self.assertIsNone(svg.find('.//{*}marker'))
        for index, (kind, (size, fields)) in enumerate(layouts.items()):
            row = rows[index]
            self.assertEqual(int(row.attrib['data-message-bytes']), size)
            expected, offset = [], 0
            for field, width in common + fields:
                expected.append((field, offset, width))
                offset += width
            self.assertEqual(offset, size)
            actual = [(g.attrib['data-field'], int(g.attrib['data-offset']), int(g.attrib['data-width']))
                      for g in row if 'data-field' in g.attrib]
            self.assertEqual(actual, expected, kind)
            cells = [g.find('{*}rect') for g in row if 'data-field' in g.attrib]
            x = 40
            for cell in cells:
                self.assertEqual(int(cell.attrib['x']), x)
                self.assertEqual(int(cell.attrib['y']), 144 + index * 190)
                self.assertEqual(cell.attrib['height'], '148')
                x += int(cell.attrib['width'])
            self.assertLessEqual(x, 1160)
            type_cell = row.find(".//*[@data-field='Message Type']")
            self.assertIn(kind, [node.text for node in type_cell.findall('{*}text')])
        self.assertNotIn('undefined', (images / name).read_text())

    def test_mold_is_one_envelope_strip_without_duplicate_layout_tables(self):
        section = self.text.split('### 一包行情怎样逐层拆开')[1].split('### 抓取、解码与读结果')[0]
        parsed = MarkdownIt('commonmark').enable('table').parse(section)
        # The diagram owns byte layouts. Reading/limit tables remain permitted
        # by writing rules 3.3 and 7.9; do not ban every table in this section.
        for index, token in enumerate(parsed):
            if token.type == 'thead_open':
                end = next(i for i in range(index + 1, len(parsed))
                           if parsed[i].type == 'thead_close')
                headers = [t.content for t in parsed[index:end] if t.type == 'inline']
                self.assertFalse(any('偏移' in h or '宽度' in h for h in headers), headers)
        svg = ET.parse(CHAPTER.parent / 'images/course-visuals/03-diagrams/03-mold-envelope-strip.svg').getroot()
        self.assertIsNone(svg.find('.//{*}marker'))

        def layer(name):
            group = svg.find(f".//*[@data-layer='{name}']")
            self.assertIsNotNone(group, name)
            return group

        def fields(group):
            return [(g.attrib['data-field'], int(g.attrib['data-offset']), int(g.attrib['data-width']))
                    for g in group if 'data-field' in g.attrib]

        def cells(group):
            return [g.find('{*}rect') for g in group if 'data-field' in g.attrib]

        ipv4, udp, mold = layer('ipv4'), layer('udp'), layer('mold')
        self.assertEqual(fields(mold), [
            ('Session', 0, 10),
            ('Sequence Number', 10, 8),
            ('Message Count', 18, 2),
            ('Message Length', 20, 2),
            ('Message Data', 22, 36),
        ])
        self.assertEqual(sum(width for _, _, width in fields(mold)), 58)
        self.assertEqual(fields(udp), [
            ('Source Port', 0, 2),
            ('Destination Port', 2, 2),
            ('Length', 4, 2),
            ('Checksum', 6, 2),
        ])
        self.assertEqual([name for name, _, _ in fields(ipv4)], [
            'Version and IHL', 'Total Length', 'Protocol', 'Source Address', 'Destination Address',
        ])
        dest = next(group for group in ipv4 if group.attrib.get('data-field') == 'Destination Address')
        self.assertIn('233.74.125.32', [node.text for node in dest.findall('{*}text')])
        self.assertTrue(any('组播' in (node.text or '') for node in dest.findall('{*}text')))
        udp_dst = next(group for group in udp if group.attrib.get('data-field') == 'Destination Port')
        self.assertIn('31032', [node.text for node in udp_dst.findall('{*}text')])
        self.assertTrue(any('组播' in (node.text or '') for node in udp_dst.findall('{*}text')))
        ys = []
        for group in (ipv4, udp, mold):
            rects = cells(group)
            self.assertEqual(len({rect.attrib['y'] for rect in rects}), 1)
            self.assertEqual(sum(int(rect.attrib['width']) for rect in rects), 1120)
            x = 40
            for rect in rects:
                self.assertEqual(int(rect.attrib['x']), x)
                x += int(rect.attrib['width'])
            ys.append(int(rects[0].attrib['y']))
        self.assertLess(ys[0], ys[1])
        self.assertLess(ys[1], ys[2])
        self.assertIn('每包只装一条 ITCH', section)
        self.assertEqual(len(re.findall(r'<img ', section)), 2)

    def test_later_filter_chapters_embed_the_same_image_in_place(self):
        shared = 'src="images/course-visuals/03-diagrams/03-itch-type-strips.svg"'
        # The current FPGA GUI chapter has its own diagrams; P4/old chapter 09 retired.
        for prefix in ('03-', '07-'):
            chapter = next(CHAPTER.parent.glob(prefix + '*.md')).read_text()
            self.assertEqual(chapter.count(shared), 1, prefix)

    def test_all_teaching_images_use_the_required_frame(self):
        frames = re.findall(r'<div style="([^"]+)">\s*<img [^>]+style="([^"]+)"[^>]*>\s*</div>', self.text)
        self.assertEqual(len(frames), self.text.count('<img '))
        self.assertEqual(len(frames), 9)
        outer = 'background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;'
        inner = 'display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;'
        for frame, image in frames:
            self.assertEqual(frame, outer)
            self.assertEqual(image, inner)

    def test_each_run_maps_output_fields_before_the_judgment(self):
        runs = re.split(r'^## 运行 [①②③]：.*$', self.text, flags=re.M)[1:]
        self.assertEqual(len(runs), 3)
        for run in runs:
            result = run.split('```bash\n', 1)[1].split('```', 1)[1]
            reading = result.split('>关键现象</span>', 1)[0]
            parsed = MarkdownIt('commonmark').enable('table').parse(reading)
            headers = []
            for index, token in enumerate(parsed):
                if token.type == 'thead_open':
                    end = next(i for i in range(index + 1, len(parsed))
                               if parsed[i].type == 'thead_close')
                    headers.append([t.content for t in parsed[index:end] if t.type == 'inline'])
            self.assertTrue(any(h in headers for h in (['字段', '实测例子', '学员读什么'], ['字段', '预期结果', '学员读什么'])))

    def test_each_run_hands_its_evidence_to_the_next_step(self):
        runs = re.split(r'^## 运行 [①②③]：.*$', self.text, flags=re.M)[1:]
        for run in runs:
            self.assertEqual(run.count('**下一线索：**'), 1)
            self.assertLess(run.index('>关键现象</span>'), run.index('**下一线索：**'))


if __name__ == '__main__':
    unittest.main()
