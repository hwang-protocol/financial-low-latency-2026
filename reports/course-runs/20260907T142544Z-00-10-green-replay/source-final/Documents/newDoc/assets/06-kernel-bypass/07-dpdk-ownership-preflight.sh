#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-dpdk-ownership"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
# ~~~~~两端只读；课堂扫读按 DEC-195：对 / 证 + 原生命令 + 读数~~~~~
{
  for host in 10.1.1.1 10.1.1.2; do
    ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" '
      bdf=0000:03:00.0
      netdev=$(basename /sys/bus/pci/devices/$bdf/net/*)
      drv=$(basename "$(readlink -f /sys/bus/pci/devices/$bdf/driver)")
      grp=$(basename "$(readlink -f /sys/bus/pci/devices/$bdf/iommu_group)")
      addr=$(ip -4 -o addr show dev "$netdev" | awk "{print \$4}")
      members=$(ls /sys/bus/pci/devices/$bdf/iommu_group/devices | paste -sd" " -)
      flags=$(awk "{for(i=1;i<=NF;i++) if(\$i==\"intel_iommu=on\"||\$i==\"iommu=pt\") printf \"%s%s\", (n++?\" \":\"\"), \$i}" /proc/cmdline)
      printf "%s / verify\n" "$(hostname)"
      printf "===== 查主机名 =====\n[哪台] 对: vm-2522-01 或 vm-2522-02  证: 没看错机\n$ hostname\n%s\n" "$(hostname)"
      printf "===== 查当前 cmdline =====\n[当前cmdline] 对: 同一行同时有 intel_iommu=on 和 iommu=pt  证: Guest IOMMU 已生效\n$ awk intel_iommu=on|iommu=pt /proc/cmdline\n%s\n" "$flags"
      printf "===== 查出站闸主人 =====\n[出站闸主人] 对: sfc  证: 本步还没把卡交给 vfio-pci\n$ basename .../0000:03:00.0/driver\n%s\n" "$drv"
      printf "===== 查数据口地址 =====\n[数据口] 对: ens64np0/1 上有 20.1.1.1/2  证: 普通网口和课程地址还在\n$ ip -4 -o addr show\n%s  %s\n" "$netdev" "$addr"
      printf "===== 查隔离组 =====\n[隔离组] 对: group 7 只有 0000:03:00.0  证: 钥匙串无夹带，才能单独交 VFIO\n$ readlink / ls .../iommu_group\n%s  %s\n" "$grp" "$members"
    '
  done
} 2>&1 | tee "$OUT/raw/classroom.txt"
(cd "$OUT" && sha256sum raw/classroom.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
