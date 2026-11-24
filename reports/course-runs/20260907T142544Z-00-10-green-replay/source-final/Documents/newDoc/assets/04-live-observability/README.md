# 第四章当前主线资产

本目录只承载在线 Trading Lab 的真实观测主线：宿主机恢复 Prometheus/Grafana、采集固定 50 Hz 的 C++ OUCH RTT raw sample、查询 Prometheus。学生运行 ③ 是打开驾驶舱 URL。旧 `assets/04-observability/` 的 Python 构造样本、Compose、Loki 三态脚本继续保留历史审计，但不再进入当前正文。

| 文件 | 职责 |
| --- | --- |
| `00-restore-observability.sh` | 从持久`.111`管理机的固定deb恢复全新`.101`宿主机Prometheus 2.31.2与Grafana 13.1.0 |
| `01-capture-order-rtt-baseline.sh` | 在行情和 AUTO 策略继续运行时，以 20 warmup + 200 measured、20 ms 间隔采集 MANUAL C++ RTT |
| `02-query-prometheus.sh` | 校验 `/metrics` exposition，并查询 target、MANUAL p99 与实时行情速率 |
| `03-verify-grafana-dashboard.sh` | 教师/审计：health、UID 与 HTTP 200。学生正文运行 ③ 改为打开 URL 读截图，不再粘贴本脚本 |

正文内联三段学生 shell（准备 A / 运行 ① / 运行 ②），资产副本必须与正文逐字一致。运行 ③ 是浏览器人工卡。Python helper 与宿主机恢复 helper 属于预置工程件。
