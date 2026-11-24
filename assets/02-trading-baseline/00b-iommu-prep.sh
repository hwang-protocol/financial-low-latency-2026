#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-guest-iommu-prep"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
exec 9>/run/lock/flle-ch02-guest-iommu.lock; flock -n 9
HOSTS=(10.1.1.1 10.1.1.2)
remote(){ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$1" bash -s -- "$2" "$RUN_ID" <<'REMOTE'
set -Eeuo pipefail
action=$1; run=$2; file=/etc/default/grub; backup="/var/backups/flle-ch02-grub.$run"
state(){ line="$(grep '^GRUB_CMDLINE_LINUX=' "$file" || true)"; cmdline="$(cat /proc/cmdline)"; group="$(readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group 2>/dev/null || true)"
devices=""; test -z "$group" || devices="$(find "$group/devices" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | LC_ALL=C sort || true)"; backups="$(find /var/backups -maxdepth 1 -type f -name 'flle-ch02-grub.*' -printf '%p\n' | LC_ALL=C sort)"; }
raw(){ printf '%s / %s\n' "$(hostname)" "$action"
printf '===== 查主机名 =====\n[主机说明] 以下检查对应当前主机：vm-2522-01 或 vm-2522-02。\n$ hostname\n%s\n' "$(hostname)"
printf '===== 查下次启动参数 =====\n[配置说明] GRUB_CMDLINE_LINUX 中应有 intel_iommu=on iommu=pt，供下次开机使用。\n$ grep ^GRUB_CMDLINE_LINUX= /etc/default/grub\n%s\n' "$line"
printf '===== 查本轮备份 =====\n[备份说明] 列出启动配置备份；<none> 表示没有备份文件。\n$ find /var/backups -maxdepth 1 -type f -name %q -printf %q | LC_ALL=C sort\n%s\n' 'flle-ch02-grub.*' '%p\n' "${backups:-<none>}"
printf '===== 查当前启动参数 =====\n[生效检查] 当前启动参数应同时包含 intel_iommu=on 和 iommu=pt。\n$ cat /proc/cmdline\n%s\n' "$cmdline"
printf '===== 查隔离组 =====\n[设备检查] 自动核对本课网卡的 IOMMU 分组，预期为 /sys/kernel/iommu_groups/7。\n$ readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group\n%s\n' "${group:-<absent>}"
printf '===== 核对分组内设备 =====\n[设备检查] 本课应只包含数据口 0000:03:00.0，脚本会自动核对。\n$ find %q -mindepth 1 -maxdepth 1 -printf %q | LC_ALL=C sort\n%s\n' "$group/devices" '%f\n' "${devices:-<absent>}"; }
valid(){ test "$(grep -c '^GRUB_CMDLINE_LINUX=' "$file")" -eq 1
case "$line" in 'GRUB_CMDLINE_LINUX=""'|'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"');; *) return 1;; esac; }
runtime_ok(){ case " $cmdline " in *' intel_iommu=on '*) ;; *) return 1;; esac; case " $cmdline " in *' iommu=pt '*) ;; *) return 1;; esac
test "${group##*/}" = 7; test "$devices" = 0000:03:00.0; }
case "$action" in
  probe) state; raw; valid; test "$line" = 'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"' && runtime_ok && exit 0; exit 10 ;;
  apply) printf '%s / apply\n===== 配置下次启动参数 =====\n先备份当前文件，再加入 IOMMU 参数；重启后还需读取实际状态。\n' "$(hostname)"; state; valid; test ! -e "$backup"; printf '$ install -m 600 %q %q\n' "$file" "$backup"; install -m 600 "$file" "$backup"; printf '备份文件：%s\n' "$backup"
    tmp=$(mktemp /etc/default/grub.flle02.XXXXXX); trap 'rm -f "$tmp"' EXIT; printf '$ sed %q %q > %q\n' 's/^GRUB_CMDLINE_LINUX=""$/GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"/' "$file" "$tmp"; sed 's/^GRUB_CMDLINE_LINUX=""$/GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"/' "$file" >"$tmp"; printf '$ install -m 644 %q %q\n' "$tmp" "$file"; install -m 644 "$tmp" "$file"; printf '$ update-grub\n'; update-grub ;;
  rollback) printf '%s / rollback\n===== 恢复启动配置 =====\n配置未完成，使用本次备份恢复。\n' "$(hostname)"; test ! -e "$backup" || { printf '$ install -m 644 %q %q\n' "$backup" "$file"; install -m 644 "$backup" "$file"; printf '$ update-grub\n'; update-grub; rm -f "$backup"; } ;;
  reboot) systemctl reboot ;;
  verify) state; raw; valid; test "$line" = 'GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"'; runtime_ok ;;
  vfio) test -e /sys/bus/pci/devices/0000:03:00.0/net/ens64np*; test "$(cat /sys/module/sfc/version)" = "$(modinfo -F version sfc)"; printf '%s / vfio\n===== 加载 VFIO 支持 =====\n加载模块后核对安全模式；本步不把网卡交给 VFIO。\n$ modprobe vfio-pci\n' "$(hostname)"; modprobe vfio-pci; unsafe="$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)"; printf '%s / vfio\n===== 查是否允许绕过 IOMMU =====\n[参数说明] 这个开关决定：是否允许 VFIO 绕过 IOMMU？\n[模式检查] N = No：不允许绕过。脚本要求 N，否则停止。\n$ cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode\n%s\n' "$(hostname)" "$unsafe"; test "$unsafe" = N ;;
  commit) printf '%s / cleanup\n===== 清理本次备份 =====\n启动状态核验已通过；删除本次临时备份，rm 成功时没有正文输出。\n$ rm -f %q\n' "$(hostname)" "$backup"; rm -f "$backup" ;;
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
for host in "${touched[@]}"; do printf '%s / reboot\n===== 重启以应用参数 =====\n仅重启本次改过配置的主机；等待启动标识变化后再核验。\n$ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@%s bash -s -- reboot %q\n远端 REMOTE 段执行：systemctl reboot\n' "$host" "$host" "$RUN_ID" | tee -a "$OUT/raw/reboot.txt"; remote "$host" reboot >>"$OUT/raw/reboot.txt" 2>&1 || true; done
for host in "${touched[@]}"; do ready=0; for _ in {1..180}; do current="$(ssh -n -o ConnectTimeout=2 -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"; test -n "$current" && test "$current" != "${boot[$host]}" && { ready=1; break; }; sleep 1; done; test "$ready" -eq 1; done
for host in "${touched[@]}"; do remote "$host" verify 2>&1 | tee -a "$OUT/raw/after-boot.txt"; done
for host in "${HOSTS[@]}"; do remote "$host" vfio 2>&1 | tee -a "$OUT/raw/vfio.txt"; done
for host in "${touched[@]}"; do remote "$host" commit 2>&1 | tee -a "$OUT/raw/cleanup.txt"; done
printf '===== 准备结果 =====\n[检查结果] IOMMU 启动参数与 VFIO 支持检查通过，数据口仍由 sfc 管理。\n[下一步] 执行准备 B2，安装 DPDK / F-Stack 软件。\n' | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
echo "evidence=$OUT"
