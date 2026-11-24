# 第02章：一次部署完整交易平台

1. `00a-runtime-prep.sh`：在 .1/.2 安装、加载并核对 Onload 运行依赖。
2. `00b-iommu-prep.sh`：按需准备 IOMMU 并重启两端，核对安全隔离；已经符合条件不重启。
3. `01-restore-trading-lab.sh`：从 .111 分发完整固定运行包，在 .101 构建当前原生客户端与完整网页；默认启动 AUTO、MANUAL 和两条加速客户端，三条路径均可下单。保存唯一 `02-trading-baseline.env`，重复执行核验同一平台。
4. `02-first-trade.sh`：在行情继续、策略保持原样时，按订单身份核对一笔 AAPL 1 股纸面 IOC。

第二章备齐普通客户端、三个加速后端、GUI/controller 与 Feed Guardian 能力。后续切换 SOFTWARE/TRANSPORT 配置、调整订阅或接入过滤程序，均不得重新编译交易客户端或替换网页。

部署中断会保留 `.pending` 身份；重贴入口先尝试按精确 RUN 清理，再创建新的部署证据，清理失败立即停止。课堂正常停顿没有跨步骤倒计时。

固定路径运行包仍保留 v12 原始构建与 SHA 证据；它与当前原生客户端共同组成平台，不能描述成全部路径使用同一 ELF。

准备A在本机与目标机加互斥锁；只有网口配置或模块摘要变化才重建initramfs，失败不写完成标记。准备B的锁/备份属于ch02。首单入口按SOFTWARE/TRANSPORT当前配置核验，SFC/READY、健康行情与盘口齐备才下单，不要求TRANSPORT中暂停的AUTO在线，也不自动切配置。

离线回归：`python3 Documents/newDoc/assets/02-trading-baseline/test-iommu-prep.py` 和 `test-preparation-contracts.py`（同目录）；后者验证重复准备、失败后重试、只读卡失败留证和两种下单配置门。
