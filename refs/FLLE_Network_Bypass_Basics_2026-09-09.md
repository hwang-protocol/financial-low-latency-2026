# 收包过程与OpenOnload对照图

2026-09-09；DEC-410；DRAFT / NOT FROZEN。

第零部分第5节改为普通收包与OpenOnload上下对照：沿报文写入主内存、通知与取包、协议处理、应用读取讲解。用户要求简化缩写，并进一步强调不能省掉必要过程；最终图在内核框中展开驱动批量取包、网络栈和套接字接收队列，在应用进程框中展开Onload库与业务线程，附库加载、主动查看/等待事件和内核支持。八条编号箭头与八行短表对应，正文解释③与⑥的变化。

第6节同步换为内存、通知与CPU的概要SVG，删除旧图及正文中在此阶段不再展开的接收描述符等细节。NAPI、softirq、MSI-X、RSS等扩展入口移至教师说明，后续章节已有的解释与实验保持。正文导航、理解检查与官方来源同步；原两PNG保留历史，六处其他图标签不变，全章仍八图。

## 依据与边界

- [AMD：普通路径与Onload对照](https://docs.amd.com/r/en-US/ug1586-onload-user/Contrasting-with-Conventional-Networking)：库可访问分配给它的网卡资源，协议处理在用户态进行。
- [AMD：透明接入](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency)：库接手套接字调用，未加速调用仍可走内核。
- [AMD：性能机制](https://docs.amd.com/r/en-US/ug1586-onload-user/How-Onload-Increases-Performance)：减少用户/内核交接，收包可轮询或等待。
- [OpenOnload源码项目](https://github.com/Xilinx-CNS/onload)：用户态协议库、支持内核模块及X2522接口；本轮未升级软件。
- [Linux NAPI](https://docs.kernel.org/networking/napi.html)：普通路径中通知与批量收包的职责。

图为处理关系示意，内存先接收报文字节；箭头不规定逐步复制次数或完整硬件时序。Onload库位于应用进程内，不代表独立服务、全部协议由网卡处理或完全无需内核；图内保留资源管理和未加速路径。没有保证性能收益，没有新增中断频率或延迟数字。

## 验证

两图XML及自包含矢量结构通过；800/1200像素预览已检查。对照图1600×1660、44处文字、八箭头；概要图1200×690、13处文字、三箭头。共57文字边界通过，箭头固定12×12头部、3px线宽、两端12px间隙。全章12张Markdown表/HTML结构通过，八图文件存在，实验代码围栏及历史输出与本轮修改前逐字一致。

`verify-filter-course-cards.py`通过11章74卡，以及08～10章18执行卡、24图片引用。两级SHA清单26/211项匹配；`git diff --check`通过。见[验证收据](evidence/network-bypass-basics-20260909.json)。无实机实验、设备配置、性能重采或新RUN；无新增PINS及坑本项。

## 待提交

本轮涉及第零部分正文、教师说明、两张新SVG、两级图册README/SHA、DECISIONS、FREEZE-LEDGER、NEXT-AI-HANDOFF、本报告与收据。此前工作区改动保持，最终提交由用户完成。

建议提交说明：`docs: explain receive paths with OpenOnload comparison diagrams`。AI未提交或推送。
