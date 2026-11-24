# 第09章 Arista 真机案例：Netnod NTP/NTS

> 2026-09-06 · DEC-357 · EXTERNAL CASE / SOURCE REVIEW · 本课未复现硬件

正文采用 Netnod 的 Arista 7130-48LB 报时应用。用户已将范围放宽为有具体代码、编译、装载和查看步骤的 FPGA 交换机案例，优先 Arista。它替代原假设48L上的NVDA过滤工程；没有把时间服务器改名成过滤器。

## 实机依据与固定版本

| 对象 | 固定身份 / 来源 |
| --- | --- |
| 外部部署 | [Arista 2022年3月 Netnod 案例](https://www.arista.com/assets/data/pdf/CaseStudies/Arista-Netnod-CaseStudy.pdf)记载从原型迁入7130L及2022年2月服务发布；这不能证明本节固定Git提交对应其生产镜像 |
| 具体48LB项目 | [Netnod 官方说明](https://www.netnod.se/news/netnod-goes-live-with-arista-fpga-implementation-of-network-time-security)和[项目根README](https://github.com/Netnod/FPGA_NTP_SERVER)列7130-48LB、VU9P FPGA及硬件网络实现 |
| 主仓库 | [FPGA_NTP_SERVER](https://github.com/Netnod/FPGA_NTP_SERVER/tree/04c89fd2f2347843246ad825ace986db7408fe89)，commit `04c89fd2f2347843246ad825ace986db7408fe89`，提交日期2023-04-18；2026-09-06只读核对 |
| NTS子模块 | [Netnod/nts](https://github.com/Netnod/nts/tree/3d621125e6062b1a26f97782922d3b48977c6463)，gitlink `3d621125e6062b1a26f97782922d3b48977c6463`；正文RTL来自此版本 |
| 板与软件 | 7130-48LB / Board Standard `lb2`；`src/example.py` 继承 `mosapi.App`，本节使用MOS命令；公开说明未固定MOS精确发行版，需设备/FDK兼容表 |
| 编译环境 | README 指定Vivado2019.2；当前 `build.sh` 和 Makefile 采用FDK2.5.0。需取得包含tscore工程的厂商FDK、器件/IP许可及发行包要求的构建/打包依赖 |

Arista 的 [OpenFDK README](https://github.com/aristanetworks/openfdk)也将 Netnod 列为外部案例，但当前 OpenFDK 的 null/EOS 命令不能直接替代本项目的 MOS 应用接口。

## 代码、命令和输出如何核对

| 学生看到的内容 | 源码或文档依据 | 限定 |
| --- | --- | --- |
| 解析器的UDP123与交换回复端口 | 固定NTS子模块 `src/rtl/nts_engine/nts_parser_ctrl.v`：UDP_PORT_NTP及tx_header_udp | 只是两个关键节选，完整解析器还校验地址、长度、协议等 |
| `i_ntp_time` 加发送补偿 | `nts_timestamp.v` 的p_transmit_timestamp_new，后续packet包含origin/receive/transmit字段 | 时间补偿是NTP定点时间字段运算，不是可随意填纳秒整数；不推算该应用实际时延 |
| `git submodule update --init --recursive` | 主仓库 `.gitmodules` 与gitlink | 必须取到固定子模块；只下载主仓库ZIP不包含完整RTL |
| `./build.sh` | [build.sh](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/build.sh)准备neorv32/processor、生成buildinfo、调用BOARDSTD=lb2 | 没有执行；需Vivado和FDK。构建可能输出大量工具日志，正文没有声称提供精简实测输出 |
| `ntps-4.0.0.x86_64.rpm` / `.swix` | [Makefile](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/Makefile)的PROJECT/VERSION_ID/APP_RPM/APP_SWIX | 预期产物名，当前工作区没有生成的硬件包 |
| `scp … admin@arista:` | [项目README](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/README.md) | arista须解析到隔离7130管理地址，不得指向现役7150 |
| `install app …`、重新登录 | 项目README的MOS安装流程 | 正文针对首次安装、无旧应用占用；旧ntps/tscore须先按原文停用、备份和卸载，不能盲目覆盖承载业务的FPGA |
| `mac address …`、`ip address 0 …`、`no shutdown` | [example.py](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/src/example.py) CLI注册与no_shutdown实现 | 槽0是服务地址槽，不是Linux接口IP；普通NTP查询不需要文档里的示例NTS密钥，正文未抄密钥 |
| `self.fpga.load_image(bit)` | example.py program_fpga选择应用名/板标准对应的bit，no_shutdown调用它 | 装包不是加载；启动还会等待同步daemon，再配置网络硬件 |
| `source ap1` / `destination ap1` | 项目README Production use using a SFP+ port | 按本项目MOS语法同口双向连接；没有推导未验证Et2/ap2场景，没有混入EOS l1 source |
| `show ip address` | example.py的show_ip_address注册于config-app-ntps | 读配置，不单独证明硬件应答 |
| `show interface et1` / `show ntps synchronisation status` | 项目README检查示例 | 链路与同步读数需真机，不填模拟成功输出 |
| `ntpdate -q …` | 项目README与[NTP官方ntpdate说明](https://www.ntp.org/documentation/4.2.8-series/ntpdate/) | -q只查询；delay为往返估计，不是芯片延迟。沿历史案例工具，不将其作为新的长期对时部署建议 |

## 必须取得的外部条件

- 厂商FDK2.5.0及匹配MOS发行说明；`resources/app.mk`、`resources/vivado.mk`、lb2 BSP、tscore RTL/管理daemon、LibApp及相关IP均应齐全。Makefile会从FDK的`examples/tscore/src`复制时钟管理文件，缺失不是普通pip安装能解决。
- Vivado2019.2及VU9P/IP许可。本文没有取得许可、运行综合/布局布线/时序与CDC检查，也没有复算完整硬件制品SHA。
- 7130-48LB、10G SR/LR光模块、相应光纤与对端网卡。项目明确记录铜模块可能不稳定；不复用现役BMv2实验的DAC已验结论。
- 可靠PPS输入、匹配的tscore时间源配置、MOS通过NTP/PTP取得绝对时间。项目说明系统时间需与秒脉冲对齐到约0.25秒以内；时间源接头电气条件、配置命令和精确MOS版本须按厂商材料补齐。
- 示例服务地址192.168.40.50、客户端192.168.40.10/24属于独立台架，不修改课程20.1.1.1/2。管理面独立，装载前保存原应用、端口source/destination和时间配置；出错按保存配置恢复。

## 本轮发现的文档漂移

同一固定主仓库提交的README仍写FDK2.0.0beta1，但build.sh/Makefile明确用2.5.0。正文优先采用实现并注明差异；没有拼接旧3.0.0 RPM与新4.0.0 SWIX。调查过更早的3fd36812提交，但其app-cfg.json解析失败，未选作课程版本。

新版src/app-cfg.json的Linux_Driver引用经仓库symlink指向顶层驱动目录；时钟daemon等文件由Makefile从FDK取得。GitHub单个raw路径404不等于工程一定缺文件，应检查符号链接及生成规则后判断。FDK未取得的部分仍列外部依赖，不标验证通过。

## 验证结论

完成官方案例、固定源码及命令定义核对；JSON、源码节选、正文卡片/导航/链接、原生SVG和图集摘要检查。图展示CPU软件过滤与FPGA报时两个不同应用，不声称同一业务代码已移植。现役P4/RTL核心/现场脚本/运行态未改，无远程设备操作、无新RUN。

状态为 **SOURCE REVIEW；完整构建与本课板上复现待完成**。外部真实部署是选择此案例的依据，不是对任意硬件/软件组合的成功保证。将来改做NVDA过滤，还需移植ITCH解析、一次额度、整包缓存与转发裁决并重新验收。


## DEC-358：一张图定位安装、装载、参数配置与真实报文（2026-09-06）

- 重画原路径SVG，1200×1750。开发机的`src/example.py`相对于`FPGA/targets/ntps_arista/`；设备上的`appdir`由该脚本`os.path.dirname(__file__)`取得，镜像路径拼成`appdir/fpga/ntps-lb2.bit`。没有猜测固定安装绝对路径。
- 图中安装命令位于MOS，`app ntps`模式的`no shutdown`调用`no_shutdown()`→`program_fpga()`→`self.fpga.load_image(bit)`；Python保持在CPU运行，镜像作为硬件配置数据交给FDK/MOS装载接口。实际底层配置总线未核实，不擅自标SPI/JTAG/PCIe，也不把管理寄存器的I2C推成镜像下载路径。
- `interface et1`模式下的同名`no shutdown`只是启用网口，source/destination负责L1接线。正文已分清两个命令上下文；图中接线块只列source/destination，完整命令仍在正文。
- FPGA功能卡对应固定主仓库`src/ntps-lb2-cfg.json`：oc_mac/rx/tx与PHY工程、nts_rx_buffer/nts_tx_buffer、nts_parser_ctrl、nts_timestamp、tscore/ntp_clock、寄存器接口及nts_verify_secure/加密核心等。卡片是功能分组，不是逐个实例、时序流水级或器件物理布局；本图仅展开普通NTP请求，NTS认证另列。
- 加载配置、时钟同步和运行参数写入分别说明；完成镜像配置不直接等于端口/业务已就绪。寄存器来自已实现电路，Python并未编译进FPGA。收发部分会使用芯片既有收发资源，不能理解为镜像创造物理晶体管或引脚。
- 核对固定example.py的路径拼接与调用顺序、板级源文件列表，SVG800px目视、正文格式/原命令不变及双层摘要。图只记录功能和接口关系，未取得FDK2.5.0或完成本课硬件复现。
