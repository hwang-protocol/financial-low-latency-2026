#!/usr/bin/env python3
"""Own one receiver-side XDP attachment; never detach another program.

The remote watchdog survives an SSH/jump-host interruption. It only unloads
this attachment; replay/session recovery remains the trading controller's job.
"""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
STATE = HERE / "attachment.json"


def link(interface):
    return json.loads(subprocess.check_output(
        ["ip", "-j", "-details", "link", "show", "dev", interface], text=True))[0]


def program_id(info):
    xdp = info.get("xdp", {})
    return xdp.get("prog", {}).get("id", xdp.get("prog_id", 0))


def detach():
    if not STATE.exists():
        return
    owned = json.loads(STATE.read_text())
    info = link(owned["interface"])
    current = program_id(info)
    if info["ifindex"] != owned["ifindex"] or current not in (0, owned["program_id"]):
        raise SystemExit("refusing to detach changed interface/program ownership")
    if current:
        subprocess.check_call(["ip", "link", "set", "dev", owned["interface"], "xdpdrv", "off"])
    STATE.unlink()
    print("owned_xdp=detached", flush=True)


def main():
    action = sys.argv[1]
    if action == "detach":
        detach()
    elif action == "dump":
        owned = json.loads(STATE.read_text())
        info = link(owned["interface"])
        if info["ifindex"] != owned["ifindex"] or program_id(info) != owned["program_id"]:
            raise SystemExit("attachment identity changed")
        program = json.loads(subprocess.check_output(
            ["bpftool", "-j", "prog", "show", "id", str(owned["program_id"])], text=True))
        if isinstance(program, list):
            program = program[0]
        maps = json.loads(subprocess.check_output(["bpftool", "-j", "map", "show"], text=True))
        selected = [m for m in maps if m["id"] in program["map_ids"] and m.get("name") == sys.argv[2]]
        if len(selected) != 1:
            raise SystemExit("missing or ambiguous owned map")
        subprocess.check_call(["bpftool", "-j", "map", "dump", "id", str(selected[0]["id"])])
    elif action == "watch":
        deadline = time.monotonic() + 180
        while STATE.exists() and time.monotonic() < deadline:
            time.sleep(1)
        if STATE.exists():
            detach()
            print("watchdog=expired; replay required if feed has GAP", flush=True)
    elif action == "attach":
        interface = sys.argv[2]
        info = link(interface)
        if STATE.exists() or program_id(info):
            raise SystemExit("refusing to replace an existing XDP attachment")
        subprocess.check_call(["ip", "link", "set", "dev", interface, "xdpdrv",
                               "obj", str(HERE / "flle_xdp_mold_itch.o"), "sec", "xdp"])
        try:
            info = link(interface)
            pid = program_id(info)
            if not pid:
                raise RuntimeError("native attach returned without a program ID")
            state = {"interface": interface, "ifindex": info["ifindex"], "program_id": pid}
            STATE.write_text(json.dumps(state) + "\n")
            with (HERE / "watchdog.log").open("a") as log:
                subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "watch"],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 start_new_session=True, close_fds=True)
            print(json.dumps(state), flush=True)
        except BaseException:
            # This process just attached the program; no other course run is
            # permitted by the outer lock. Close the attach/receipt failure gap.
            subprocess.run(["ip", "link", "set", "dev", interface, "xdpdrv", "off"], check=True)
            if STATE.exists():
                STATE.unlink()
            raise
    else:
        raise SystemExit("usage: xdp-session.py attach IFACE|detach|watch|dump MAP")


if __name__ == "__main__":
    main()
