# Module 1 Experimental Wire Schema Run State

- `RUN_ID`: `20260721T042347Z`
- `PURPOSE`: Module 1 实验性统一金融 wire schema 的软件边界验证
- `PROFILE_ID`: `module1-experimental-wire-schema-v0`
- `STARTED_AT_UTC`: `2026-07-21T04:23:47Z`
- `RESULT_DIR`: `reports/20260721T042347Z-module1-experimental-wire-schema/`
- `STATUS`: `COMPLETED — FUNCTIONAL_PASS_WITH_BOUNDARIES`
- `RUN_CLOSURE`: `CLOSED`
- `FINISHED_AT_UTC`: `2026-07-21T04:28:51Z`
- `RESULT`: `20/20 self-tests PASS; two JSON/CSV/stdout replays byte-identical; monitoring PIDs/HTTP unchanged`
- `REMOTE_CLEANUP`: `/tmp/flle-module1-wire-schema-20260721T042347Z removed; compiler residue 0`

## 范围与边界

- 唯一允许的远端节点是 `10.1.1.101`（`vm-monitor`）。
- 唯一允许的远端写入范围是 `/tmp/flle-module1-wire-schema-20260721T042347Z`；不修改网络、监控服务、systemd、仓库 checkout 或其他主机。
- 该 schema 是 `EXPERIMENTAL v0`，用于课程软件边界验证；不是 FIX、ITCH 或任何交易所协议，也不是生产标准或已冻结课程标准。
- 基线为 Verilator RUN `20260721T034958Z` 已验证的固定 160-bit 字段顺序；本轮只验证 host-side 网络字节序编解码、畸形输入和 sequence 分类。

## Schema v0 合同

- 固定长度：20 octets。
- `magic16=0x4d44`，network byte order。
- `symbol32`：4 个原始 ASCII octets；本 v0 仅接受正好 4 个大写 `A-Z` 或数字 `0-9`，不做 NUL/空格填充或字符集转换。
- `side1+reserved15`：16-bit network-order flags；bit 15 是 side（`0=BUY`, `1=SELL`），bit 14..0 必须为 0。
- `price32`：unsigned network-order transport integer；实验约定单位为 `10^-4` currency unit，语法范围 `0..UINT32_MAX`。
- `qty32`：unsigned network-order transport integer，单位为 whole units，语法范围 `0..UINT32_MAX`。
- `seq32`：unsigned network-order session-local sequence；v0 不定义 wrap-around。
- 业务层对零价格/零数量的限制不属于本轮 wire codec。

## 验收与恢复点

- C++ reference codec 至少覆盖 round-trip、big-endian golden bytes、bad magic、reserved 非零、API invalid side、短/长帧、sequence gap/duplicate/backward 与 price/qty 边界。
- 至少执行两次独立确定性 replay，并对 JSON/CSV 逐字节比较及 SHA-256。
- 运行前后 Prometheus、node exporter、Grafana、Loki 的 MainPID 与四个本地 HTTP health 状态不变。
- 失败尝试不得删除；若没有失败，attempt ledger 明确记录 `failed_attempts=0`，不制造失败。
- 完成归档和校验后删除精确远端临时目录，并将本状态改为 `COMPLETED` 或真实失败状态。

## 完成证据

- 最终报告：`reports/20260721T042347Z-module1-experimental-wire-schema/report.md`
- 机器结果：`raw/vm-monitor/replay1/results.json`、`results.csv` 及独立 replay2。
- runner 内部 build/self-test/gate 无失败；另保留一次只读后置审计 `jq` 缺失的 `rc=127` 失败，重试使用现有工具 PASS。
- 未更新 PINS、FREEZE 或 DECISIONS；schema 仍为未冻结的 `EXPERIMENTAL v0`。
