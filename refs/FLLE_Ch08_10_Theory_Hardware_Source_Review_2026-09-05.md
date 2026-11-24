# 第08～10章理论与真实 FPGA 路线资料复核

> 2026-09-05 更新：第08章现役位置已由 DEC-333 改到 `.2 X2522/sfc/native XDP`；本文旧 `.11` 路径/旧 RUN 只保留原轮事实。当前三章接收位置与13入口连续验收见 [客户端主线与重刷报告](FLLE_Ch08_10_Receiver_First_Topology_2026-09-05.md)。原资料复核、真实 FPGA 未实测边界和图文来源仍有效。

> 日期：2026-09-05 · DEC-327 初稿 / DEC-328 评估收口 / DEC-329 课件配图 / DEC-330 map 身份图 · DOC/FIGURE-ONLY · NOT FROZEN
> 范围：课程教学设计与本地静态验证。没有实体 7130/U250，没有执行部署、烧录或性能实验，没有新 RUN。

## 教学约定

- 受众是网络工程师，系统/硬件术语就近用中文解释；先讲工作原理，再进入原有软件实验。
- 假设已经拿到真机，按真实顺序讲资料、配置、开发、镜像、规则、验收和回退；不增加绿色操作卡，不伪造操作输出。
- 同一任务保持 Type A + Locate 8095 + 完整 `NVDA    ` + 一次性额度 1。8095 只对应固定行情数据集。
- P4 是语言，BMv2 是软件执行平台；选择 Arista OpenFDK RTL 路线不意味着该硬件天然支持 P4。

## 一手资料与关键核验

