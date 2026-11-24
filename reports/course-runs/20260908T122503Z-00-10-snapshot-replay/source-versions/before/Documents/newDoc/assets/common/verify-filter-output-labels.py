#!/usr/bin/env python3
"""Exercise Ch08-10 printf arguments locally; never execute a course card or SSH."""
from pathlib import Path
import importlib.util
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cards", HERE / "verify-filter-course-cards.py")
cards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cards)


def headers(code):
    lexer = shlex.shlex(code, posix=True, punctuation_chars=";|&<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    for i, token in enumerate(tokens[:-1]):
        if token != "printf" or tokens[i + 1] != "%s\\n":
            continue
        end = i + 2
        while end < len(tokens) and tokens[end] not in {";", "|", ">", ">>", "&&", "||"}:
            end += 1
        args = tokens[i + 2:end]
        if not any("===== 查" in value for value in args):
            continue
        assert any(" 对: " in value and "  证: " in value for value in args), args
        assert any(value.startswith("$ ") for value in args) or any(
            name in " ".join(args) for name in ("源码指纹", "带行号", "安装编译")
        ), args
        # Passing argv avoids executing the literal $ commands or substitutions.
        output = subprocess.run(["printf", "%s\n", *args], check=True,
                                capture_output=True, text=True).stdout
        assert "\\n" not in output, output
        assert "===== 查" in output and "  证: " in output, output
        yield output


def check():
    paths = [HERE / "check-filter-handoff.sh"]
    for _, asset, shorts, _, support in cards.CHAPTERS:
        paths += [HERE.parent / asset / name for name in shorts]
        paths.append(HERE.parent / asset / "live-support" / support)
    count = 0
    delegated = 0
    for path in paths:
        source = path.read_text()
        subprocess.run(["bash", "-n", str(path)], check=True)
        if path.name == "stage-actions.sh" and path.parent.parent.name == "10-verilator":
            assert 'stage-output.py' in source, "missing delegated stage renderer"
            spec = importlib.util.spec_from_file_location("rtl_output", path.with_name("stage-output.py"))
            renderer = importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
            assert set(renderer.HEADERS) == {"prepare", "arm", "verify", "restore"}
            for action, lines in renderer.HEADERS.items():
                output = renderer.heading(action)
                assert any("===== 查" in line for line in lines)
                assert any(" 对: " in line and "  证: " in line for line in lines)
                assert any(line.startswith("$ ") for line in lines)
                assert output == "\n".join(lines)+"\n" and "\\n" not in output
                delegated += 1
            continue
        found = 0
        for line in source.splitlines():
            if "===== 查" not in line or "printf" not in line:
                continue
            if line.startswith("ssh -n ") and "set -Eeuo pipefail;" in line:
                tokens = shlex.split(line)
                host = next(i for i, token in enumerate(tokens) if token.startswith("root@"))
                # shlex retains \$ inside double quotes; bash removes that escape
                # while constructing the argument passed to SSH.
                line = tokens[host + 1].replace("\\$", "$")
                subprocess.run(["bash", "-n"], input=line, text=True, check=True)
            found += len(list(headers(line.rstrip().removesuffix("\\"))))
        if path.name == "01-xdp-hook-readiness.sh":
            assert "check-filter-handoff.sh" in source
        else:
            assert found, f"Missing output labels: {path}"
        count += found
    print(f"PASS {len(paths)} scripts: {count} printf blocks + {delegated} data-renderer headers checked locally; no SSH/live")


if __name__ == "__main__":
    check()
