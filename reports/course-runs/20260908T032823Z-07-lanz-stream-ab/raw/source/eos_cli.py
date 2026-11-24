#!/usr/bin/env python3
"""Run an allow-listed EOS command plan over public-key SSH without saving config."""

import argparse
import getpass
import os
import pathlib
import re
import stat
import sys

import pexpect


PROMPT = re.compile(rb"(?:^|\r?\n)[^\r\n]+([#>]) ?$")
PRIVILEGED = re.compile(rb"(?:^|\r?\n)[^\r\n]+# ?$")
FORBIDDEN = re.compile(
    r"(?i)(write\s+memory|copy\s+.*startup|reload|install|boot\s+system|delete\s+)"
)
ALLOWED_CONFIG = re.compile(
    r"(?i)^(configure terminal|end|vlan (?:20|100|200|3101|3102)|no vlan (?:100|200|3101|3102)|"
    r"name (?:fll|FLLE_P4_(?:LEFT|RIGHT)(?:_20260820)?|FLLE_TS_SINK_20260903)|"
    r"interface Ethernet(?:1|2|11|12)|interface Vlan20|"
    r"queue-monitor length|default queue-monitor length|"
    r"queue-monitor length thresholds 64 32|default queue-monitor length thresholds|"
    r"queue-monitor streaming|default queue-monitor streaming|no queue-monitor streaming|"
    r"qos trust dscp|default qos trust|tx-queue (?:[0-3]|5)|"
    r"priority strict|no priority|default priority|bandwidth percent (?:10|20|30|40)|"
    r"default bandwidth percent|exit|"
    r"(?:no )?mac address-table static 0200\.0007\.0001 vlan 20 interface Ethernet1|"
    r"(?:no )?mac address-table static 0200\.0007\.0002 vlan 20 interface Ethernet2|"
    r"switchport mode access|switchport access vlan (?:20|21|100|200|3101|3102)|spanning-tree portfast|"
    r"ip address 20\.1\.1\.254/24|no ip routing|default switchport access vlan|"
    r"ptp mode e2etransparent|ptp mode boundary|default ptp mode|ptp enable|default ptp enable|"
    r"mac timestamp before-fcs|no mac timestamp|"
    r"monitor session FLLETS source Ethernet1 rx|"
    r"monitor session FLLETS destination Ethernet11|"
    r"no monitor session FLLETS|"
    r"monitor session FLLEXDP source Ethernet1 rx|"
    r"monitor session FLLEXDP destination Ethernet11|"
    r"no monitor session FLLEXDP|"
    r"(?:no |default )ip igmp snooping vlan (?:100|200)|"
    r"platform fm6000 keyframe FLLETS interface Ethernet11 21\.1\.1\.11 000a\.f7f8\.48a0|"
    r"platform fm6000 keyframe FLLETS source ip 20\.1\.1\.254|"
    r"platform fm6000 keyframe FLLETS fields skew|"
    r"no platform fm6000 keyframe FLLETS)$"
)
STREAMING_ONLY = re.compile(r"(?i)^(no shutdown|shutdown)$")


PASSWORD_FILE = pathlib.Path("/root/.config/flle/eos_admin_password")


def load_password():
    if PASSWORD_FILE.is_file():
        metadata = PASSWORD_FILE.stat()
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise SystemExit(
                f"EOS_PASSWORD_FILE_UNSAFE path={PASSWORD_FILE} expected=root:root,0600"
            )
        return PASSWORD_FILE.read_text(encoding="utf-8").rstrip("\r\n")
    if not sys.stdin.isatty():
        raise SystemExit(
            "EOS_AUTH_REQUIRED: create the documented root-only credential file "
            "or rerun from an interactive terminal"
        )
    return getpass.getpass("EOS admin password (not stored): ")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="one EOS command per line")
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("show", "controlled-config"), required=True)
    return parser.parse_args()


def load_plan(path, mode):
    commands = []
    streaming_ctx = False
    for number, raw in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        command = raw.strip()
        if not command or command.startswith("#"):
            continue
        if FORBIDDEN.search(command):
            raise SystemExit(f"forbidden EOS command at line {number}: {command}")
        if mode == "show" and not re.fullmatch(r"show(?: [^;\r\n]*)?", command):
            raise SystemExit(f"show-only plan rejected line {number}: {command}")
        if mode == "controlled-config":
            allowed = ALLOWED_CONFIG.fullmatch(command) or re.fullmatch(
                r"show(?: [^;\r\n]*)?", command
            )
            if STREAMING_ONLY.fullmatch(command):
                allowed = streaming_ctx
            if not allowed:
                raise SystemExit(f"config allow-list rejected line {number}: {command}")
            lowered = command.lower()
            if lowered == "queue-monitor streaming":
                streaming_ctx = True
            elif lowered in ("end", "exit"):
                streaming_ctx = False
        commands.append(command)
    if not commands:
        raise SystemExit("empty EOS plan")
    return commands


def main():
    args = parse_args()
    commands = load_plan(args.plan, args.mode)
    common_dir = pathlib.Path(__file__).resolve().parent
    known_hosts = common_dir / "ssh_known_hosts"
    identity_file = pathlib.Path(
        os.environ.get("FLLE_IDENTITY_FILE", "/root/.ssh/flle_course_ed25519")
    )
    key_args = [
        "-tt", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "-o", "IdentitiesOnly=yes", "-o", f"IdentityFile={identity_file}",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}", "admin@10.1.1.253",
    ]
    child = pexpect.spawn("/usr/bin/ssh", key_args, encoding=None, timeout=45)
    child.setwinsize(2000, 240)
    password = None
    try:
        child.expect(PROMPT)
    except pexpect.EOF:
        failure = child.before.decode("utf-8", "replace")
        child.close(force=True)
        if "Permission denied" not in failure:
            raise SystemExit("EOS_AUTH_REQUIRED: public key failed; rerun from an interactive terminal")
        password = load_password()
        password_args = [
            "-tt", "-o", "PubkeyAuthentication=no", "-o", "ConnectTimeout=8",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts}",
            "-o", "PreferredAuthentications=keyboard-interactive,password",
            "admin@10.1.1.253",
        ]
        child = pexpect.spawn("/usr/bin/ssh", password_args, encoding=None, timeout=45)
        child.setwinsize(2000, 240)
        login_state = child.expect([re.compile(rb"(?i)password:"), PROMPT])
        if login_state == 0:
            child.sendline(password.encode("utf-8"))
            child.expect(PROMPT)
    if child.match.group(1) == b">":
        child.sendline(b"enable")
        enable_state = child.expect([PRIVILEGED, re.compile(rb"(?i)password:")])
        if enable_state == 1:
            if password is None:
                password = load_password()
            child.sendline(password.encode("utf-8"))
            child.expect(PRIVILEGED)

    transcript = []
    child.sendline(b"terminal length 0")
    child.expect(PRIVILEGED)
    for command in commands:
        wire = command if not command.startswith("show ") else command + " | no-more"
        child.sendline(wire.encode("ascii"))
        child.expect(PRIVILEGED)
        output = child.before.replace(b"\r", b"").decode("utf-8", "replace")
        transcript.append(f"$ {command}\n{output}\n")
        if "% Invalid input" in output or "% Authorization failed" in output:
            raise RuntimeError(f"EOS rejected command: {command}")

    child.sendline(b"exit")
    child.close(force=True)
    rendered = "\n".join(transcript)
    pathlib.Path(args.output).write_text(rendered)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
