# 第 07 章：eBPF / XDP 可编程网络

- **状态：** ✅ 2026-11-24 完成，`XDP_DROP_GAP_MATCH_PASS`
- **课程原文：** [07-ebpf-xdp-programmable-network.md](../../07-ebpf-xdp-programmable-network.md)
- **课程脚本：** [assets/07-xdp/](../../assets/07-xdp/)，主要参考 `live-support/run-xdp-receiver-live.sh`
- **原始输出和全部脚本：** [../aws-runs/20261124T1029Z-07-xdp/](../aws-runs/20261124T1029Z-07-xdp/)

## 本章要做什么

在 `.2` 的网卡驱动层挂一个 XDP 程序。它在行情包**进入 Linux 网络协议栈之前**就看到每个包：

1. 先全部放行，只计数：多少行情包、AAPL 多少、NVDA 多少
2. 再故意**丢掉恰好 1 个** NVDA 新订单消息
3. 看行情接收程序能否立刻发现缺口（MoldUDP64 序号断了），并自动停止交易

验收标准：XDP 记录的“丢掉的序号” == 行情接收程序报告的“等待中的序号”。

```text
.1 交易所 ──UDP──▶ [ENA 网卡] ──▶ [XDP 程序] ──XDP_PASS──▶ 内核协议栈 ──▶ flle-feed-receiver
                                     │
                                     └──XDP_DROP（只丢 1 个 NVDA Add Order）
```

---

## 第 1 步：装工具链

```bash
ssh flle-tr2 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q clang llvm libbpf-dev linux-tools-common linux-tools-$(uname -r) gcc-multilib >/tmp/apt-xdp.log 2>&1
echo apt_rc=$?
clang --version | head -1; bpftool version | head -1; ls /usr/include/bpf/bpf_helpers.h'
```

| 包 | 用途 |
|---|---|
| `clang` / `llvm` | 把 C 编译成 BPF 字节码（gcc 不行）；`llvm-objdump` 看目标文件 |
| `libbpf-dev` | BPF 头文件，如 `bpf_helpers.h` |
| `linux-tools-$(uname -r)` | 和当前内核版本匹配的 `bpftool`，用来查看、操作 BPF 程序和 map |
| `gcc-multilib` | 提供 `asm/types.h` 等头文件，BPF 编译时要用 |

```text
apt_rc=0
Ubuntu clang version 14.0.0-1ubuntu1.1
bpftool v7.4.0
/usr/include/bpf/bpf_helpers.h
```

## 第 2 步：改 XDP 程序里的 3 个常量

课程的 `flle_xdp_mold_itch.c` 只认实验台的行情：源 `20.1.1.1`、目的组播 `233.74.125.32:31032`。改成 AWS 的单播地址。C 代码里 IP 是 32 位十六进制数，先算出来：

```bash
printf '%x %x\n' $((172<<24|31<<16|10<<8|43)) $((172<<24|31<<16|12<<8|156))
# → ac1f0a2b ac1f0c9c
```

`172<<24` 就是把 172 放到最高 8 位，依次拼起来，等于把 IP 的四段写成一个 32 位整数。

在本机准备一个工作目录（scratchpad），拷课程的辅助脚本，sed 改常量：

```bash
A=assets; S=<工作目录>/ch07; mkdir -p $S
cp $A/07-xdp/live-support/xdp-session.py $A/07-xdp/live-support/set-xdp-policy.py $A/common/wait-feed-state.py $S/
sed -e 's/#define FEED_SOURCE 0x14010101U/#define FEED_SOURCE 0xac1f0a2bU  \/* AWS: 172.31.10.43 (course 20.1.1.1) *\//' \
    -e 's/#define FEED_GROUP  0xe94a7d20U/#define FEED_GROUP  0xac1f0c9cU  \/* AWS unicast dst 172.31.12.156 (course group 233.74.125.32) *\//' \
    -e 's/#define FEED_PORT   31032/#define FEED_PORT   42121  \/* AWS unicast port (course 31032) *\//' \
    $A/07-xdp/flle_xdp_mold_itch.c > $S/flle_xdp_mold_itch.c
diff $A/07-xdp/flle_xdp_mold_itch.c $S/flle_xdp_mold_itch.c
for f in $S/*; do sed -i 's/\r$//' "$f"; done      # 去 Windows 换行
```

