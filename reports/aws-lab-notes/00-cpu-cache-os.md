# 第 00 章：CPU、缓存与操作系统基础

- **状态：** ✅ 2026-11-24 完成
- **课程原文：** [00-cpu-cache-memory-os-basics.md](../../00-cpu-cache-memory-os-basics.md)
- **课程脚本：** [assets/00-basics/01-cpu-cache-baseline.sh](../../assets/00-basics/01-cpu-cache-baseline.sh)、[02-page-fault-shape.sh](../../assets/00-basics/02-page-fault-shape.sh)
- **原始输出：** [../aws-runs/20261124T1012Z-00-basics/](../aws-runs/20261124T1012Z-00-basics/)
- **机器：** `flle-trader-2`，当时临时改成 c7i.xlarge（4 vCPU）

## 本章要做什么

围绕四个“等待点”理解延迟从哪里来：取数据（缓存）、准备内存（缺页）、CPU 调度、收包（中断 vs 轮询）。动手的部分只有两个：

1. 看这台机器的 CPU、缓存、页大小
2. 运行 ①：第一次往内存写数据，看见缺页

---

## 实验 1：CPU 和缓存基线

### 课程原脚本为什么不能直接跑

课程脚本写死了 `ssh root@10.1.1.101 bash -s <<'REMOTE' ... REMOTE`，也就是登录到实验台的某台机器再执行。AWS 上没有 `10.1.1.101`，所以我把 `<<'REMOTE'` 和 `REMOTE` 之间的那段脚本**原样抠出来**，用 SSH 送到 `.2` 上执行。

### 执行的命令（在本机 Git Bash，仓库根目录）

```bash
mkdir -p reports/aws-runs/ch00

# awk 的意思：遇到 "bash -s <<'REMOTE'" 那一行就开始打印（f=1），遇到单独一行 REMOTE 就停止
awk '/bash -s <<.REMOTE./{f=1;next} /^REMOTE$/{f=0} f' assets/00-basics/01-cpu-cache-baseline.sh \
  | ssh flle-tr2 'bash -s' > reports/aws-runs/ch00/01-cpu-cache-baseline.txt 2>&1
```

> **踩坑：** 第一次用 `sed -n '/^ssh .../,/^REMOTE$/p'` 抠，结果是空文件。原因是 Windows checkout 的文件行尾带 `\r`，`^REMOTE$` 匹配不上。换成上面的 awk 写法就好了。

抠出来、实际在 `.2` 上跑的脚本就是这几行：

```bash
set -Eeuo pipefail
printf '$ lscpu\n'; lscpu                                # CPU 型号、核数、各级缓存总量
printf '\n$ getconf PAGE_SIZE\n'; getconf PAGE_SIZE      # 内存页大小
printf '\n$ /sys/devices/system/cpu/cpu0/cache/index*/...\n'
for d in /sys/devices/system/cpu/cpu0/cache/index*; do   # 逐级读 CPU 0 的缓存
  printf '%s ' "$(basename "$d")"
  printf 'level='; tr -d '\n' <"$d/level"                # 第几级：1/2/3
  printf ' type='; tr -d '\n' <"$d/type"                 # Data / Instruction / Unified
  printf ' size='; tr -d '\n' <"$d/size"                 # 每个核看到的容量
  printf ' line='; cat "$d/coherency_line_size"          # 缓存行大小
done
```

另外开机时还看了 vCPU 的拓扑（哪些 vCPU 在同一个物理核上）：

```bash
ssh flle-tr2 'nproc; lscpu -e=CPU,CORE,SOCKET,NODE; uname -r'
```

### 实际输出（节选）

```text
Model name:            Intel(R) Xeon(R) Platinum 8488C
Thread(s) per core:    2
Core(s) per socket:    2
Socket(s):             1
Hypervisor vendor:     KVM
Virtualization type:   full
L1d cache:             96 KiB (2 instances)
L1i cache:             64 KiB (2 instances)
L2 cache:              4 MiB (2 instances)
L3 cache:              105 MiB (1 instance)
NUMA node0 CPU(s):     0-3

$ getconf PAGE_SIZE
4096

$ /sys/devices/system/cpu/cpu0/cache/index*/...
index0 level=1 type=Data size=48K line=64
index1 level=1 type=Instruction size=32K line=64
index2 level=2 type=Unified size=2048K line=64
index3 level=3 type=Unified size=107520K line=64
```

