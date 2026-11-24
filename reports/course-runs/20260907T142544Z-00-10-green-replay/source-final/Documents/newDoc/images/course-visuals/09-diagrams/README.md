# 第09章现役机制图

> 更新：2026-09-06 · DEC-359 · DOC/SOURCE-REVIEW

面向网络工程师：图先讲位置、流向与职责，正文就近解释系统和硬件术语。新增 SVG 是教学机制图/硬件设计图，不是实测截图。

| 文件 | 用途与边界 |
| --- | --- |
| `09-asic-p4-fpga-programmability.svg` / `.png` | 章首主图：同色灰框表示既有硬件资源，紫色表示可改内容；传统 ASIC 配已有规则、P4 ASIC 编写专用单元处理逻辑、FPGA 配置资源功能与选通连接 |
| `09-p4-software-and-hardware-targets.svg` / `.png` | 章首执行平台图：P4 源码分别经过对应工具编译，交给 BMv2 的 CPU 或 Tofino 的 ASIC；虚线编译装载、实线报文，两个平台不是串联路径 |
| `09-09-v1model-pipeline.png` | v1model 流水线 |
| `09-13-match-action-contract.png` | 历史参考，已撤正文：通用查表图不足以解释本课NVDA五字段策略；图中的默认drop不适用于market_policy |
| `09-17-link-local-guard.png` | 历史参考，已撤正文：漏普通组播分支，多画本课源码没有的miss counter；勿作为现役流程图复用 |
| `09-20-bmv2-common-object.png` | 历史参考，已撤正文：原双臂共享进程图混入当前开场不需要的控制字典 |
| `09-25-p4info-runtime-dictionary.png` | 历史参考，已撤正文：独立 P4Runtime 控制字典教学分支 |
| `09-p4-language-and-target.svg` | 运行①三环节图标：读字段、决定去向、输出字节；下方放大同包头部输出与载荷保留，1200×900，正文表格同序 |
| `09-bmv2-process-and-ports.svg` | 运行②：`.11`虚拟机里的BMv2进程、双直通网口与同一7150两侧VLAN，1200×890；图示运行②接流后的路径 |
| `09-vlan-three-paths.svg` | 同一7150的三种路径：原VLAN20直通、未隔离开桥的错误示意、分成100/200后必经BMv2；1200×1260，正文直接用SVG |
| `09-arista-fpga-path.svg` | Netnod 7130-48LB安装/装载总图，1200×1750；定位源码、设备存储、CPU管理调用、FPGA电路与真实报文 |
| `09-arista-hardware-journey.svg` | 历史推演图，已撤正文；保留资产，不当作可部署过滤工程 |

本目录保存 14 个图片文件；正文实际引用 7 张（3 PNG + 4 SVG）。两张新图保留 SVG 可编辑源，正文使用同源 PNG。主图 SVG 为 1200×1410、PNG 为 1600×1880；执行平台图 SVG 为 1200×650、PNG 为 1600×867。摘要见本目录及上级 `SHA256SUMS`。

## 新图的教学约束与来源（2026-09-06）

- 主图比较可编程范围，不是性能排名，也不是芯片真实布局。传统 ASIC 一行只是已有 IP/ACL 功能示例，具体型号还可能提供其它字段能力。P4 一行画编译器将程序映射到既有专用资源，不把 P4 缩成只更新表项，也不暗示任意重接物理电路。
- FPGA 两幅小图保留相同资源格子的位置，每格代表一组基础逻辑资源；紫色功能与连接发生变化。串行/并行仅示意组织方式，省略时钟、缓存与完整数据/结果传递，不是可综合工程或延迟结论。金属线路、资源容量和可选互连仍是预制的。
- P4 是语言，也可以有 FPGA 后端；主图第二行专指 P4 可编程 ASIC，不把它推广为所有 P4 target。第二张图比较两种执行平台，迁移需适配源码、架构和资源限制；BMv2 的 JSON 不作为硬件制品。
- 物理控制路径的事实仍保留在 PINS 与既有 RUN 中：`.11 simple_switch + Thrift simple_switch_CLI`。按用户要求，独立 P4Runtime 练习及“没有用它”的否定说明撤出学生正文，旧图/脚本/证据保留原路径。