```diff
< #define FEED_SOURCE 0x14010101U
> #define FEED_SOURCE 0xac1f0a2bU  /* AWS: 172.31.10.43 (course 20.1.1.1) */
< #define FEED_GROUP  0xe94a7d20U
> #define FEED_GROUP  0xac1f0c9cU  /* AWS unicast dst 172.31.12.156 (course group 233.74.125.32) */
< #define FEED_PORT   31032
> #define FEED_PORT   42121  /* AWS unicast port (course 31032) */
```

课程的辅助脚本是做什么的：

| 脚本 | 作用 |
|---|---|
| `xdp-session.py attach <网卡>` | 用 `ip link set dev <网卡> xdpdrv obj ... sec xdp` 挂载，记下程序 ID 到 `attachment.json` |
| `xdp-session.py dump counters` / `dump drop_audit` | 用 bpftool 把 BPF map 导出成 JSON |
| `xdp-session.py detach` | 卸载自己挂的程序 |
| `set-xdp-policy.py allow\|block <个数> <TTL秒> <程序ID>` | 往策略 map 里写：放行，或者丢掉接下来 N 个 NVDA 新订单 |
| `wait-feed-state.py <URL> <状态>` | 轮询网关 `/api/state`，等行情接收程序进入某个状态（HEALTHY / GAP） |

我自己加了一个 [summarize-counters.py](../aws-runs/20261124T1029Z-07-xdp/summarize-counters.py)：XDP 的计数器是 **per-CPU map**（每个 CPU 一份，避免多核抢同一个计数器），它把各 CPU 的值加起来，再算两次导出之间的增量。

## 第 3 步：主脚本 `ch07-aws.sh`

在 `.2` 上用 sudo 跑。[完整文件](../aws-runs/20261124T1029Z-07-xdp/ch07-aws.sh)，逐段解释：

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
D=/home/ubuntu/flle/ch07; cd "$D"
IF=enp39s0
API=http://172.31.12.156:8088
log(){ printf '\n===== %s =====\n' "$*"; }

log "toolchain"
clang --version | head -1; bpftool version | head -1; ip -V
```

**3.1 编译**

```bash
log "build BPF object"
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu \
  -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o
