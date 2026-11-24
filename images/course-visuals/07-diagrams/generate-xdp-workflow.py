#!/usr/bin/env python3
"""Generate the same source/build/load diagram with each current step highlighted."""
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    (2, 110, 154, "查看 C 源码", "任务：阅读过滤条件；输入是 flle_xdp_mold_itch.c。", [
        "nl -ba flle_xdp_mold_itch.c",
    ], [236]),
    (3, 320, 280, "编译并检查 BPF 对象", "任务：Clang 把 .c 编成 .o，再用 LLVM 工具检查 .o。", [
        "clang -O2 -g -target bpf \\",
        "  -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu \\",
        "  -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o",
        "llvm-objdump -h flle_xdp_mold_itch.o",
    ], [450, 483, 516, 567]),
    (4, 656, 238, "装载到内核，挂到网卡入口", "任务：装载 BPF 对象，经 Verifier 检查后挂到 ens64np1。", [
        "ip link set dev ens64np1 xdpdrv \\",
        "  obj flle_xdp_mold_itch.o sec xdp",
        "ip -details link show dev ens64np1",
    ], [785, 818, 867]),
]
NUMERALS = {2: "②", 3: "③", 4: "④"}


def generate(active):
    out = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="966" viewBox="0 0 1200 966" role="img" aria-labelledby="title desc">
<title id="title">从 C 源码到 XDP 程序：当前运行{NUMERALS[active]}</title>
<desc id="desc">三张任务卡依次为查看源码、编译检查、装载挂载；每张卡下列出核心命令，绿色卡表示当前步骤。运行④会重新编译当前源码，然后装载本次对象。</desc>
<defs><marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" viewBox="0 0 12 12" refX="0" refY="6" orient="auto"><path d="M0 0 L12 6 L0 12 Z" fill="#64748b"/></marker></defs>
<style>
text {{font-family:'Noto Sans CJK SC',sans-serif;fill:#1e293b}}
.title {{font-size:32px;font-weight:700}}
.subtitle {{font-size:23px;fill:#475569}}
.heading {{font-size:28px;font-weight:700}}
.task {{font-size:24px;fill:#475569}}
.command {{font-family:'Noto Sans Mono CJK SC','Noto Sans CJK SC',monospace;font-size:25px;white-space:pre;fill:#1e293b}}
.badge {{font-size:21px;font-weight:700;fill:#fff}}
</style>
<rect width="1200" height="966" rx="20" fill="#fff"/>
<text x="36" y="47" class="title">C 源码 → BPF 对象 → 内核中的 XDP 程序</text>
<text x="36" y="82" class="subtitle">命令按源码所在目录书写 · 绿色为当前步骤，实际执行正文绿色入口。</text>''']
    for step, top, height, title, task, commands, ys in STEPS:
        current = step == active
        fill, border = ("#ecfdf5", "#16a34a") if current else ("#f8fafc", "#cbd5e1")
        label = "#166534" if current else "#475569"
        code_top = ys[0] - 34
        code_bottom = ys[-1] + 18
        out += [f'<g id="step-{step}" data-current="{str(current).lower()}">',
                f'<rect x="36" y="{top}" width="1128" height="{height}" rx="16" fill="{fill}" stroke="{border}" stroke-width="2"/>',
                f'<text x="62" y="{top+43}" class="heading" style="fill:{label}">运行{NUMERALS[step]} · {escape(title)}</text>',
                f'<text x="62" y="{top+79}" class="task">{escape(task)}</text>',
                f'<rect x="60" y="{code_top}" width="1080" height="{code_bottom-code_top}" rx="10" fill="#fff" stroke="#e2e8f0"/>']
        if current:
            out += [f'<rect x="1026" y="{top+18}" width="112" height="34" rx="17" fill="#15803d"/>',
                    f'<text x="1082" y="{top+43}" text-anchor="middle" class="badge">当前步骤</text>']
        out += [f'<text x="80" y="{y}" xml:space="preserve" class="command">{escape(command)}</text>' for command, y in zip(commands, ys)]
        out.append('</g>')
    # Arrow tips end 12 px before the next card; marker reference is its tail.
    for start, end in ((276, 296), (612, 632)):
        out.append(f'<path d="M600 {start} V{end}" fill="none" stroke="#64748b" stroke-width="2.5" stroke-linecap="butt" marker-end="url(#arrow)"/>')
    out += ['<text x="36" y="934" class="subtitle">运行④先重新编译当前源码，再装载本次 .o；挂载后才开始处理报文。</text>', '</svg>']
    return '\n'.join(out) + '\n'


if __name__ == "__main__":
    for active in (2, 3, 4):
        (HERE / f"07-xdp-workflow-{active}.svg").write_text(generate(active), encoding="utf-8")
