#!/usr/bin/env python3
"""Offline contract audit for the Guest-IOMMU two-host transaction card."""

from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "assets/02-trading-baseline/00b-iommu-prep.sh"
CHAPTER = next((ROOT / "").glob("02-*.md"))


def require_order(text: str, *needles: str) -> None:
    positions = [text.index(needle) for needle in needles]
    assert positions == sorted(positions), tuple(zip(needles, positions))


script = ASSET.read_text()
chapter = CHAPTER.read_text()
subprocess.run(["bash", "-n", str(ASSET)], check=True)
assert len(script.splitlines()) <= 60
assert "remote(){ ssh -n " not in script  # heredoc must reach remote bash stdin

remote_start = script.index("<<'REMOTE'\n") + len("<<'REMOTE'\n")
remote_end = script.index("\nREMOTE\n", remote_start)
remote_script = script[remote_start:remote_end] + "\n"
subprocess.run(["bash", "-n"], input=remote_script, text=True, check=True)

assert "bash assets/02-trading-baseline/00b-iommu-prep.sh" in chapter

# Phase one is read-only on both hosts; phase two starts only after that loop ends.
require_order(
    script,
    'for host in "${HOSTS[@]}"; do\n  if remote "$host" probe',
    'test "$preflight_failed" -eq 0',
    "touched=()",
    'remote "$host" apply',
    'remote "$host" reboot',
    'remote "$host" verify',
    'remote "$host" commit',
)
probe = script[script.index("  probe)") : script.index("  apply)")]
assert "state; raw; valid" in probe
assert not any(word in probe for word in ("install -m", "sed -i", "update-grub"))
assert "preflight_failed=1" in script
assert "/proc/sys/kernel/random/boot_id" in script
assert 'test "$current" != "${boot[$host]}"' in script

# Raw state precedes assertions; both the configured and already-live cases are accepted.
for field in (
    "$ hostname",
    "^GRUB_CMDLINE_LINUX=",
    "flle-ch02-grub.*",
    "$ cat /proc/cmdline",
    "/sys/bus/pci/devices/0000:03:00.0/iommu_group",
    '"$group/devices"',
    "[配置说明]",
    "[生效检查]",
    "[设备检查]",
    "===== 查主机名 =====",
    "===== 查下次启动参数 =====",
    "===== 查本轮备份 =====",
    "===== 查当前启动参数 =====",
    "===== 查隔离组 =====",
    "===== 核对分组内设备 =====",
):
    assert field in script
assert "===== %s / %s =====" not in script
assert "===== 准备结果 =====" in script
assert 'tee "$OUT/raw/result.txt"' in script
assert "state; raw; valid" in script[script.index("  verify)") : script.index("  commit)")]
assert "intel_iommu=on" in script and "iommu=pt" in script
assert 'test "${group##*/}" = 7' in script
assert 'test "$devices" = 0000:03:00.0' in script
assert 'for host in "${touched[@]}"; do remote "$host" verify' in script
assert 'for host in "${HOSTS[@]}"; do remote "$host" verify' not in script
assert 'for host in "${HOSTS[@]}"; do remote "$host" vfio' in script
assert "enable_unsafe_noiommu_mode" in script
assert "[模式检查] N" in script

# Every mutation has a run-scoped backup; apply failure rolls back all touched hosts.
assert 'backup="/var/backups/flle-ch02-grub.$run"' in script
require_order(script, 'test ! -e "$backup"', 'install -m 600 "$file" "$backup"')
assert 'for item in "${touched[@]}"; do remote "$item" rollback' in script
rollback = script[script.index("  rollback)") : script.index("  reboot)")]
require_order(rollback, 'install -m 644 "$backup" "$file"', "update-grub", 'rm -f "$backup"')
assert "flle-ch02-grub.before-iommu" not in script
assert "changed=" not in script

# Exercise the remote state machine entirely in a temporary local fixture.
with tempfile.TemporaryDirectory(prefix="flle02-iommu-test-") as tmp_text:
    tmp = Path(tmp_text)
    grub = tmp / "grub"
    cmdline = tmp / "cmdline"
    backups = tmp / "backups"
    group = tmp / "iommu_groups/7"
    group_link = tmp / "device/iommu_group"
    bindir = tmp / "bin"
    backups.mkdir()
    (group / "devices").mkdir(parents=True)
    group_link.parent.mkdir()
    group_link.symlink_to(group)
    bindir.mkdir()
    update_grub = bindir / "update-grub"
    update_grub.write_text('#!/usr/bin/env bash\ntest "${FAIL_UPDATE_GRUB:-0}" = 0\n')
    update_grub.chmod(0o755)

    fixture_script = remote_script
    fixture_script = fixture_script.replace("/etc/default/grub.flle02.", f"{tmp}/grub.flle02.")
    fixture_script = fixture_script.replace("/etc/default/grub", str(grub))
    fixture_script = fixture_script.replace(
        "/sys/bus/pci/devices/0000:03:00.0/iommu_group", str(group_link)
    )
    fixture_script = fixture_script.replace("/proc/cmdline", str(cmdline))
    fixture_script = fixture_script.replace("/var/backups", str(backups))
    env = os.environ | {"PATH": f"{bindir}:{os.environ['PATH']}"}

    def run_remote(action: str, fail_update: bool = False) -> subprocess.CompletedProcess[str]:
        run_env = env | {"FAIL_UPDATE_GRUB": "1" if fail_update else "0"}
        return subprocess.run(
            ["bash", "-s", "--", action, "TEST"],
            input=fixture_script,
            text=True,
            capture_output=True,
            env=run_env,
            check=False,
        )

    grub.write_text('GRUB_CMDLINE_LINUX=""\n')
    cmdline.write_text("BOOT_IMAGE=/vmlinuz ro\n")
    (group / "devices/0000:03:00.0").touch()
    probe = run_remote("probe")
    assert probe.returncode == 10
    assert 'GRUB_CMDLINE_LINUX=""' in probe.stdout

    applied = run_remote("apply")
    assert applied.returncode == 0
    assert grub.read_text() == 'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"\n'
    assert (backups / "flle-ch02-grub.TEST").exists()
    rolled_back = run_remote("rollback")
    assert rolled_back.returncode == 0
    assert grub.read_text() == 'GRUB_CMDLINE_LINUX=""\n'
    assert not (backups / "flle-ch02-grub.TEST").exists()

    failed = run_remote("apply", fail_update=True)
    assert failed.returncode != 0
    assert (backups / "flle-ch02-grub.TEST").exists()
    assert run_remote("rollback").returncode == 0

    grub.write_text('GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"\n')
    cmdline.write_text("BOOT_IMAGE=/vmlinuz ro intel_iommu=on iommu=pt\n")
    (backups / "flle-ch02-grub.before-iommu").write_text("legacy backup\n")
    assert run_remote("probe").returncode == 0
    (group / "devices/0000:04:00.0").touch()
    wrong_group = run_remote("verify")
    assert wrong_group.returncode != 0
    assert "0000:04:00.0" in wrong_group.stdout

    grub.write_text('GRUB_CMDLINE_LINUX="quiet splash"\n')
    unsafe = run_remote("probe")
    assert unsafe.returncode != 0 and unsafe.returncode != 10
    assert 'GRUB_CMDLINE_LINUX="quiet splash"' in unsafe.stdout

print("02 IOMMU contract: PASS")