llvm-objdump -h flle_xdp_mold_itch.o            # 看段：xdp（代码）、.maps（map 定义）、.BTF（类型信息）
sha256sum flle_xdp_mold_itch.c flle_xdp_mold_itch.o
```

| 参数 | 意思 |
|---|---|
| `-target bpf` | 输出 BPF 字节码，不是 x86 机器码 |
| `-O2` | 必须优化，否则 verifier 常常不认未优化的代码 |
| `-g` | 生成 BTF 调试信息，bpftool 才能按字段名显示 map 内容 |
| `-I/usr/include/x86_64-linux-gnu` | Ubuntu 把 `asm/types.h` 放在这里 |

**3.2 记下原始网卡设置，注册“退出时恢复”**

```bash
ORIG_MTU=$(cat /sys/class/net/$IF/mtu)
ORIG_CH=$(ethtool -l $IF | awk '/Current hardware/{f=1} f&&/Combined/{print $2; exit}')
echo "original mtu=$ORIG_MTU combined_channels=$ORIG_CH"
restore() {
  log "restore NIC"
  python3 xdp-session.py detach 2>/dev/null || ip link set dev $IF xdpdrv off 2>/dev/null || true
  ip link set dev $IF mtu "$ORIG_MTU" || true
  ethtool -L $IF combined "$ORIG_CH" 2>/dev/null || true
  ip -details link show dev $IF | head -2
  ethtool -l $IF | tail -5
}
trap restore EXIT        # 不管脚本成功、失败还是中途出错，退出时都恢复网卡
```

`trap ... EXIT` 很重要：改网卡参数的脚本一定要保证能恢复，否则网卡停在奇怪的状态。

**3.3 让 ENA 支持原生 XDP**

```bash
log "prepare ENA for native XDP (MTU <= 3498, half of the queues)"
ip link set dev $IF mtu 1500
ethtool -L $IF combined 2 || echo "channel change refused (continuing)"
ethtool -l $IF | tail -5
sleep 3
```

ENA 驱动的限制：
- **MTU ≤ 3498**：XDP 要求一个包放在一个内存页（4 KB）里，AWS 默认的 9001 巨帧放不下
- **队列只能用一半**：ENA 要给 XDP 的 `XDP_TX` 预留发送队列，4 个降到 2 个

**3.4 挂载**

```bash
log "attach native XDP (xdpdrv)"
python3 xdp-session.py attach $IF
ip -details link show dev $IF | grep -oE 'xdp.*|prog/xdp.*' | head -3
PROG_ID=$(python3 -c 'import json;print(json.load(open("attachment.json"))["program_id"])')
bpftool prog show id "$PROG_ID"
```

`xdpdrv` = 原生模式，程序在驱动里执行。还有 `xdpgeneric`（通用模式，内核协议栈入口处执行，任何网卡都行，但慢）和 `xdpoffload`（跑在网卡上，ENA 不支持）。

**3.5 放行，然后重启回放**（第一次失败后加的，见下面“第一次失败”）

```bash
log "policy allow, then restart replay (NIC reconfiguration above drops packets -> fresh session)"
python3 set-xdp-policy.py allow 0 5 "$PROG_ID"
SESSION_BEFORE=$(curl -fsS $API/api/state | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' $API/api/replay > replay-restart.json
python3 wait-feed-state.py $API/api/state HEALTHY --timeout 30 --session-not "$SESSION_BEFORE" | tee feed-baseline.json
sleep 2
```

`--session-not`：要等到**新的** session 且 HEALTHY，避免旧 session 的状态误判。

**3.6 放行 5 秒，看计数**

```bash
log "observe 5 s with policy allow"
python3 xdp-session.py dump counters > counters-t0.json
sleep 5
python3 xdp-session.py dump counters > counters-allow.json
python3 summarize-counters.py counters-t0.json counters-allow.json
curl -fsS $API/api/state | python3 -c 'import json,sys; f=json.load(sys.stdin)["feed"]; print("feed integrity=%s next_expected=%s gaps=%s gate=%s" % (f["integrity"], f["next_expected"], f["gaps"], f["trading_gate"]))'
```

**3.7 只丢一个**

```bash
log "policy block ONE NVDA Add Order"
python3 set-xdp-policy.py block 1 5 "$PROG_ID"                  # 丢 1 个，5 秒内有效
python3 wait-feed-state.py $API/api/state GAP --timeout 12 | tee feed-gap.json
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"PAUSE"}' $API/api/replay > replay-paused.json || true
python3 xdp-session.py dump counters > counters-block.json
python3 xdp-session.py dump drop_audit > drop-audit.json        # XDP 记录：丢了哪个序号
python3 summarize-counters.py counters-allow.json counters-block.json
```

为什么要暂停回放：让现场停住，导出的 XDP 记录和行情接收程序的状态是同一时刻的。

**3.8 对账**

```bash
log "match XDP audit against feed gap"
python3 - <<'PY'
import json
def unwrap(v): return v.get("formatted", v)
audit = unwrap(json.load(open("drop-audit.json"))[0])["value"]
gap = json.load(open("feed-gap.json"))["feed"]
print("xdp drop_audit:", audit)
print("feed gap: integrity=%s next_expected=%s gap_size=%s pending=%s trading_gate=%s" % (
    gap["integrity"], gap["next_expected"], gap.get("gap_size"), gap.get("pending"), gap.get("trading_gate")))
ok = (audit["drops"] == 1 and audit["first_drop_locate"] == 8095
      and audit["first_drop_sequence"] == gap["next_expected"] and gap["integrity"] == "GAP")
