#!/usr/bin/env python3
"""把 policy map 写成 allow 或 block。"""

import json
import struct
import subprocess
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "allow"
remaining = int(sys.argv[2]) if len(sys.argv) > 2 else 1
ttl_seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
if mode not in {"allow", "block"}:
    raise SystemExit("mode must be allow or block")
if mode == "block" and remaining != 1:
    raise SystemExit("classroom policy is one-shot: remaining must be 1")
if ttl_seconds <= 0 or ttl_seconds > 30:
    raise SystemExit("ttl must be in (0, 30] seconds")
maps = json.loads(subprocess.check_output(["bpftool", "-j", "map", "show"], text=True))
if len(sys.argv) > 4:
    program = json.loads(subprocess.check_output(
        ["bpftool", "-j", "prog", "show", "id", sys.argv[4]], text=True))
    if isinstance(program, list):
        program = program[0]
    maps = [item for item in maps if item["id"] in program["map_ids"]]
for name in ("policy", "drop_audit"):
    if sum(item.get("name") == name for item in maps) != 1:
        raise SystemExit(f"ambiguous or missing map: {name}; specify the attached program ID")
policy = next(item for item in maps if item.get("name") == "policy")
deadline_ns = time.monotonic_ns() + int(ttl_seconds * 1_000_000_000) if mode == "block" else 0
value = struct.pack(
    "<IIQQ",
    1 if mode == "block" else 0,
    8095,
    remaining if mode == "block" else 0,
    deadline_ns,
)
command = [
    "bpftool",
    "map",
    "update",
    "id",
    str(policy["id"]),
    "key",
    "hex",
    "00",
    "00",
    "00",
    "00",
    "value",
    "hex",
    *[f"{byte:02x}" for byte in value],
]
audit = next(item for item in maps if item.get("name") == "drop_audit")
if mode == "block":
    # 先清审计，再武装策略；反过来会让高包速率下的首个命中被随后清零。
    subprocess.check_call([
        "bpftool", "map", "update", "id", str(audit["id"]),
        "key", "hex", "00", "00", "00", "00",
        "value", "hex", *(["00"] * 16),
    ])
subprocess.check_call(command)
print(
    f"policy_id={policy['id']} mode={mode} "
    f"remaining={remaining if mode == 'block' else 0} "
    f"ttl_seconds={ttl_seconds if mode == 'block' else 0}"
)
