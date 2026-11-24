# 第 04 章：C++ 热路径——队列、忙轮询与 CPU 隔离

- **状态：** 🟡 2026-11-24 四组都跑完；快慢方向清楚，但课程的环境稳定检查没通过（EC2 网络抖动）
- **课程原文：** [04-low-latency-software-design.md](../../04-low-latency-software-design.md)
- **课程脚本：** [assets/04-live-software/01~04-*.sh](../../assets/04-live-software/)，测量程序 [apps/flle-trading-lab/tests/software_measurement.py](../../apps/flle-trading-lab/tests/software_measurement.py)
- **原始输出：** [../aws-runs/20261124T1013Z-04-software/](../aws-runs/20261124T1013Z-04-software/)

## 本章要测什么

MANUAL 交易员是一个 C++ 进程，里面有两个线程：

```text
网页下单 → [管理线程] ──放进队列──▶ [下单线程] ──OUCH/TCP──▶ 交易所
                       └──── “交接”（handoff）────┘
```

本章只测**交接**这一小段：管理线程把订单放进队列，到下单线程拿到它，花了多久。比较三件事：

| 运行 | 对比 | 课程配置名 |
|---|---|---|
| ① | 基线：`std::deque` + 互斥锁 + 条件变量 | `DEQUE_CV` |
| ② | 队列存储：`deque` vs 固定大小 Ring | `DEQUE_CV` vs `FIXED_CV` |
| ③ | 交接方式：锁 + 条件变量（睡着等通知） vs 无锁 SPSC + 忙轮询（一直盯着看） | `FIXED_CV` vs `SPSC_SPIN` |
| ④ | 下单线程的 CPU：独占 vs 和杂活挤一个核 | `SPSC_SPIN:dedicated` vs `SPSC_SPIN:shared` |

---

## 准备 1：把 `.2` 换成 4 个 vCPU

课程把 MANUAL 下单线程绑 CPU 2、AUTO 绑 CPU 3、杂活放 CPU 0–1，至少要 4 个 vCPU。c7i.large 只有 2 个，所以临时换成 c7i.xlarge（每小时多约 0.1 美元）。

```bash
export MSYS_NO_PATHCONV=1 R=ap-northeast-1
# 确认两台都是停机状态（改机型必须先停机）
aws ec2 describe-instances --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364 \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name]' --output text
# 改机型 → 开机
aws ec2 modify-instance-attribute --region $R --instance-id i-0872ca5de433c6364 --instance-type '{"Value":"c7i.xlarge"}'
aws ec2 start-instances --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364
aws ec2 wait instance-running --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364

# 等 SSH 能连上，看 CPU 拓扑
for h in flle-ex1 flle-tr2; do
  for i in $(seq 1 20); do ssh -o ConnectTimeout=8 $h 'echo "$(hostname) up; nproc=$(nproc)"; lscpu -e=CPU,CORE,SOCKET,NODE' && break; sleep 6; done
done
```

```text
ip-172-31-12-156 up; nproc=4
CPU CORE SOCKET NODE
  0    0      0    0
  1    1      0    0
  2    0      0    0
  3    1      0    0
```

**注意：** CPU 0 和 2 在同一个物理核，1 和 3 在同一个物理核。所以“MANUAL 在 CPU 2 独占”其实和 CPU 0 的杂活共用一个物理核的执行单元（超线程），比课程物理机更“吵”。

然后启动交易系统（见[第 02 章](02-trading-baseline.md)）：

```bash
cd apps/flle-trading-lab && bash aws/flle-aws.sh start && bash aws/flle-aws.sh status
```

## 准备 2：改测量程序，让它能在 AWS 上跑

课程的 `software_measurement.py` 有三处和实验台绑死：

1. 用 `ssh root@10.1.1.2 ...` 远程去读 CPU 列表、给线程绑核。AWS 上测量程序**本来就在 `.2` 上跑**，直接本机执行就行
2. 测量时把行情切成 `MULTICAST_A`（只发 A 路组播）。AWS 没有组播，要保持 `UNICAST`
3. 恢复脚本默认 IP 是 `10.1.1.2`

不改原文件，用 sed 生成一份 `_aws` 版本：

