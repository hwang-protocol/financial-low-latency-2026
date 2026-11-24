# 第07章 fresh-live 支撑文件

这里保存第07章 fresh-live 教师入口所需的程序、配置和解析器。运行脚本只能从这个 tracked 目录取代码；`reports/` 只保存运行证据，不能作为源码仓库。

- `lanz/` 的 5 个文件逐字节迁自已验证 RUN `20260721T053935Z-arista-lanz-lower-trigger-boundary/commands/`。
- `ptp/` 的 6 个文件源自已验证 RUN `20260721T024157Z-x2522-ptp-hwts-smoke/commands/`；当前节点 guard 已增加 procfs 内容与 FLLE 交易进程安全门，不再声称其字节与旧 RUN 完全相同。
- `qos/` 保存教师现场 C2 的双口共享出口背景流发生器；它是本课新写的可复现实验代码，不是从旧报告目录搬来的结果。
- `oneway/` 保存历史旁支 `11-oneway-latency-live.sh` 的两端网卡硬件戳对照程序。本实验台 `.1` / `.2` 共一块双口 X2522，那组数字不是独立钟的 PTP 证据，不能当第三幕主线。
- `stamped-span/` 保存第三幕教师现场：真实行情 SPAN 副本、7150 入口戳、`.2` PHC RX，以及 `.2` 跟随 7150 的 PTP slave 配置。
- `../LIVE-SUPPORT-SHA256SUMS` 当前锁定全部 tracked 依赖；使用该清单的入口都在外部动作之前执行 `sha256sum -c`，并把清单副本及其 SHA-256 写进本次新 RUN。

迁移保留的是经过现场验证的程序字节，不是历史测量结果；新增目录同样只放生成器和解析器。每次运行仍生成新的 RUN_ID、流量、pcap、设备转录和结果文件。