print("verdict=" + ("XDP_DROP_GAP_MATCH_PASS" if ok else "MISMATCH"))
PY
```

四个条件都满足才算通过：只丢了 1 个、丢的是 NVDA（locate 8095）、丢的序号 == 接收方在等的序号、接收方状态是 GAP。

## 第 4 步：上传并运行

```bash
# 交易系统要在跑（bash aws/flle-aws.sh start）
cd <工作目录>/ch07
tar -cf - . | ssh flle-tr2 'mkdir -p ~/flle/ch07 && tar -xf - -C ~/flle/ch07 && cd ~/flle/ch07 &&
  chmod +x *.sh *.py && sudo bash ./ch07-aws.sh > run.log 2>&1; echo rc=$?; cat run.log'
```

---

## 结果（第二次，成功）

```text
===== build BPF object =====
flle_xdp_mold_itch.o:	file format elf64-bpf
Idx Name                   Size     Type
  3 xdp                    00000990 TEXT
  5 .maps                  00000060 DATA
  6 license                00000004 DATA
 16 .BTF                   00000c5d
original mtu=9001 combined_channels=4

===== prepare ENA for native XDP (MTU <= 3498, half of the queues) =====
Current hardware settings:
Combined:	2

===== attach native XDP (xdpdrv) =====
{"interface": "enp39s0", "ifindex": 2, "program_id": 70}
xdp qdisc mq state UP mode DEFAULT group default qlen 1000
prog/xdp id 70 tag 5ea12fda2767642b jited
70: xdp  name flle_xdp_mold_itch  tag 5ea12fda2767642b  gpl
	loaded_at 2026-11-24T10:30:25+0000  uid 0
	xlated 2544B  jited 1572B  memlock 4096B  map_ids 8,6,7
	btf_id 51

===== policy allow, then restart replay =====
policy_id=6 mode=allow remaining=0 ttl_seconds=0
{"session":"0612260002", ... "feed":{"next_expected":505, "gaps":0, "integrity":"HEALTHY","trading_gate":"OPEN"}}

===== observe 5 s with policy allow =====
COURSE_UDP      total=   71063  delta= 53931
MOLD_HEARTBEAT  total=       0  delta=     0
AAPL_STOCK      total=   10935  delta=  6160
NVDA_STOCK      total=   32079  delta= 26951
OTHER_ITCH      total=   28049  delta= 20820
SHORT_INPUT     total=       0  delta=     0
POLICY_DROP     total=       0  delta=     0
feed integrity=HEALTHY next_expected=71065 gaps=0 gate=OPEN

===== policy block ONE NVDA Add Order =====
policy_id=6 mode=block remaining=1 ttl_seconds=5.0
{"session":"0612260002", ... "feed":{"next_expected":71089,"last_delivered":71088,"first_pending":71090,"highest_received":71090,
  "pending":1,"gaps":1,"gap_size":1,"integrity":"GAP","trading_gate":"INHIBITED_FEED_GAP"}}
POLICY_DROP     total=       1  delta=     1

===== match XDP audit against feed gap =====
xdp drop_audit: {'first_drop_sequence': 71089, 'first_drop_locate': 8095, 'drops': 1}
feed gap: integrity=GAP next_expected=71089 gap_size=1 pending=1 trading_gate=INHIBITED_FEED_GAP
verdict=XDP_DROP_GAP_MATCH_PASS

===== restore NIC =====
owned_xdp=detached
2: enp39s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 9001 ... numtxqueues 4 numrxqueues 4
Combined:	4
```

### 怎么读

| 输出 | 意思 |
|---|---|
| `elf64-bpf`，有 `xdp`、`.maps`、`.BTF` 段 | 编译对了：代码、map 定义、类型信息都在 |
| `xdp qdisc` / `prog/xdp id 70` | 网卡上挂着 XDP 程序（`ip link` 显示 `xdp` 而不是 `xdpgeneric`，说明是**原生模式**） |
| `jited` | 字节码已经被 JIT 编译成 x86 机器码，不是解释执行 |
| `xlated 2544B jited 1572B` | 校验后的字节码 2.5 KB，编译成机器码 1.5 KB |
| `map_ids 8,6,7` | 用了 3 个 map：计数器、策略、丢包记录 |
| 放行 5 秒：53,931 个行情包 | 每秒约 1 万个。NVDA 26,951 > AAPL 6,160，NVDA 当天交易更活跃 |
| `POLICY_DROP delta=1` | 只丢了 1 个 |
| `next_expected=71089, first_pending=71090` | 接收方收到了 71090，但还在等 71089 → 发现缺口，71090 先缓存（`pending=1`） |
| `trading_gate=INHIBITED_FEED_GAP` | 行情不完整，自动**停止下单**。用残缺的盘口下单可能亏钱 |
| 最后 `mtu 9001`、`Combined: 4` | 网卡恢复原状 |

---

## 第一次失败：网卡重置先丢了包

第一次的脚本没有 3.5 的“重启回放”。结果（[attempt1-nic-reset-gap/run.log](../aws-runs/20261124T1029Z-07-xdp/attempt1-nic-reset-gap/run.log)）：

```text
feed integrity=GAP next_expected=1930496 gaps=1 gate=INHIBITED_FEED_GAP     ← 还没开始丢，已经是 GAP 了
{"session":"0612260001", "feed":{"next_expected":1930496, "highest_received":1942216, "pending":6886,
  "gap_messages":11516, "resync_required":true, "resync_reason":"GAP_LIMIT", ...}}