```bash
ssh flle-tr2 'set -e; cd ~/flle/app/tests
sed -e "s/\[\"ssh\", f\"root@{host}\", \"cat\", /[\"cat\", /" \
    -e "s/\[\"ssh\", f\"root@{host}\", \"bash\", \"-s\"\]/[\"bash\", \"-s\"]/" \
    -e "s/\"MULTICAST_A\"/\"UNICAST\"/g" \
    -e "s/测量期间只发 A 路组播，B 路关闭。/测量期间固定为单播 UNICAST（AWS 无组播）。/" \
    software_measurement.py > software_measurement_aws.py
sed -e "s/from software_measurement import/from software_measurement_aws import/" \
    -e "s/default=\"10.1.1.2\"/default=\"172.31.12.156\"/" \
    restore_software_profile.py > restore_software_profile_aws.py
diff software_measurement.py software_measurement_aws.py | grep "^[<>]"
grep -c ssh software_measurement_aws.py || true                          # 应该是 0
python3 -c "import ast; ast.parse(open(\"software_measurement_aws.py\").read())" && echo syntax-ok   # 语法检查
curl -s http://172.31.12.156:8088/api/state | python3 -c "import json,sys; s=json.load(sys.stdin); print(s[\"market_mode\"], s[\"replay\"][\"status\"], {k:v[\"status\"] for k,v in s[\"health\"].items()})"'
```

改动（完整的在 [aws-patch.diff](../aws-runs/20261124T1013Z-04-software/aws-patch.diff)）：

```diff
<             ["ssh", f"root@{host}", "cat", "/sys/devices/system/cpu/online"],
>             ["cat", "/sys/devices/system/cpu/online"],
<         ["ssh", f"root@{host}", "bash", "-s"], input=script, text=True,
>         ["bash", "-s"], input=script, text=True,
<     record = dict(original_mode=original, measurement_mode="MULTICAST_A", restored=False)
>     record = dict(original_mode=original, measurement_mode="UNICAST", restored=False)
<         set_market_mode(base_url, "MULTICAST_A")
>         set_market_mode(base_url, "UNICAST")
```

**学到的写法：** `ast.parse` 只解析不执行，用来检查 sed 改完的 Python 有没有语法错误，很安全。

## 准备 3：写一个脚本连跑四组

课程每组一个脚本（`01-*.sh` ~ `04-*.sh`），参数完全相同，只是 `--profiles` 和 CPU 安排不同。我把它们合成一个 `run-all.sh`，放在 `.2` 上后台跑（四组一共约 10 分钟，SSH 断了也不受影响）。

`~/flle/ch04/run-all.sh`（最终版，[原文件](../aws-runs/20261124T1013Z-04-software/run-all.sh)）：

```bash
#!/usr/bin/env bash
set -uo pipefail
cd ~/flle/app/tests
TR=172.31.12.156
COMMON=(--base-url http://$TR:8088 --trader-host $TR --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3
  --precondition-samples 1000 --warmup 40 --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20
  --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5
  --bootstrap-resamples 4000 --bootstrap-seed 20260828)
run() { # 名字 配置 其他参数...
  local name=$1 prof=$2; shift 2
  local out=~/flle/ch04/$name; mkdir -p $out
  echo "===== START $name $(date -u +%FT%TZ)"
  taskset -c 1 python3 software_measurement_aws.py --profiles "$prof" "${COMMON[@]}" "$@" --output $out/software.csv > $out/result.txt 2>&1
  echo "rc=$? $name $(date -u +%FT%TZ)"
}
run 01-deque-cv        DEQUE_CV:dedicated                      --shared-cpu 1 --housekeeping-cpus 0-1
run 02-fixed-cv        DEQUE_CV:dedicated,FIXED_CV:dedicated   --shared-cpu 1 --housekeeping-cpus 0-1
run 03-spsc-spin       FIXED_CV:dedicated,SPSC_SPIN:dedicated  --shared-cpu 1 --housekeeping-cpus 0-1
run 04-spsc-shared-cpu SPSC_SPIN:dedicated,SPSC_SPIN:shared    --shared-cpu 0 --housekeeping-cpus 0
taskset -c 1 python3 restore_software_profile_aws.py > ~/flle/ch04/restore.txt 2>&1; echo "restore rc=$?"
echo ALL-DONE
```

### 参数是什么意思（和课程完全一样）

