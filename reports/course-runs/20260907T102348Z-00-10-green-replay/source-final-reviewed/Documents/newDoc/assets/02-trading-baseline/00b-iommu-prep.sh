#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-guest-iommu-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
exec 9>/run/lock/flle-ch06-guest-iommu.lock; flock -n 9
HOSTS=(10.1.1.1 10.1.1.2)
remote(){ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$1" bash -s -- "$2" "$RUN_ID" <<'REMOTE'
set -Eeuo pipefail
action=$1; run=$2; file=/etc/default/grub; backup="/var/backups/flle-ch06-grub.$run"
state(){ line="$(grep '^GRUB_CMDLINE_LINUX=' "$file" || true)"; cmdline="$(cat /proc/cmdline)"; group="$(readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group 2>/dev/null || true)"
devices=""; test -z "$group" || devices="$(find "$group/devices" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | LC_ALL=C sort || true)"; backups="$(find /var/backups -maxdepth 1 -type f -name 'flle-ch06-grub.*' -printf '%p\n' | LC_ALL=C sort)"; }
raw(){ printf '%s / %s\n' "$(hostname)" "$action"
printf '===== 查主机名 =====\n[哪台] 对: vm-2522-01 或 vm-2522-02  证: 没看错机\n$ hostname\n%s\n' "$(hostname)"
printf '===== 查 GRUB 下次清单 =====\n[GRUB下次清单] 对: GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"  证: 下次开机仍开 IOMMU\n$ grep ^GRUB_CMDLINE_LINUX= /etc/default/grub\n%s\n' "$line"
printf '===== 查本轮备份 =====\n[本轮备份] 对: <none> 或本卡 flle-ch06-grub.<RUN>  证: 旧备份不挡重跑\n$ find /var/backups -name flle-ch06-grub.*\n%s\n' "${backups:-<none>}"
printf '===== 查当前 cmdline =====\n[当前cmdline] 对: 同一行同时有 intel_iommu=on 和 iommu=pt  证: Guest IOMMU 已生效\n$ cat /proc/cmdline\n%s\n' "$cmdline"
printf '===== 查隔离组 =====\n[隔离组] 对: /sys/kernel/iommu_groups/7（7只是本机号）  证: 内核已给 X2522 建 DMA 围栏\n$ readlink -f .../iommu_group\n%s\n' "${group:-<absent>}"
printf '===== 查组里有谁 =====\n[组里有谁] 对: 只有 0000:03:00.0  证: 钥匙串无夹带，才能单独交 VFIO\n$ ls .../iommu_group/devices\n%s\n' "${devices:-<absent>}"; }
valid(){ test "$(grep -c '^GRUB_CMDLINE_LINUX=' "$file")" -eq 1
case "$line" in 'GRUB_CMDLINE_LINUX=""'|'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"');; *) return 1;; esac; }
runtime_ok(){ case " $cmdline " in *' intel_iommu=on '*) ;; *) return 1;; esac; case " $cmdline " in *' iommu=pt '*) ;; *) return 1;; esac
test "${group##*/}" = 7; test "$devices" = 0000:03:00.0; }
case "$action" in
  probe) state; raw; valid; test "$line" = 'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"' && runtime_ok && exit 0; exit 10 ;;
  apply) state; valid; test ! -e "$backup"; install -m 600 "$file" "$backup"; printf '$ backup\n%s\n' "$backup"
    tmp=$(mktemp /etc/default/grub.flle06.XXXXXX); trap 'rm -f "$tmp"' EXIT; sed 's/^GRUB_CMDLINE_LINUX=""$/GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"/' "$file" >"$tmp"; install -m 644 "$tmp" "$file"; printf '$ update-grub\n'; update-grub ;;
  rollback) test ! -e "$backup" || { install -m 644 "$backup" "$file"; printf '$ update-grub\n'; update-grub; rm -f "$backup"; } ;;
  reboot) systemctl reboot ;;
  verify) state; raw; valid; test "$line" = 'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"'; runtime_ok ;;
  vfio) test -e /sys/bus/pci/devices/0000:03:00.0/net/ens64np*; test "$(cat /sys/module/sfc/version)" = "$(modinfo -F version sfc)"; modprobe vfio-pci; unsafe="$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)"; test "$unsafe" = N; printf '%s / vfio\n===== 查 VFIO DMA 安全模式 =====\n[unsafe no-IOMMU] 对: N  证: VFIO 不允许绕过 IOMMU\n$ cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode\n%s\n' "$(hostname)" "$unsafe" ;;
  commit) rm -f "$backup" ;;
esac
REMOTE
}
declare -A plan=(); preflight_failed=0
for host in "${HOSTS[@]}"; do
  if remote "$host" probe 2>&1 | tee -a "$OUT/raw/preflight.txt"; then plan[$host]=0; else rc=${PIPESTATUS[0]}; if test "$rc" -eq 10; then plan[$host]=10; else preflight_failed=1; fi; fi
done
test "$preflight_failed" -eq 0; touched=()
for host in "${HOSTS[@]}"; do
  test "${plan[$host]}" -eq 10 || continue; touched+=("$host")
  if remote "$host" apply 2>&1 | tee -a "$OUT/raw/configure.txt"; then continue; fi
  rollback_failed=0
  for item in "${touched[@]}"; do remote "$item" rollback 2>&1 | tee -a "$OUT/raw/rollback.txt" || rollback_failed=1; done
  test "$rollback_failed" -eq 0 || printf 'rollback incomplete; use the preserved RUN backup\n' >&2
  exit 1
done
declare -A boot=(); for host in "${touched[@]}"; do boot[$host]="$(ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" cat /proc/sys/kernel/random/boot_id)"; done
for host in "${touched[@]}"; do remote "$host" reboot >/dev/null 2>&1 || true; done
for host in "${touched[@]}"; do ready=0; for _ in {1..180}; do current="$(ssh -n -o ConnectTimeout=2 -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"; test -n "$current" && test "$current" != "${boot[$host]}" && { ready=1; break; }; sleep 1; done; test "$ready" -eq 1; done
for host in "${touched[@]}"; do remote "$host" verify 2>&1 | tee -a "$OUT/raw/after-boot.txt"; done
for host in "${HOSTS[@]}"; do remote "$host" vfio 2>&1 | tee -a "$OUT/raw/vfio.txt"; done
for host in "${touched[@]}"; do remote "$host" commit; done
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
echo "evidence=$OUT"
