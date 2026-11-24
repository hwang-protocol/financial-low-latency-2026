#!/usr/bin/env python3
"""Sequential classroom green-card replay. Does not write Git history."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path("/financial-low-latency")
STATE = ROOT / "Documents/reports/run-state/full-course-replay.json"
PAUSE_LABEL_MARKERS = (
    "②-1",
    "②-2",
    "②-3",
    "需要运行 · 运行 ① 教师在跳板机执行；前置为准备 A 完成、行情交易系统正常",
    "需要运行 · 运行 ② 教师在跳板机执行；前置为运行①成功且过滤进程仍在运行",
    "需要运行 · 运行 ③ 教师在跳板机执行；前置为运行②成功、缺口现场仍保留",
)
PAUSE_SECONDS = 120


def now():
    return datetime.now(timezone.utc).isoformat()


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    STATE.write_text(text)
    (ROOT / state["OUT"] / "session.json").write_text(text)


def extract_cards(doc_text, filename):
    cards = []
    matches = list(
        re.finditer(r'<div style="border-left:6px solid (#[a-fA-F0-9]+);[^\n]*</div>', doc_text)
    )
    seq = 0
    for index, card in enumerate(matches):
        if card.group(1).lower() != "#15803d":
            continue
        label = re.sub(r"<[^>]+>", "", card.group())
        if "模拟" in label or "需要运行" not in label:
            continue
        seq += 1
        end = matches[index + 1].start() if index + 1 < len(matches) else len(doc_text)
        segment = doc_text[card.end() : end]
        fences = list(
            re.finditer(
                r"^(?P<fence>```|~~~)bash\n(?P<code>.*?)^(?P=fence)\s*$",
                segment,
                re.M | re.S,
            )
        )
        for fence_index, block in enumerate(fences, 1):
            code = block.group("code")
            cid = f"{filename[:2]}-{seq:02}-{fence_index}"
            cards.append(
                {
                    "id": cid,
                    "chapter": filename[:2],
                    "source": f"Documents/newDoc/{filename}",
                    "line": doc_text.count("\n", 0, card.start()) + 1,
                    "label": label,
                    "sha256": hashlib.sha256(code.encode()).hexdigest(),
                    "status": "PENDING",
                    "attempts": [],
                }
            )
    return cards


def cmd_init():
    rid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-00-10-green-replay"
    out = ROOT / "Documents/reports/course-runs" / rid
    for name in ["cards", "raw", "source-before"]:
        (out / name).mkdir(parents=True, exist_ok=True)
    cards = []
    for path in sorted((ROOT / "Documents/newDoc").glob("[0-9][0-9]-*.md")):
        text = path.read_text()
        (out / "source-before" / path.name).write_text(text)
        extracted = extract_cards(text, path.name)
        for card in extracted:
            (out / "cards" / f"{card['id']}.sh").write_text(
                Path(ROOT / card["source"]).read_text()  # placeholder overwritten below
            )
        # write actual bash from extraction
        # re-extract codes
        matches = list(
            re.finditer(r'<div style="border-left:6px solid (#[a-fA-F0-9]+);[^\n]*</div>', text)
        )
        seq = 0
        written = []
        for index, card in enumerate(matches):
            if card.group(1).lower() != "#15803d":
                continue
            label = re.sub(r"<[^>]+>", "", card.group())
            if "模拟" in label or "需要运行" not in label:
                continue
            seq += 1
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            segment = text[card.end() : end]
            for fence_index, block in enumerate(
                re.finditer(
                    r"^(?P<fence>```|~~~)bash\n(?P<code>.*?)^(?P=fence)\s*$",
                    segment,
                    re.M | re.S,
                ),
                1,
            ):
                cid = f"{path.name[:2]}-{seq:02}-{fence_index}"
                (out / "cards" / f"{cid}.sh").write_text(block.group("code"))
                written.append(cid)
        cards.extend(extracted)
        assert [c["id"] for c in extracted] == written, path.name
    state = {
        "RUN_ID": rid,
        "OUT": str(out.relative_to(ROOT)),
        "STATUS": "RUNNING",
        "STARTED": now(),
        "AUTHORIZATION": (
            "DEC-388: user required ch07 QoS/LANZ/PTP/final as green cards; "
            "skip ch04 Grafana browser; skip ch10 simulated commands; "
            "no git history operations."
        ),
        "SKIP": ["04-run-③-browser-user-self", "10-命令(模拟)"],
        "CARDS": cards,
        "BROWSER_CHECKS": [],
        "FIXES": [],
    }
    save(state)
    paths = sorted(
        set(
            [
                *ROOT.glob("Documents/newDoc/[0-9][0-9]-*.md"),
                *ROOT.glob("Documents/newDoc/assets/**/*.sh"),
                *ROOT.glob("Documents/newDoc/assets/**/*.py"),
                *ROOT.glob("apps/flle-trading-lab/scripts/*"),
                *ROOT.glob("apps/flle-trading-lab/src/**/*"),
            ]
        )
    )
    (out / "source-before/SHA256SUMS").write_text(
        "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + str(p.relative_to(ROOT)) + "\n"
            for p in paths
            if p.is_file()
        )
    )
    print(rid, len(cards), "Bash cards")
    for card in cards:
        print(card["id"], card["label"][:72])


def load_state():
    return json.loads(STATE.read_text())


def run_one(state, cid, auto_review=True):
    out = ROOT / state["OUT"]
    card = next(c for c in state["CARDS"] if c["id"] == cid)
    code = out / "cards" / f"{cid}.sh"
    attempt = {
        "started": now(),
        "sha256": hashlib.sha256(code.read_bytes()).hexdigest(),
        "log": f"raw/{cid}-attempt-{len(card['attempts']) + 1}.txt",
    }
    card["attempts"].append(attempt)
    card["status"] = "RUNNING"
    state["CURRENT_CARD"] = cid
    save(state)
    print("START", cid, card["label"][:80], flush=True)
    before = set((ROOT / "Documents/reports/course-runs").iterdir())
    start = time.monotonic()
    with (out / attempt["log"]).open("w") as log:
        proc = subprocess.Popen(
            ["bash", str(code)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
        )
        attempt["pid"] = proc.pid
        save(state)
        rc = proc.wait()
    attempt.update(
        ended=now(),
        exit=rc,
        seconds=round(time.monotonic() - start, 2),
        created_runs=sorted(
            p.name
            for p in set((ROOT / "Documents/reports/course-runs").iterdir()) - before
        ),
    )
    if rc == 0:
        if auto_review:
            card["status"] = "PASS"
            card["reviewed_at"] = now()
            card["evidence_paths"] = re.findall(
                r"^evidence=(.+)$",
                (out / attempt["log"]).read_text(errors="replace"),
                re.M,
            )
        else:
            card["status"] = "COMMAND_PASS_PENDING_REVIEW"
    else:
        card["status"] = "FAILED"
        state["STATUS"] = "FAILED"
    save(state)
    tail = "\n".join((out / attempt["log"]).read_text(errors="replace").splitlines()[-16:])
    print("END", cid, "exit", rc, "seconds", attempt["seconds"], "new_runs", attempt["created_runs"], flush=True)
    print(tail, flush=True)
    if rc:
        sys.exit(rc)
    return state


def cmd_run(cids):
    state = load_state()
    for cid in cids:
        run_one(state, cid, auto_review=False)


def cmd_run_all():
    state = load_state()
    pending = [c for c in state["CARDS"] if c["status"] in {"PENDING", "FAILED"}]
    # resume PENDING only; do not auto-retry FAILED unless asked
    pending = [c for c in state["CARDS"] if c["status"] == "PENDING"]
    for card in pending:
        run_one(state, card["id"])
        if any(marker in card["label"] for marker in PAUSE_LABEL_MARKERS):
            print(f"CLASSROOM PAUSE {PAUSE_SECONDS}s after {card['id']}", flush=True)
            time.sleep(PAUSE_SECONDS)
    state = load_state()
    failed = [c["id"] for c in state["CARDS"] if c["status"] == "FAILED"]
    if failed:
        state["STATUS"] = "FAILED"
    elif all(c["status"] == "PASS" for c in state["CARDS"]):
        state["STATUS"] = "PASS"
        state["ENDED"] = now()
    save(state)
    print("ALL_DONE", state["STATUS"], flush=True)


def cmd_status():
    state = load_state()
    print(state["RUN_ID"], state["STATUS"])
    for card in state["CARDS"]:
        print(card["id"], card["status"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "init":
        cmd_init()
    elif cmd == "run":
        cmd_run(sys.argv[2:])
    elif cmd == "run-all":
        cmd_run_all()
    elif cmd == "status":
        cmd_status()
    else:
        raise SystemExit(f"unknown command {cmd}")