| 参数 | 值 | 意思 |
|---|---|---|
| `--profiles` | `A:dedicated,B:dedicated` | 要比较的两种配置；只有一个就是测基线 |
| `--repeat 8` | | 每种配置跑 8 轮。两种配置交替跑（ABBA 顺序），抵消时间漂移 |
| `--precondition-samples 1000` | | 正式测之前先热身 1000 笔，让缓存、分支预测都热起来 |
| `--warmup 40 --samples 400` | | 每轮先丢弃 40 笔，再记 400 笔 |
| `--interval-us 20000` | | 每 20 ms 下一笔（每秒 50 笔），不是压测，是看单笔延迟 |
| `--treatment-cpu 2` | | MANUAL 下单线程（被测的）绑 CPU 2 |
| `--control-cpu 3 --control-port 48121` | | AUTO 交易员绑 CPU 3，作为**对照组** |
| `--control-every 5` | | 每 5 笔 MANUAL 单插 1 笔 AUTO 单。AUTO 配置一直不变，它的延迟变了，说明是**环境**变了，不是被测配置的问题 |
| `--shared-cpu` / `--housekeeping-cpus` | | “挤共享核”时下单线程坐哪；杂活线程放哪些 CPU |
| `--stability-limit-pct 20` | | **每轮内**，AUTO 前半段和后半段的往返中位数变化不能超过 20%，否则这一轮作废 |
| `--environment-equivalence-pct 40` | | 两种配置下 AUTO 的整体差异不能超过 40% |
| `--single-profile-spread-limit 1.5` | | 同一配置 8 轮之间，最慢一轮 p99 不能超过最快一轮的 1.5 倍 |
| `--direction-consistency-pct 87.5` | | 相邻的 A/B 对里，至少 7/8 对是同一边更快 |
| `--bootstrap-resamples 4000 --bootstrap-seed ...` | | 用 bootstrap 重抽样 4000 次算 p99 差异的 95% 置信区间；固定种子，结果可复现 |

**为什么要 `taskset -c 1`：** 见下面的“踩坑”。

### 上传并后台运行

```bash
# 用 bash -s 从标准输入传脚本（原因见踩坑 2）
cat <<'EOF' | ssh flle-tr2 'bash -s'
cd ~/flle/ch04
chmod +x run-all.sh
setsid nohup ./run-all.sh > run-all.log 2>&1 < /dev/null &    # 完全脱离 SSH 会话
sleep 3
for p in $(pgrep -f 'software_measurement_aws[.]py'); do taskset -pc $p; done   # 确认绑在 CPU 1
cat run-all.log
EOF
```

- `nohup`：忽略 SSH 断开时的挂断信号
- `setsid`：开一个新会话，彻底和当前终端分开
- `< /dev/null`：不占用 SSH 的标准输入，否则 SSH 会一直等着不退出
- `taskset -pc PID`：查看某个进程允许在哪些 CPU 上跑

### 在本机等它跑完

```bash
until ssh -o ConnectTimeout=10 flle-tr2 'grep -q ALL-DONE ~/flle/ch04/run-all.log'; do sleep 30; done
ssh flle-tr2 'cat ~/flle/ch04/run-all.log'
```

```text
===== START 01-deque-cv 2026-11-24T10:13:53Z
rc=0 01-deque-cv 2026-11-24T10:15:42Z
===== START 02-fixed-cv 2026-11-24T10:15:42Z
rc=0 02-fixed-cv 2026-11-24T10:19:29Z
===== START 03-spsc-spin 2026-11-24T10:19:29Z
rc=1 03-spsc-spin 2026-11-24T10:20:09Z        ← 失败了，见踩坑 3
===== START 04-spsc-shared-cpu 2026-11-24T10:20:09Z
rc=0 04-spsc-shared-cpu 2026-11-24T10:23:56Z
restore rc=0
ALL-DONE
```

看每组的摘要（`sed -n "/测量摘要/,\$p"`：从“测量摘要”那行打印到文件末尾）：

```bash
ssh flle-tr2 'cd ~/flle/ch04; for d in 0?-*; do echo "#### $d"; sed -n "/测量摘要/,\$p" $d/result.txt; done; cat restore.txt'
```

---

## 踩坑记录（按发生顺序）

### 踩坑 1：测量程序没绑核，把被测线程挤了

第一次没加 `taskset`。跑着跑着发现运行 ① 的交接 p99 是 **255 µs**，看了一下：

```bash
ssh flle-tr2 'pgrep -af software_measurement | head -2; top -bn1 | head -15'
```

