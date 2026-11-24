# 修复01：独立Builder缺少跨章自测依赖

第二章运行①原卡失败于 `.101` make test；test_gui_reset.py向上猜仓库根目录，访问不存在的 /var/Documents/newDoc/assets/07-arista-time/lanz_stream_collector.py。当前部署只复制app目录，首次构建因此失败。

修复：labctl部署时把真实LANZ collector作为tests构建输入一起复制，现有source.sha256覆盖；测试优先读随包输入，仓库内运行仍读权威源。没有跳过失败测试或复制伪造模块。

独立临时app目录（无仓库布局）164项测试完成，8项原有仅完整checkout检查按既有合同跳过；GUI reset测试实际通过。当前正重跑第二章原卡，首次失败回执保留。本轮因此不能称全程zero-edit。
