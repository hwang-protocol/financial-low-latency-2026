# 调度图立体重画与图后说明压缩

日期：2026-09-09；DEC-408；DRAFT / NOT FROZEN。

按用户要求，以仓库原 `00-14-scheduler-core-selection.png` 为视觉参考，原位重画 `00-scheduler-thread-states.svg`。保留候选线程架、彩色标牌、中间选择机构、两块处理器和次要等待区的构图，使用原生SVG路径、渐变、描边与阴影呈现金属、齿轮、面板和引脚；没有把PNG嵌入SVG。

①～③仍以开始执行前等待为主，左侧提示线程已经准备好但需等待安排。④⑤表现执行中的暂停与恢复。中间机械机构为内核调度功能的比喻，正文图注明确其角色；图不规定线程优先级、精确调度队列结构或固定等待时长。

图后说明压为五行短表和两句正文。从说明表起至逻辑CPU编号段前，汉字数由370降为192。可运行、阻塞、恢复、上下文切换和后续观察延迟的含义保留；逻辑CPU与亲和性段落保持。

验证：800/1200像素整图已目视检查；21处文字边界、五编号箭头、统一12×12头部和两端12px间隙通过。正文仍八图，全部代码围栏与历史输出逐字保持，改动只在第4节。13张Markdown表/HTML结构、11章74导航卡、08～10章18执行卡及24图片引用通过；两级SHA24/209项匹配，`git diff --check`通过。详见 [验证收据](evidence/scheduler-industrial-20260909.json)。

无新实验、RUN_ID或设备事实，PINS及坑本无需更新。旧PNG保留为历史资产，前轮报告描述当时版本。

待提交：第零部分正文、调度SVG、两级图册README/SHA、DECISIONS、FREEZE-LEDGER、NEXT-AI-HANDOFF、本报告及收据；工作区其他前轮修改保留。

建议提交说明：`docs: restore dimensional scheduler artwork and tighten explanations`。AI未提交或推送。