测量程序（Python）自己占了 100% 一个核，而且调度器会把它挪到任何 CPU 上，包括被测的 CPU 2。于是用 `taskset -c 1` 把它固定在 CPU 1（杂活核），从头重跑。没绑核的结果留在 [unpinned-attempt/](../aws-runs/20261124T1013Z-04-software/unpinned-attempt/) 作对比。

### 踩坑 2：`pkill -f` 把自己杀了

想停掉旧的运行，我执行了：

```bash
ssh flle-tr2 'pkill -f run-all.sh; pkill -f software_measurement_aws.py; ...后续命令'
```

结果后面的命令都没执行。原因：`ssh` 在远端是用 `bash -c '整条命令'` 执行的，这个 bash 进程的命令行里**也包含 `run-all.sh` 这个字符串**，所以 `pkill -f run-all.sh` 把执行它的 bash 也杀了。

两个解决办法，我都用了：
1. **脚本走标准输入：** `cat <<'EOF' | ssh flle-tr2 'bash -s'`。远端进程的命令行只是 `bash -s`，不含要杀的名字
2. **正则小技巧：** `pkill -f 'run-all[.]sh'`。`[.]` 匹配的是字符 `.`，但 `pkill` 自己的命令行里是 `[.]`，匹配不上自己

```bash
cat <<'EOF' | ssh flle-tr2 'bash -s'
pkill -f 'run-all[.]sh'
pkill -f 'software_measurement_aws[.]py'
sleep 2
pgrep -af 'measurement_aws' || echo "old runner stopped"
cd ~/flle/ch04
rm -rf unpinned-attempt; mkdir unpinned-attempt; mv 0?-* run-all.log unpinned-attempt/
sed -i 's/^  python3 software_measurement_aws.py/  taskset -c 1 python3 software_measurement_aws.py/; s/^python3 restore_software_profile_aws.py/taskset -c 1 python3 restore_software_profile_aws.py/' run-all.sh
grep -c 'taskset -c 1' run-all.sh
setsid nohup ./run-all.sh > run-all.log 2>&1 < /dev/null &
EOF
```

### 踩坑 3：运行 ③ 撞到持仓上限

```text
  File "/home/ubuntu/flle/app/flle_trading/gateway.py", line 701, in send_command
    raise ValueError(str(response["error"]))
ValueError: position limit
```

查当时的持仓和策略配置：

```bash
cat <<'EOF' | ssh flle-tr2 'bash -s'
curl -s http://172.31.12.156:8088/api/state | python3 -c '
import json,sys; s=json.load(sys.stdin)
for k in ("positions","strategy"):
    if k in s: print(k, json.dumps(s[k]))'
EOF
```

```text
positions {"AAPL": 50, "NVDA": 25}
strategy {"enabled": true, "imbalance_threshold": 0.35, "quantity": 25, "max_position": 200, "cooldown_ms": 5000}
```

AUTO 策略一直在后台自动交易，测量时又不断下对照单，某一刻持仓碰到了风控上限（200）被拒单。查的时候已经回落到 50，所以单独重跑运行 ③ 就行。失败的记录改名保留：

```bash
cat <<'EOF' | ssh flle-tr2 'bash -s'
cd ~/flle/ch04 && mv 03-spsc-spin 03-spsc-spin-failed-position-limit
cat > rerun-03.sh <<'R'
#!/usr/bin/env bash
cd ~/flle/app/tests
TR=172.31.12.156; out=~/flle/ch04/03-spsc-spin; mkdir -p $out
echo "START $(date -u +%FT%TZ)"
taskset -c 1 python3 software_measurement_aws.py --profiles FIXED_CV:dedicated,SPSC_SPIN:dedicated \
  --base-url http://$TR:8088 --trader-host $TR --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3 \
  --precondition-samples 1000 --warmup 40 --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20 \
  --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5 \
  --bootstrap-resamples 4000 --bootstrap-seed 20260828 --shared-cpu 1 --housekeeping-cpus 0-1 \
  --output $out/software.csv > $out/result.txt 2>&1
echo "rc=$? $(date -u +%FT%TZ)"
taskset -c 1 python3 restore_software_profile_aws.py > ~/flle/ch04/restore-after-03.txt 2>&1
echo RERUN-DONE
R
chmod +x rerun-03.sh; setsid nohup ./rerun-03.sh > rerun-03.log 2>&1 < /dev/null &
EOF

until ssh flle-tr2 'grep -q RERUN-DONE ~/flle/ch04/rerun-03.log'; do sleep 20; done
```