| 资料 | 复核到的事实 | 正文如何使用 |
| --- | --- | --- |
| [Linux verifier](https://docs.kernel.org/bpf/verifier.html)、[Cilium BPF 参考](https://docs.cilium.io/en/latest/reference-guides/bpf/index.html) | 类型/指针/控制流检查、装载与执行分离 | 第08章解释 verifier、JIT、map；不把内存安全说成协议正确 |
| [P4-16 v1.2.4](https://p4.org/wp-content/uploads/sites/53/p4-spec/docs/P4-16-v1.2.4.html) | 语言与架构/target 分离，状态操作原子性有目标约束 | 第09章先定义语言工位；沿用 DEC-326 的 BMv2 证据边界 |
| [OpenFDK null](https://github.com/aristanetworks/openfdk/tree/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/null) | `BOARDSTD=l` 支持 DCS-7130-48L/96L 与 XCVU7P；示例列 EOS 最低 4.28.0F | 假设 48L + EOS；最低版本不是所有应用的兼容保证 |
| [null EOS daemon](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/null/src/eos/NullExampleDaemon.py) | 枚举兼容 FPGA，选板型 bit，经 `fpga.load_image()` 装载并读寄存器 | null 只检验装载/管理；不是 MAC 透传或业务过滤器 |
| [EOS 扩展](https://www.arista.com/en/um-eos/eos-managing-eos-extensions)、[7130 L1](https://www.arista.com/en/um-eos/eos-configuring-layer-1-on-the-7130-platform) | 安装与启动保留分开；L1 在目的接口指定 source | 包安装、镜像装载、原帧导流分层；不杜撰 Application 编号 |
| [OpenNIC Shell 固定版本](https://github.com/Xilinx/open-nic-shell/tree/940907fc99fc8d73dbea0028b3a23095a660a42a) | U250 支持；默认 100G；CMAC 322 MHz、用户区 250 MHz；RX 整包 FIFO 恢复反压；低字节先映射 | 先独立 100G 台架；拟将过滤器接于 RX 用户区与 QDMA 之间 |
| [OpenNIC Driver 固定版本](https://github.com/Xilinx/open-nic-driver/tree/3de226996ff5bacf8c4bdcec5318725e39c80b23) | `onic` 驱动、shell/QDMA 版本依赖；链路先就绪再加载驱动 | 先验证默认 NIC 路径，再加业务逻辑 |
| [UG1289 U200/U250 配置章节](https://docs.amd.com/r/en-US/ug1289-u200-u250-reconfig-accel/MCS-File-Generation-and-Alveo-Card-Programming) | v1.1：spix4 / 128 MB、用户镜像起点 `0x01002000`、保护区到 `0x01001FFF`、指定配置器件、Configuration File Only、断开 JTAG 后冷启动 | 第10章讲 JTAG 与 Flash 两条流程；只在实卡板版和手册一致时采用该布局 |
| [Vivado UG908](https://docs.amd.com/r/2025.1-English/ug908-vivado-programming-debugging/Programming-a-Configuration-Memory-Device) | 配置存储器件的选择、Program/Verify | 解释限定镜像区域与验证，避免全片擦除 |
| [Verilator overview](https://verilator.org/guide/latest/overview.html) | 生成可在 CPU 执行的模型 | 软件周期功能通过不替代综合、时序与板上验证 |

OpenFDK 固定 revision 为 `13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d`；OpenNIC Shell/Driver revision 如表。公开文档、固定代码和设备专属交付包仍须共同核对；本轮未领取、安装或验证本例所需的 IP 许可，也未取得硬件恢复包。

## 评估后补充复核（DEC-328）

| 建议 | 本次一手复核 | 处理与状态 |
| --- | --- | --- |
| 硬件各步的未实测标识 | 09 六步、10 八步均无板上 RUN | 14 个步骤标题逐个加“设计／未实测”；硬件图前统一同类紫色图注，不新增绿色卡 |
| 100G 与 10G 接入取舍 | 固定 OpenNIC 是 CMAC 100G 路线；[PG210](https://docs.amd.com/r/4.1-English/pg210-25g-ethernet)是另一套 10G/25G 子系统 | 明写本例另配 Exchange 侧 100G NIC/主机、绕过 7150；保留原 10G 拓扑需新 shell 适配，仍待开发和板验 |
| CMAC 许可 | [README / CMAC license](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md#cmac-license)列出 UltraScale+ Integrated 100G Ethernet No Charge License，以及 bitstream generation is not permitted 类错误 | 免费许可也要领取并被工具识别；缺许可阻止镜像生成，不笼统断言必在综合阶段失败；补许可后需重置/重新生成 IP 输出 |
| null EOS 启停出处 | [`examples/null/src/eos/NullExample.yaml`](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/null/src/eos/NullExample.yaml)定义 null 模式、disabled/noSyntax 和 show null status；[`NullExampleCli.py`](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/null/src/eos/NullExampleCli.py)中 DisabledCmd.handler/noHandler 调用 disable/enable，ShowNullStatusCmd 渲染 appName | 命令保留并附源码链接；这里只是定义复核，不是 EOS 实跑回执 |
| 官方重配脚本 | [`setup_device.sh`](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/script/setup_device.sh)固定补 0000 域，改上游桥错误上报，等待 c 再重扫；[`program_fpga.sh`](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/script/program_fpga.sh)消费完整 BDF 环境变量并调用同目录 Tcl | 正文点名路径、参数、执行主机与影响；先审阅适配，不把上游脚本当已验安全入口，不复制执行 |
| PCIe 异常边界 | README / Programming FPGA 记录 Dell/iDRAC 强制重启、已加载 onic 重扫可挂内核、无 BDF 时 setup 不适用、首次直接配置后暖重启 | 明确停流、释放驱动/VM、独立 JTAG 和带外管理；未复用 Dell 临时双重重启 workaround 作为通用流程 |
| Flash 布局的证据等级 | 本轮成功读取 [UG1289 v1.1 原页](https://docs.amd.com/r/en-US/ug1289-u200-u250-reconfig-accel/MCS-File-Generation-and-Alveo-Card-Programming)（2023-06-13）：参数表确认 spix4、128、0x01002000；操作步骤确认 mt25qu01g-spi-x1_x2_x4 与 Configuration File Only | 官方参数已在线复核，不降为“凭记忆”；实卡板版、Flash、启动配置、恢复区及镜像适用性仍“待人工核对”，烧录仍未实测 |

其它收口：三章统一“第08/09/10章”称呼，第08章内核/用户态/map 定义前移；准备 A 与运行①～④补预期读数及估计耗时；三章开头提示回归普通段落。图片文件未改，21 个引用与 11 个 SVG 保持上一轮内容；只调整正文图注。

## 设计推导，不是已实现硬件

DEC-329 仅调整第08章入门图解，不改变以下硬件设计。

现役 `market_filter.sv` 只接收 288-bit ITCH 与独立 Sequence，输出单周期 verdict；它没有原帧出口、FIFO、BAR、CDC、Session 审计或硬件期限。新 wrapper 必须补齐这些职责，不能把现役 `.sv` 单独转换为可收发的网卡镜像。

固定无 tag 报文为 100 B（不含 FCS），ITCH 从偏移 64 开始，Stock 在 88–95。512-bit 接口每拍最多 64 B，第二拍才能认全 Stock；第一版选择先存整帧再裁决，保证 DROP 不泄漏首拍。源/组/端口、IP/UDP/Mold 长度和有效封装也由 wrapper 校验。

共享额度、shadow/active 提交、跨时钟配置握手、审计快照与 5 秒硬件撤销均是拟建合同；寄存器地址和 Arista 新应用 CLI 尚未生成。P4-to-FPGA 后端不在已验证路线中。

## 本轮验证

| 检查 | 结果 |
| --- | --- |
| 新增 SVG | DEC-327 的 11 张仍在；DEC-330 另增 `08-what-is-a-map.svg`。XML 可解析，1200/800 px 带 Noto 审图 |
| 正文图引用 | DEC-330 后 08/09/10 为 11/8/5，全部本地路径存在 |
| 导航 / 任务地图 | 7/7/6，位置、组名、知识句和当前标签逐字一致 |
| 既有绿色卡 | 6/3/1，数量不变；硬件推演无新增绿色操作卡 |
| 命令、源码摘录、原始输出 | 与修改前 HEAD 的所有非 Mermaid 围栏逐字一致；仅新增教学用行内参数说明 |
| 文件完整性 | DEC-330 后中央图摘要 171 项；局部 13/9/8 项（含 README），全部复算通过 |
| Markdown/HTML | div/span 平衡、围栏成对、`git diff --check` 通过 |
| 在线与硬件验证 | 本轮未执行；DEC-325/326 既有 RUN 与终态证据未改变 |

仍待：取得实卡 SKU/板版/FDK/IP/工具许可与恢复资料；开发两个板级 wrapper 和管理端；独立台架完成综合、时序、装载、单包 GAP、恢复、冷启动与性能验证。不能把本报告标为 HARDWARE PASS。

## 旧课件配图吸收（DEC-329）

用户提供 `Documents/newDoc/19.eBPF.pptx`（7页，SHA=`a69fd93245053c6fce3a3858c9a73e121f6cf856ea25fcf3fde640f05a20893d`），要求参考图文且克制理论篇幅。已读取全部幻灯片文本与图片关系，并检查第3～7页六张知识图；只提取三张原图，不改 PPT，不访问内部项目地址或执行附件内容。

| 来源 | 本章用法 | 读图边界 |
| --- | --- | --- |
| 第4页 `ppt/media/image111.png` | 开篇应用/内核/硬件分层 | 聚焦右侧网络列，不新增存储专题 |
| 第6页 `ppt/media/image114.png` | 运行①的事件/Hook 概览 | 各处小蜜蜂代表能力位置；本课仍为主机 CPU 上的 native XDP |
| 第7页 `ppt/media/image115.png` | 替换旧 `08-11-verifier-load-gate.png` 的正文引用 | 右侧为通用 hook 而非 XDP；approved 不等于业务正确或无缺陷保证 |

课件公开参考 [eBPF.io 入门](https://ebpf.io/what-is-ebpf/)已在线复核。用两张新增图和一张替换图配短中文提示，压缩原四行角色表与重复说明；没有新增导航、绿色卡或实验。生态项目图、纯文字图、execve 代码图不进入主线。

三 PNG 与 PPT 内 media 逐字节一致，原尺寸分别 1212×712、1230×705、1237×523；原尺寸及 800 px 预览均目视通过。PPT SHA 不变，旧 PNG 留盘，09/10 正文 SHA 不变；本轮全部代码/输出/Mermaid 围栏逐字不变，图册与摘要同步。

## map 身份图（DEC-330）

用户指出章首突然出现 “map 是程序与用户态共享规则、额度和计数的数据表”，缺少对象关系。处理：开场不再先抛术语；分层图后引用 [Linux BPF maps](https://docs.kernel.org/bpf/maps.html) 的 generic storage 原文，并新增 `08-what-is-a-map.svg`。图只画用户态写规则/读计数、内核键值表、XDP 查表判决；包路径用实线，查表用紫色虚线。运行 ⑤ 的 one-shot 图保持原职责。无新绿色卡、无设备操作。

## 软件模拟与真卡接入复审（DEC-334）

2026-09-05 重新在线读取固定版本 [OpenNIC Driver README](https://github.com/Xilinx/open-nic-driver/blob/3de226996ff5bacf8c4bdcec5318725e39c80b23/README.md#building-the-driver) 和 [OpenNIC Shell README](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md)。前者明确make生成onic.ko、链路先就绪再装驱动、检查dmesg与新netdev；后者仍是100G shell。没有因此认定当前sfc课程控制器支持onic，也没有硬件操作。

本地对应源码：`assets/common/feed-guardianctl.sh` 的direct/unicast-only分别启用/关闭组播，并断言SFC/READY/sfc；`assets/10-verilator/mold_filter_adapter.cpp` 在allow初始化额度0，block才装1；既有024538Z的adapter.log确认相同读数。真卡第八步的IP/netdev/profile/组播迁移表是据此提出的接入设计，尚无实现或板上验证。

图文清楚区分软件模型在socket后、真卡在DMA前；原09六步与10八步均保留设计/未实测标签。用户没有真卡，课程不新增烧录绿卡，仍讲查资料→默认PASS工程→集成过滤→构建→临时装载→持久配置→同一业务验收。现场验证继续引用DEC-333，不冒称本轮重跑。
