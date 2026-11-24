#!/usr/bin/env python3
"""Read-only Chapter 00–10 navigation and 08–10 executable-card checks."""
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "Documents/newDoc"
CHAPTERS = [
    ("08-ebpf-xdp-programmable-network.md", "08-xdp", [
        "00-xdp-toolchain-prep.sh", "01-xdp-hook-readiness.sh",
        "02-xdp-action-model.sh", "03-xdp-parser-bounds.sh", "04-xdp-build.sh",
    ], "05-xdp-inline-live.sh", "run-xdp-receiver-live.sh"),
    ("09-p4-programmable-data-plane.md", "09-p4", [
        "00-p4-toolchain-prep.sh", "00b-bmv2-tool-prep.sh",
        "08-compile-trading-bridge.sh",
    ], "09-trading-p4-drop-live.sh", "run-trading-p4-drop-live.sh"),
    ("10-verilator-fpga-smartnic-simulation.md", "10-verilator", [
        "00-verilator-toolchain-prep.sh",
    ], "08-rtl-filter-live.sh", "stage-actions.sh"),
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


P4_STAGES = ["09a-configure-p4-path.sh", "09b-inspect-p4-path.sh",
             "09c-drop-one-packet.sh", "09d-restore-p4-path.sh"]


RTL_STAGES = ["08a-prepare-rtl-filter.sh", "08b-arm-rtl-filter.sh",
              "08c-verify-rtl-filter.sh", "08d-restore-rtl-filter.sh"]

class NavigationParser(HTMLParser):
    """Validate component boundaries, not merely balanced HTML tags."""

    def __init__(self):
        super().__init__()
        self.stack = []
        self.cards = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        style = dict(attrs).get("style", "")
        if self.current is None:
            if tag != "div" or "border:2px solid #4f46e5" not in style:
                return
            self.current = []
            self.stack = ["div"]
            return
        require(tag in {"div", "span"} and len(self.stack) == 1,
                "navigation card contains nested content/image/markup")
        self.current.append({"tag": tag, "style": style, "text": ""})
        self.stack.append(tag)

    def handle_data(self, data):
        if self.current is None:
            return
        if len(self.stack) == 1:
            require(not data.strip(), "navigation card contains body text")
        else:
            self.current[-1]["text"] += data

    def handle_endtag(self, tag):
        if self.current is None:
            return
        require(self.stack and self.stack.pop() == tag,
                "navigation card has mismatched closing tag")
        if not self.stack:
            self.cards.append(self.current)
            self.current = None


def check_navigation(doc, filename):
    # Ignore displayed code: it may itself contain HTML examples.
    prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", doc, flags=re.M | re.S)
    parser = NavigationParser()
    parser.feed(prose)
    require(parser.current is None, f"{filename}: unclosed navigation card")
    require(len(parser.cards) == len(re.findall(r"位置：全章第", prose)),
            f"{filename}: metadata outside navigation component")
    for card in parser.cards:
        require(len(card) >= 3 and [x["tag"] for x in card[:2]] == ["div", "div"]
                and all(x["tag"] == "span" for x in card[2:]),
                f"{filename}: navigation must be identity, location, sibling labels")
        group = card[0]["text"].removeprefix("导航卡 · ")
        knowledge = re.search(r"本步知识：(.*?)　位置：", card[1]["text"])
        active = [x["text"] for x in card[2:] if "background:#15803d" in x["style"]]
        require(knowledge is not None and len(active) == 1,
                f"{filename}: missing knowledge or unique active label")
        rows = re.findall(r"^\| " + re.escape(active[0]) + r" \| (.*?) \| (.*?) \|$",
                          prose, re.M)
        # Inline code/backticks are presentation, not different task meanings.
        clean = lambda text: re.sub(r"[`*]", "", text).strip()
        require(len(rows) == 1 and clean(rows[0][0]) == clean(group)
                and clean(rows[0][1]) == clean(knowledge[1]),
                f"{filename}: task map differs from navigation: {active[0]}")
        require(re.search(r"^#{2,4} " + re.escape(active[0]) + r"(?:：\S[^\n]*)?$", prose, re.M),
                f"{filename}: task heading differs from active label: {active[0]}")
    return len(parser.cards)


def check():
    chapters = sorted(DOCS.glob("[0-9][0-9]-*.md"))
    navigation_count = sum(check_navigation(p.read_text(), p.name) for p in chapters)
    print(f"PASS navigation: {len(chapters)} chapters, {navigation_count} cards; optional subtitles checked")
    total_cards = total_images = 0
    for filename, asset, shorts, entry, support in CHAPTERS:
        doc = (DOCS / filename).read_text(encoding="utf-8")
        # A div HTML block ends at a blank line in CommonMark. Without it,
        # a following fence can be swallowed as raw HTML despite balanced ```.
        for markdown_file in [DOCS / filename, *(DOCS / "assets" / asset).glob("*.md")]:
            markdown = markdown_file.read_text(encoding="utf-8")
            require(not re.search(r"</(?:div|span)>[ \t]*\n[ \t]*```",
                                  markdown),
                    f"{markdown_file.name}: blank line required between HTML card and code fence")
            for green in re.finditer(r'<div style="border-left:6px solid #15803d[^\n]*</div>', markdown):
                label = re.sub(r"<[^>]+>", "", green[0])
                require("需要运行" in label or label.startswith("命令(模拟) · "),
                    f"{markdown_file.name}: simulated green command requires inline simulation label")
        cards = list(re.finditer(
            r'<div style="border-left:6px solid #15803d[^\n]*需要运行[^\n]*</div>', doc
        ))
        positions = re.findall(r"位置：全章第 (\d+) / (\d+) 项", doc)
        require([int(n) for n, _ in positions] == list(range(1, len(positions) + 1)),
                f"{filename}: navigation order")
        require({int(total) for _, total in positions} == {len(positions)},
                f"{filename}: navigation totals")
        expected = [(DOCS / "assets" / asset / s).read_text(encoding="utf-8")
                    for s in shorts]
        entries = P4_STAGES if asset == "09-p4" else RTL_STAGES if asset == "10-verilator" else [entry]
        expected.extend(f"bash Documents/newDoc/assets/{asset}/{name}\n" for name in entries)
        require(len(cards) == len(expected), f"{filename}: green card count")
        for index, (card, source) in enumerate(zip(cards, expected)):
            tail = doc[card.end():cards[index + 1].start() if index + 1 < len(cards) else len(doc)]
            block = re.search(r'^```bash\n(.*?)^```\s*$', tail, re.M | re.S)
            require(block is not None, f"{filename}: card {index + 1} missing bash")
            require(not tail[:block.start()].strip(),
                    f"{filename}: text between green card and executable block")
            require(block[1] == source, f"{filename}: card {index + 1} source drift")
            require("跳板机" in card[0] and "预期" in card[0],
                    f"{filename}: card {index + 1} terminal/expected metadata")
            require("仅供展示 · 输出解读" in tail[block.end():],
                    f"{filename}: card {index + 1} output explanation")
            if index < len(shorts):
                require(len(source.splitlines()) <= 50, f"{filename}: short card too long")
                require("$0" not in source and "BASH_SOURCE" not in source,
                        f"{filename}: inline card depends on script filename")
            subprocess.run(["bash", "-n"], input=block[1], text=True, check=True)
        for script in entries + ["live-support/" + support] + (["live-support/stage-actions.sh"] if asset == "09-p4" else []):
            subprocess.run(["bash", "-n", str(DOCS / "assets" / asset / script)], check=True)
        support_lines = len((DOCS / "assets" / asset / "live-support" / support).read_text().splitlines())
        disclosure = doc
        if asset in {"09-p4", "10-verilator"}:
            disclosure += (DOCS / "assets" / asset / "TEACHER-LIVE-NOTES.md").read_text()
        require(f"{support_lines} 行" in disclosure and support in disclosure,
                f"{filename}: long workflow disclosure drift")
        for tag in ["div", "span"]:
            require(len(re.findall(fr"<{tag}\b", doc)) == doc.count(f"</{tag}>"),
                    f"{filename}: unbalanced {tag}")
        require(len(re.findall(r"^```", doc, re.M)) % 2 == 0,
                f"{filename}: unbalanced fences")
        images = re.findall(r'<img\b[^>]*src="([^"]+)"', doc)
        for relative in images:
            image = DOCS / relative
            require(image.is_file(), f"missing image: {relative}")
            if image.suffix == ".svg":
                ET.parse(image)
        total_cards += len(cards)
        total_images += len(images)
        simulated = sum(re.sub(r"<[^>]+>", "", green[0]).startswith("命令(模拟) · ")
                        for green in re.finditer(r'<div style="border-left:6px solid #15803d[^\n]*</div>', doc))
        print(f"PASS {filename}: {len(cards)} execution cards, {simulated} simulated command cards, {len(images)} images")
    print(f"PASS total: {total_cards} execution cards, {total_images} image references; no live execution")


if __name__ == "__main__":
    check()