**这在真实交易系统里也会发生：** 风控上限是硬限制，测量、压测时也会触发。

---

## 结果

### 运行 ①：基线 DEQUE_CV

```text
这一轮能不能用：不能用：好几道门没过
AUTO 有没有自己乱跳：6/8 轮都稳
8 轮交棒最快 29211 ns（29.2 µs），最慢 239610 ns（239.6 µs）；最慢是最快的 8.20 倍（门限 1.50）
先热身 1000 笔，每轮预热 40、计入 400，共 8 轮

原来的格子（独占座位）
  MANUAL 计入 3200 笔
    交棒：47133 ns（47.1 µs）
    发出去到回执：587700 ns（587.7 µs）
    整段：612765 ns（612.8 µs）
  AUTO 计入 640 笔
    交棒：215677 ns（215.7 µs）
    往返中位：198110 ns（198.1 µs）（只看稳不稳）
```

- 交接 p99 = 47.1 µs，但 8 轮之间从 29 跳到 240 µs，相差 8.2 倍（门限 1.5）
- **“交棒”只占整段的 8%**，整段 613 µs 的大头是“发出去到回执”，也就是网络往返

### 运行 ②：deque vs 固定格子

```text
原来的格子 交棒 p99：62233 ns（62.2 µs）   整段 761.9 µs
固定格子   交棒 p99：72577 ns（72.6 µs）   整段 672.6 µs
交棒谁更快：样本读数 原来的格子 少 10.3 µs；结论：本批检查未通过，不能判断谁更快
AUTO 有没有自己乱跳：10/16 轮都稳
```

置信区间 −42.3 ~ +36.8 µs 跨过 0，**分不出快慢**。换存储结构这点差异被噪声淹没了。

### 运行 ③：条件变量 vs 忙轮询（重跑后）

```text
AUTO 有没有自己乱跳：13/16 轮都稳

固定格子（独占座位）    交棒：114141 ns（114.1 µs）  整段：665692 ns（665.7 µs）
盯着看（独占座位）      交棒：2402 ns（2.4 µs）      整段：635769 ns（635.8 µs）

交棒谁更快：盯着看 的 p99 少 111739 ns（111.7 µs）
相邻快慢方向：8/8 对都是同一边更快
```

```text
queue_effect {'difference_ns': 111739, 'ci95': {'low_ns': 72311, 'high_ns': 146151}, 'verdict': 'RIGHT_LOWER'}
total_effect {'difference_ns': 29923, 'ci95': {'low_ns': -10136, 'high_ns': 66034}, 'verdict': 'NO_DETECTED_DIFFERENCE'}
comparison_verdict REJECTED_WITHIN_ROUND_DRIFT
drift pass [True, False, True, True, True, True, False, True, True, True, True, True, False, True, True, True]
```

- **忙轮询把交接从 114 µs 降到 2.4 µs，快了约 47 倍**；置信区间 72 ~ 146 µs 完全在 0 的一边；8/8 对方向一致
- 但整段的差异（30 µs）分不出来：区间 −10 ~ +66 µs 跨过 0，被网络抖动淹没
- 16 轮里有 3 轮 AUTO 前后半段漂移超过 20%，所以课程判定 `REJECTED_WITHIN_ROUND_DRIFT`

### 运行 ④：忙轮询，独占核 vs 共享核

```text
AUTO 有没有自己乱跳：15/16 轮都稳

盯着看（独占座位）     交棒：2292 ns（2.3 µs）     整段：602563 ns（602.6 µs）
盯着看（挤在杂活核）   交棒：42936 ns（42.9 µs）   整段：544837 ns（544.8 µs）

交棒谁更快：盯着看（独占座位） 的 p99 少 40644 ns（40.6 µs）
相邻快慢方向：8/8 对都是同一边更快
MANUAL 独占座位时坐 CPU 2
MANUAL 挤杂活核时坐 CPU 0
```

```text
queue_effect {'difference_ns': -40644, 'ci95': {'low_ns': -44934, 'high_ns': -35620}, 'verdict': 'LEFT_LOWER'}
total_effect {'difference_ns': 57726, 'ci95': {'low_ns': 25616, 'high_ns': 81785}, 'verdict': 'RIGHT_LOWER'}
drift pass [True × 15, False]
```

- 忙轮询线程挤到共享核，交接 p99 从 2.3 涨到 42.9 µs（18 倍）。区间很窄（35.6 ~ 44.9），非常确定
- 整段反而是“共享核”低 58 µs，这是网络噪声，不是真的更快
- 只有 1/16 轮漂移超标，但规则是一轮不过就整批不能用

