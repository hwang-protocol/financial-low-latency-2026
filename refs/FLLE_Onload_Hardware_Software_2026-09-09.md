# OpenOnload硬件与软件分工补图

2026-09-09；DEC-412；DRAFT / NOT FROZEN。

用户追问旁路段仅有文字，以及协议处理代码位于网卡还是应用进程。本轮在第5节补独立分工SVG：左边网卡硬件负责报文收发、队列分发和DMA写内存；右边是CPU执行的软件，以普通内核协议栈作位置参照，Onload库和业务代码同属应用进程。两条独立编号箭头配两行表，主机内存与内核/驱动资源支持明确保留。普通收包主图、RSS高级延伸与四等待点图保持。

[AMD Onload Transparency](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency)明确用户态库实现协议处理、接手Socket调用；[OpenOnload官方项目](https://github.com/Xilinx-CNS/onload)说明用户态共享库与支持内核模块的组成。这里解释受支持加速路径，不将全部协议工作描述为只在用户态完成，不把TCP完整卸载到网卡。图中箭头表达处理关系，报文仍在主机内存；不刻画DMA一致性、复制次数或详细调用时序。型号、启动命令和完整性能对照留第六部分。

验证：1200×920原生平面SVG，800/1200目视、18文字边界、两箭头固定12×12头部和两端12px间隙通过。全章15表及HTML结构通过；新增一图后全文10图，之前九个img标签、实验代码和历史输出逐字保持。导航检查11章74卡及08～10章18执行卡/24图片引用通过；两级SHA29/214项匹配，git diff空白检查通过。[验证收据](evidence/onload-hardware-software-20260909.json)。

无实机操作、设备配置、重采或新RUN，无新增PINS/坑本项。待提交：正文、教师说明、新SVG、两级README/SHA、DECISIONS/FREEZE-LEDGER/NEXT-AI-HANDOFF、本报告与收据。前轮改动保持，AI未提交或推送。

建议提交说明：`docs: illustrate Onload hardware and software roles`。