```text
CPU CORE SOCKET NODE
  0    0      0    0
  1    1      0    0
  2    0      0    0
  3    1      0    0
6.8.0-1069-aws
```

### 怎么读

| 看到的 | 意思 |
|---|---|
| `Xeon Platinum 8488C` | 第 4 代至强 Sapphire Rapids，AWS 定制型号 |
| `Hypervisor vendor: KVM` | 这是虚拟机，底下是 AWS Nitro（基于 KVM） |
| `Thread(s) per core: 2` | 开了超线程，一个物理核当两个 vCPU 用 |
| `L1d 96 KiB (2 instances)` | `lscpu` 显示的是**总量**：2 个物理核 × 48K。`/sys` 里看的是**每核** 48K |
| `L3 105 MiB (1 instance)` | 整颗 CPU 共享的末级缓存，所有核共用 |
| `line=64` | 缓存行 64 字节。CPU 从内存搬数据的最小单位，也是“伪共享”问题的根源 |
| `PAGE_SIZE 4096` | 内存页 4 KB，下一个实验就按页来写 |
| `lscpu -e` 的 CORE 列 | CPU 0 和 2 是同一个物理核（CORE 0），1 和 3 是 CORE 1。**第 04 章**把线程分别绑到 CPU 2、3 时要记住这点 |

---

## 实验 2：运行 ①，第一次往每页写数据

### 执行的命令

同样把课程脚本里的 Python 部分抠出来，送到 `.2` 上用 `python3 -` 执行（`-` 表示从标准输入读程序）：

```bash
sed -n "/^import mmap/,/^buf.close()/p" assets/00-basics/02-page-fault-shape.sh \
  | ssh flle-tr2 'python3 -' > reports/aws-runs/ch00/02-page-fault-shape.txt 2>&1
```

实际执行的 Python（课程原文，注释是课程写的）：

```python
import mmap, os, resource

page = os.sysconf("SC_PAGE_SIZE")          # A. 页大小
size = page * 128                          #    申请 128 页
buf = mmap.mmap(-1, size,                  #    匿名、私有、可读写的内存
                flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE)
before = resource.getrusage(resource.RUSAGE_SELF).ru_minflt   # B. 写之前的次缺页累计数

for offset in range(0, size, page):        # C. 每页写 1 个字节
    buf[offset] = 1

after = resource.getrusage(resource.RUSAGE_SELF).ru_minflt    # D. 写之后
print("page_size=%d" % page)
print("touched_pages=%d" % (size // page))
print("minor_fault_delta=%d" % (after - before))
buf.close()
```

### 实际输出

```text
page_size=4096
touched_pages=128
minor_fault_delta=128
```

### 怎么读

- `mmap` 返回时，内核只是**登记了一段地址**，并没有真正分配物理内存
- 每页**第一次被写**时，CPU 发现这个地址还没对应物理页，触发**缺页异常**，内核这时才分配一页、清零、建立映射，再让程序继续
- 写了 128 页，次缺页正好多了 128 次，一页一次
- “次缺页”（minor fault）：不用读硬盘，只是分配内存。“主缺页”（major fault）要从硬盘读，慢得多
- **和低延迟的关系：** 每次缺页要几百纳秒到几微秒。交易程序如果在开盘后才第一次碰某块内存，这个延迟就落在关键路径上。所以交易程序启动时会**先把所有要用的内存写一遍**（预热，pre-fault），或者用 `mlockall`、大页（hugepage）

---

## AWS 和课程的区别

- 课程在实验台物理机上跑，AWS 是 KVM 虚拟机。`lscpu` 能看到 `Hypervisor vendor: KVM`
- 缺页实验的结果和物理机一样（128 → 128），这是操作系统行为，和虚拟化无关
- 课程里讲的 `perf` 硬件计数器（缓存命中率等），c7i 虚拟机只支持一部分事件，要完整的用 `.metal` 机型

## 自己再练的命令

```bash
ssh flle-tr2
lscpu -e                                    # 每个 vCPU 属于哪个核
cat /proc/cpuinfo | grep -m1 flags          # CPU 支持的指令集
grep -E 'pgfault|pgmajfault' /proc/vmstat   # 系统总的缺页计数
# 申请 100MB 并每页写一次，看次缺页数（约 25600 = 100MB / 4KB，再加上 Python 自己的）
/usr/bin/time -v python3 -c 'x=bytearray(100*1024*1024); x[::4096]=b"\1"*(len(x)//4096)' 2>&1 | grep -i fault
```

## 笔记 / 疑问

（自己补充）