| 官方来源 | 本轮核对的内容 |
| --- | --- |
| [P4-16 v1.2.4](https://p4.org/wp-content/uploads/sites/53/p4-spec/docs/P4-16-v1.2.4.html) | P4 的数据面语言定位及目标架构约束 |
| [Intel Tofino](https://www.intel.com/content/www/us/en/products/details/network-io/programmable-ethernet-switch.html) | 多条流水线与 Match Action Units；可编程 ASIC 的既有资源 |
| [AMD UG1291 FPGA Architecture](https://docs.amd.com/r/en-US/ug1291-viv/FPGA-Architecture) | FPGA 的逻辑单元与互连 |
| [BMv2 upstream](https://github.com/p4lang/behavioral-model) | JSON 驱动的软件参考交换机、开发测试定位 |
| [P4 Studio](https://github.com/p4lang/open-p4studio) | Tofino 编译环境与硬件所需 BSP、SerDes 驱动的分工；开源树不等于全部真机依赖齐全 |
| [APS Networks 产品页](https://www.aps-networks.com/products/) | 基于 Tofino 的物理可编程交换机实例；未核供货、报价或本课采购适用性 |
| [Cisco Silicon One 架构](https://www.cisco.com/c/en/us/solutions/collateral/silicon-one/silicon-one-foundation-success-wp.html) | 从 P4 到芯片制品、SDK 与 NOS 的分层；不代表任意 Cisco 成品开放用户装载 |

## 重渲染与检查

使用 resvg 0.47.0，显式加载 Noto Sans CJK SC Regular/Bold；先渲染 800 px 正文宽度与 1200 px 原尺寸审图，再生成 1600 px PNG。示例中的路径指向维护者实际准备的工具与字体，勿依赖某轮 `/tmp`：

```bash
"$RESVG_BIN" --skip-system-fonts \
  --use-font-file "$CJK_REGULAR_FONT" --use-font-file "$CJK_BOLD_FONT" \
  -w 1600 09-asic-p4-fpga-programmability.svg 09-asic-p4-fpga-programmability.png
```

将输入输出文件名换成 `09-p4-software-and-hardware-targets` 可生成第二图。检查文字出框、连线端点、串并行连接、正文图框、7 项导航、7 张运行卡与源脚本一致性，再更新局部和中央 SHA。无现场部署、性能测试或新 RUN。

原 DEC-275 删除的失真旧协议/接口/RUN 图不恢复；本轮不删除既有图片。

## DEC-352：准备A流程图精简（2026-09-06）

原SVG路径内重画，使用原生矢量报文块、放大镜、规则卡、分流与拼接图形，正文仍引用SVG；目录和正文图片数不变。三环节为教学简化，排队、出口处理和校验块在图中注明省略。下部Mold/ITCH是字段组示意，包含本课消息长度/类型等声明；保留载荷可能为空，不代表每个Type A报文还有额外业务载荷。图中放行字节保持原样，不作为实测截图或性能结论。

来源核对：[BMv2 deparser.cpp](https://github.com/p4lang/behavioral-model/blob/main/src/bm_sim/deparser.cpp)的有效头部尺寸、prepend与顺序输出；[simple_switch说明](https://github.com/p4lang/behavioral-model/blob/main/docs/simple_switch.md)的处理顺序与emit限制；本课`assets/09-p4/trading_bridge_nvda_drop.p4`的DeparserImpl顺序与空Egress/校验块。2026-09-06只读核对。使用上文resvg和字体参数生成800px临时预览，图中文字与连线目视通过；代码围栏不变、运行卡/引用、加粗解析及双层摘要通过。

DEC-352 措辞补正：用户指出放行包内容未改，“写回”容易暗示修改。图表第三环节改为“输出字节”，说明BMv2内部的header字段与剩余字节表示；字段值和emit顺序不变，输出内容可不变。追加核对上游[parser.cpp](https://github.com/p4lang/behavioral-model/blob/main/src/bm_sim/parser.cpp)的extract与`pkt->remove(bytes_parsed)`，对应deparser的prepend/输出。此说明限定BMv2软件实现，不据此断言硬件必然复制整个报文。800px审图、加粗/围栏不变和双层摘要/diff通过。

## DEC-353：进程与真实网口（2026-09-06）

`09-bmv2-process-and-ports.svg`采用原生矢量终端、网口和程序窗口；全图只画一台7150，内部划分VLAN100/200，中间红叉表示两域在7150上不直接互通。蓝/绿实线展示行情前向链路，反向路径相反；紫色虚线是`.11`本地CLI与simple_switch之间的Thrift9090。JSON只画进程已加载，避免再展开编译路径。正文当前准备B只安装工具，此图预览运行②接流后的形态。

证据：PINS中2026-08-31双PF PCI passthrough与2026-09-05接口/Et11/Et12身份；现役`assets/09-p4/live-support/run-trading-p4-drop-live.sh`的两条`--interface`参数、JSON与9090；[BMv2 README](https://github.com/p4lang/behavioral-model#running-your-p4-program)的接口对应/CLI说明。仅核对仓库事实和上游文档，未重跑设备。800px带Noto字体目视、原执行围栏、运行卡/引用、加粗和导航通过；SVG为可编辑源，正文原生引用。

## DEC-355：策略改为简述与关键代码（2026-09-06）

按用户最终范围，正文用原market_policy声明、实际CLI装表值及额度动作节选讲清策略。撤09-13/09-17两张PNG正文引用，旧文件保留；本轮不新增图形资产。现役图片数7、目录图片文件13。来源是`assets/09-p4/trading_bridge_nvda_drop.p4`和当前184行live-support脚本；[P4规范默认动作定义](https://p4.org/wp-content/uploads/sites/53/p4-spec/docs/P4-16-v1.2.4.html)确认未命中执行各表声明的default_action，并不统一等于drop。源码NoAction仍会继续后续转发判断。


## DEC-356：三态VLAN接流图（2026-09-06）

`09-vlan-three-paths.svg` 原生绘制主机屏幕、网口、检查站与成环图标；每行只画同一台7150，网线/主机IP不变。蓝色原直通道、橙色错误接法、蓝绿两侧隔离路径；“大厅隔成两间房，中间只留检查站”解释必须经过P4。第二行仅为错误拓扑示意，不执行，也不声称某种STP行为已实测。源为本章isolate-tools/cut-endpoints计划与040223Z/041235Z物理回执中的端口分组；原生SVG在800px显式Noto字体渲染审图。

运行②最终为4个独立前台脚本，用户已否定35张逐命令微卡。正文全章7张执行卡、8图；实际配置/查看通过，完整验证边界见TEACHER-LIVE-NOTES.md。此图是机制图，不是设备截图；不从BMv2软件实验外推ASIC性能。


## DEC-357：采用有实际部署依据的 Netnod Arista 案例（2026-09-06）

用户接受其它具体FPGA交换机应用，优先Arista。撤48L假设过滤工程及null装载教学，正文改7130-48LB/MOS上的NTP服务；固定主仓库04c89fd2与NTS子模块3d621125，按实际build.sh采用FDK2.5.0，README的旧2.0.0beta1不作现役构建版本。来源、代码与依赖详见assets/09-p4/ARISTA-HARDWARE-NOTES.md。

原09-arista-fpga-path.svg路径内重画。上方CPU软件过滤为现役7150/BMv2路径，图中仅画行情前向；下方单口ap1 RX/TX连接Et1，FPGA识别NTP、填时间、回复同一测试主机。箭头蓝请求/绿回复，紫色虚线制品装载，橙色PPS。省略实际时钟校准连接细节，底部注明MOS+tscore；不把NTP输出当透明转发，也不画未经源码与资料确认的第二端口。

撤旧journey正文引用但保留文件；正文7图（3PNG+4SVG），目录14图片文件，导航7项、绿色运行卡7张不变。800px显式Noto字体渲染审图、源码节选/卡片/链接/加粗/摘要检查；无Vivado构建、设备执行或本课硬件复现。


## DEC-358：安装包怎样变成 FPGA 电路（2026-09-06）

原`09-arista-fpga-path.svg`重画为单张加载总图：开发机Vivado生成bit、Python管理代码随包交付；MOS安装到设备存储，应用模式no shutdown沿真实函数调用加载本机板标准镜像；六个图标展示收发缓存、解析校验、时间戳回复、时钟、寄存器、NTS认证。Et1/ap1真实包路径与装载路径分开，网口接线命令标明interface模式。底部保留BMv2 CPU执行与本案例FPGA执行的简短对照。

图示appdir为运行脚本所在目录，不猜固定绝对安装路径；FDK/MOS装载接口以下不假设具体总线。包内两类文件、函数名、路径拼接、模块来源均按固定04c89fd2核对，细节见ARISTA-HARDWARE-NOTES.md。功能分组并非真实布局，省略PPS外部接线与辅助逻辑；未把普通NTP画成必经NTS认证。原生SVG1200×1750，800px Noto字体审图，7图/7运行卡/7导航及目录14图不变，双层SHA更新；无硬件执行。


## DEC-359：审核后的理论位置与来源（2026-09-06）

原图文件不改。Parser/Deparser图和v1model图归运行①导航后，BMv2进程/网口图归运行②；准备A/B只保留工具准备。VLAN三态图补紫色关键图卡与灰框，统一800px展示；resvg0.47配Noto CJK字体在800px重渲染，文字/连线目视可读。现役仍7图（3PNG+4SVG），目录14图片文件。

- 正文固定[P4-16 v1.2.5](https://p4.org/wp-content/uploads/sites/53/2024/10/P4-16-spec-v1.2.5.html)，与p4c版本独立。[ITCH5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf)补Type A/Locate/Stock/36字节定义来源。
- Tofino作为已发布实例，正文新增[Intel PCN827577-00](https://cdrdv2-public.intel.com/827577/PCN827577-00.pdf)所列型号停产边界及[Open P4 Studio专有驱动依赖](https://github.com/p4lang/open-p4studio#what-is-included)；不推断APS整机当前供货。
- Parser/Deparser当前依据固定为本课BMv2版本对应的`68f4a978f465fd76e98fcdecb762981843fb7310`：[parser.cpp](https://github.com/p4lang/behavioral-model/blob/68f4a978f465fd76e98fcdecb762981843fb7310/src/bm_sim/parser.cpp)的extract/remove，[deparser.cpp](https://github.com/p4lang/behavioral-model/blob/68f4a978f465fd76e98fcdecb762981843fb7310/src/bm_sim/deparser.cpp)的prepend/有效头输出；两文件SHA分别为`63c95e577e0ffe68e65b4bba94b2d630fefcab05d1a479a5a0d975b016daccd2`、`e8b82244808afec8d80ac94ee7c267854f0349defef626f7fea1c73c04f24078`。上文旧main链接保留历史核对记录，以本条固定提交为当前实现依据。

只读公开资料与本地校验，无新设备实验。正文结构、加粗、卡片、引用及双层摘要同步检查。