### 最后恢复

```text
已恢复盯着看，配置名 SPSC_SPIN
MANUAL 下单线程坐在 CPU 2，杂活在 3
AUTO 下单线程坐在 CPU 3，杂活在 3
```

### 汇总

| 运行 | 对比 | 交接 p99 | 差异 95% 区间 | 方向一致 | 课程判定 |
|---|---|---|---|---|---|
| ① | deque + 锁 + 条件变量 | 47.1 µs（轮间 29–240 µs） | — | — | ❌ `REJECTED_MULTIPLE_GATES` |
| ② | deque vs 固定格子 | 62.2 vs 72.6 µs | −42.3 ~ +36.8，分不出 | 不适用 | ❌ `REJECTED_WITHIN_ROUND_DRIFT`（6/16 轮） |
| ③ | 条件变量 vs SPSC 忙轮询 | **114.1 vs 2.4 µs** | +72.3 ~ +146.2 | 8/8 | ❌ `REJECTED_WITHIN_ROUND_DRIFT`（3/16 轮） |
| ④ | 忙轮询 独占 vs 共享核 | **2.3 vs 42.9 µs** | −44.9 ~ −35.6 | 8/8 | ❌ `REJECTED_WITHIN_ROUND_DRIFT`（1/16 轮） |

| | 课程（物理机） | AWS（c7i.xlarge） |
|---|---|---|
| 锁 + 条件变量 | 约 17 µs | 47–114 µs |
| 忙轮询独占核 | 约 6.8 µs | **2.4 µs** |
| 忙轮询挤共享核 | 约 57–65 µs | 42.9 µs |
| 忙轮询快几倍 | 约 2.5 倍 | **约 47 倍** |

## 学到的

1. **在虚拟机里，“睡着等叫醒”特别贵。** 条件变量让线程睡着，vCPU 也跟着空闲，叫醒要经过 hypervisor，一来一回几十到上百微秒。忙轮询线程一直醒着，不受影响。所以在云上忙轮询的优势（47 倍）比物理机（2.5 倍）大得多
2. **忙轮询本身很快：** 2.4 µs 比课程的 6.8 µs 还低，c7i 的 CPU 更新
3. **忙轮询必须独占一个核：** 挤到共享核，要和别的线程轮流用 CPU，p99 涨 18 倍
4. **换队列存储（deque → 固定格子）在这个环境里看不出来：** 噪声远大于差异
5. **整段约 600 µs，基本由网络决定。** 交接省下 100 µs，在整段里被网络抖动淹没。真实系统要先把网络降到微秒级，软件优化才看得出来
6. **为什么课程判定全不通过：** 课程要求 AUTO 每轮前后半段的往返中位数变化不超过 20%，EC2 网络抖动常超过。课程的原则是**宁可判不能用，也不事后放宽门限**。所以本次结论只能当“方向参考”

## 收工：下载数据、改回机型

```bash
# 把 .2 上的整个 ch04 目录打包拉回本机
cd reports/aws-runs; D=20261124T1013Z-04-software; mkdir -p $D
ssh flle-tr2 'cd ~/flle/ch04 && tar -czf - --exclude="*.pyc" .' | tar -xzf - -C $D
ssh flle-tr2 'cd ~/flle/app/tests && diff software_measurement.py software_measurement_aws.py' > $D/aws-patch.diff

# 停程序 → 停机 → 改回 c7i.large
cd ../../apps/flle-trading-lab && bash aws/flle-aws.sh stop
export MSYS_NO_PATHCONV=1 R=ap-northeast-1
aws ec2 stop-instances --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364
aws ec2 wait instance-stopped --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364
aws ec2 modify-instance-attribute --region $R --instance-id i-0872ca5de433c6364 --instance-type '{"Value":"c7i.large"}'
```

## 下次可以试

- 用 **c7i.metal**（裸金属，没有 hypervisor，约 4 美元/小时）重跑，看能否通过环境检查，以及条件变量是否回到 17 µs 左右
- 把 `--stability-limit-pct` 放宽到 40 只做学习用（结论不能和课程比）
- 用 `perf stat -e context-switches,cpu-migrations -p <下单线程PID>` 看条件变量和忙轮询的上下文切换次数差别

## 笔记 / 疑问

（自己补充）
