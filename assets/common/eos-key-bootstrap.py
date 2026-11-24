#!/usr/bin/env python3
"""Install the FLLE course public key in EOS running-config, then verify it."""

import getpass
import pathlib
import re
import stat
import sys

import pexpect


HOST = "10.1.1.253"
USER = "admin"
COMMON = pathlib.Path(__file__).resolve().parent
KNOWN_HOSTS = COMMON / "ssh_known_hosts"
IDENTITY = pathlib.Path("/root/.ssh/flle_course_ed25519")
PUBLIC_KEY = pathlib.Path("/root/.ssh/flle_course_ed25519.pub")
PASSWORD_FILE = pathlib.Path("/root/.config/flle/eos_admin_password")
PROMPT = re.compile(rb"(?:^|\r?\n)[^\r\n]+([#>]) ?$")
PRIVILEGED = re.compile(rb"(?:^|\r?\n)[^\r\n]+# ?$")
CONFIG = re.compile(rb"(?:^|\r?\n)[^\r\n]+\(config\)# ?$")


def ssh_args(password_mode=False):
    args = [
        "-tt", "-o", "ConnectTimeout=8",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={KNOWN_HOSTS}",
    ]
    if password_mode:
        args += [
            "-o", "PubkeyAuthentication=no",
            "-o", "PreferredAuthentications=keyboard-interactive,password",
        ]
    else:
        args += [
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", f"IdentityFile={IDENTITY}",
        ]
    return args + [f"{USER}@{HOST}"]


def key_login_works():
    child = pexpect.spawn("/usr/bin/ssh", ssh_args(), encoding=None, timeout=15)
    child.setwinsize(2000, 240)
    try:
        child.expect(PROMPT)
        child.sendline(b"exit")
        child.close(force=True)
        return True
    except (pexpect.EOF, pexpect.TIMEOUT):
        child.close(force=True)
        return False


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
            "EOS_PASSWORD_REQUIRED: create the documented root-only credential file "
            "or rerun this preparation card in an interactive terminal"
        )
    return getpass.getpass("EOS admin password (not stored): ")


def install_running_key(password, public_key):
    child = pexpect.spawn(
        "/usr/bin/ssh", ssh_args(password_mode=True), encoding=None, timeout=30
    )
    child.setwinsize(2000, 240)
    state = child.expect([re.compile(rb"(?i)password:"), PROMPT])
    if state == 0:
        child.sendline(password.encode())
        child.expect(PROMPT)
    if child.match.group(1) == b">":
        child.sendline(b"enable")
        state = child.expect([PRIVILEGED, re.compile(rb"(?i)password:")])
        if state == 1:
            child.sendline(password.encode())
            child.expect(PRIVILEGED)
    child.sendline(b"configure terminal")
    child.expect(CONFIG)
    child.sendline(("username admin ssh-key " + public_key).encode("ascii"))
    child.expect(CONFIG)
    response = child.before.replace(b"\r", b"").decode("utf-8", "replace")
    if any(marker in response for marker in ("% Invalid input", "% Authorization failed", "% Error")):
        raise RuntimeError("EOS rejected the fixed public-key command")
    child.sendline(b"end")
    child.expect(PRIVILEGED)
    child.sendline(b"exit")
    child.close(force=True)


def main():
    for path in (KNOWN_HOSTS, IDENTITY, PUBLIC_KEY):
        if not path.is_file():
            raise SystemExit(f"EOS_BOOTSTRAP_MISSING_FILE path={path}")
    if key_login_works():
        print("PASS_EOS_PUBLIC_KEY_ALREADY_READY host=10.1.1.253 config=running-only")
        return 0
    password = load_password()
    public_key = PUBLIC_KEY.read_text(encoding="ascii").strip()
    try:
        install_running_key(password, public_key)
    finally:
        password = ""
    if not key_login_works():
        raise SystemExit("EOS_PUBLIC_KEY_VERIFY_FAILED")
    print("PASS_EOS_PUBLIC_KEY_BOOTSTRAP host=10.1.1.253 config=running-only startup=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