feed gap: integrity=GAP next_expected=1930496 gap_size=1 pending=6886 trading_gate=INHIBITED_FEED_GAP
verdict=MISMATCH
```

**原因：** `ip link set mtu` 和 `ethtool -L` 会让 ENA **重置一下**，重置那一瞬间网卡收不了包，行情接收程序在序号 1930496 就出现了缺口。之后积压了 6886 条、超过缓存上限（`GAP_LIMIT`），需要重新同步。XDP 再丢包时，两边序号对不上。

**修复：** 网卡准备好、XDP 挂好之后，先 `RESTART` 回放开一个新 session（0612260002），等 HEALTHY 再丢包。课程原脚本也有这一步，我第一次漏了。

```bash
# 把失败的结果挪到一边，用修好的脚本重跑
cat ch07-aws.sh | ssh flle-tr2 'cd ~/flle/ch07 && mkdir -p attempt1-nic-reset-gap && mv run.log *.json attempt1-nic-reset-gap/;
  cat > ch07-aws.sh && sudo bash ./ch07-aws.sh > run.log 2>&1; echo rc=$?; sed -n "/policy allow/,\$p" run.log'
```

**教训：** 在生产环境改网卡参数、挂 XDP 都会造成瞬间丢包，必须在收盘后做，或者先把这条行情切到备用线路（课程的 A/B 双路组播就是干这个的）。

## 收工：下载

```bash
cd reports/aws-runs; D=20261124T1029Z-07-xdp; mkdir -p $D
ssh flle-tr2 'cd ~/flle/ch07 && sudo chown -R ubuntu: . && tar -czf - --exclude="*.pyc" --exclude=__pycache__ .' | tar -xzf - -C $D
```

`sudo chown -R ubuntu: .`：脚本用 sudo 跑，生成的文件属于 root，先改回来再打包。

## 学到的

- XDP 在包进入协议栈之前处理：可以 `XDP_PASS`（放行）、`XDP_DROP`（丢弃）、`XDP_TX`（原路弹回）、`XDP_REDIRECT`（转到别的网卡或 AF_XDP socket）
- BPF 程序每读一个字段前都要检查 `data + 偏移 <= data_end`，否则内核的 verifier 不让加载。这保证了 BPF 程序不会越界读内存
- BPF map 是内核程序和用户态程序之间交换数据的方式：用户态写策略，XDP 读策略；XDP 写计数，用户态读计数
- MoldUDP64 序号能**立刻**发现丢包，接收程序会自动停止交易
- ENA 支持原生 XDP，但 MTU ≤ 3498、队列减半

## 自己再练的命令

```bash
ssh flle-tr2
sudo bpftool prog list                # 系统里所有 BPF 程序
sudo bpftool map list                 # 所有 map
sudo bpftool net list                 # 哪些网卡挂了 XDP / tc 程序
ip -details link show enp39s0         # 看有没有 xdp 字样
# XDP 挂着的时候：
sudo bpftool map dump id <map_id>     # 直接看计数器
sudo bpftool prog dump xlated id <prog_id> | head -50   # 看校验后的字节码
```

## 笔记 / 疑问

（自己补充）
