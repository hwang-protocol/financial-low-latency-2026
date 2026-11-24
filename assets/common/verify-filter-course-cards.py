#!/usr/bin/env python3
"""Read-only current 00–08 structure and XDP executable-card checks.

The former checker described retired P4/Verilator chapters and an older task
map layout. Chapter 08 now teaches a Windows GUI workflow. Never execute cards.
"""
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT
# Also consumed by verify-filter-output-labels.py.
CHAPTERS = [
    ("07-ebpf-xdp-programmable-network.md", "07-xdp", [
        "00-xdp-toolchain-prep.sh", "01-xdp-hook-readiness.sh",
        "03-xdp-parser-bounds.sh", "04-xdp-build.sh",
    ], "05-xdp-inline-live.sh", "run-xdp-receiver-live.sh"),
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check():
    chapters = sorted(DOCS.glob("[0-9][0-9]-*.md"))
    require([p.name[:2] for p in chapters] == [f"{n:02d}" for n in range(9)],
            "expected chapters 00–08")
    image_count = bash_count = 0
    for chapter in chapters:
        doc = chapter.read_text()
        prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", doc, flags=re.M | re.S)
        for tag in ("div", "span"):
            require(len(re.findall(fr"<{tag}\b", prose)) == prose.count(f"</{tag}>"),
                    f"{chapter.name}: unbalanced {tag}")
        require(len(re.findall(r"^```", doc, re.M)) % 2 == 0,
                f"{chapter.name}: unbalanced fences")
        require(not re.search(r"</(?:div|span)>[ \t]*\n[ \t]*```", doc),
                f"{chapter.name}: blank line required before code fence")
        for code in re.findall(
                r'<div style="border-left:6px solid #15803d[^\n]*需要运行[^\n]*</div>\s*\n```bash\n(.*?)^```\s*$',
                doc, re.M | re.S):
            subprocess.run(["bash", "-n"], input=code, text=True, check=True)
            bash_count += 1
        positions = re.findall(r"(?:位置|进度)：全章第 (\d+) / (\d+) 项", prose)
        if positions:
            require([int(n) for n, _ in positions] == list(range(1, len(positions) + 1))
                    and {int(total) for _, total in positions} == {len(positions)},
                    f"{chapter.name}: navigation order/totals")
        for relative in re.findall(r'<img\b[^>]*src="([^"]+)"', prose):
            image = DOCS / relative
            require(image.is_file(), f"missing image: {relative}")
            if image.suffix == ".svg":
                ET.parse(image)
            image_count += 1
    for filename, asset, shorts, entry, support in CHAPTERS:
        doc = (DOCS / filename).read_text()
        cards = list(re.finditer(
            r'<div style="border-left:6px solid #15803d[^\n]*需要运行[^\n]*</div>', doc))
        expected = [f"bash assets/{asset}/{name}\n" for name in [*shorts, entry]]
        require(len(cards) == len(expected) + 1, f"{filename}: command + GUI card count")
        require("交易网页" in cards[-1][0] and "重新开始并清空交易" in cards[-1][0],
                f"{filename}: missing manual recovery card")
        for index, (card, source) in enumerate(zip(cards, expected)):
            end = cards[index + 1].start() if index + 1 < len(cards) else len(doc)
            tail = doc[card.end():end]
            block = re.search(r'^```bash\n(.*?)^```\s*$', tail, re.M | re.S)
            require(block is not None and not tail[:block.start()].strip(),
                    f"{filename}: card {index + 1} missing adjacent bash")
            script = DOCS / "assets" / asset / [*shorts, entry][index]
            require(block[1] in (source, script.read_text()),
                    f"{filename}: card {index + 1} source drift")
        for name in [*shorts, entry, "live-support/" + support]:
            subprocess.run(["bash", "-n", str(DOCS / "assets" / asset / name)], check=True)
    print(f"PASS {len(chapters)} chapters, {image_count} images, {bash_count} bash blocks; "
          "XDP cards match scripts; no live execution")


if __name__ == "__main__":
    check()
