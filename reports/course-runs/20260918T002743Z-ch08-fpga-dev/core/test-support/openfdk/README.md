# OpenFDK 本地测试依赖

本目录保存第 08 章 [test_eos_control.py](../../test_eos_control.py) 使用的三份公开源码，使管理逻辑测试可以直接读取仓库文件。Python 3 环境须已安装 `six`；运行测试时无需下载 OpenFDK。

来源为 [Arista OpenFDK](https://github.com/aristanetworks/openfdk)，固定提交为 `13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d`。三份 Python 文件逐字保留上游内容，与[已有来源证据](../../../../../design/evidence/ch08-modern-eos-20260917.json)中的 SHA-256 一致；全部复制文件同时与该提交的 Git 对象核对一致。逐文件来源、大小和校验值见 [SOURCES.json](SOURCES.json)；本目录文件清单见 [SHA256SUMS](SHA256SUMS)。

| 文件 | 测试中使用的功能 |
| --- | --- |
| `resources/libapp/register_file.py` | 读取寄存器 CSV，并通过测试提供的内存后端访问寄存器 |
| `resources/libapp/serial.py` | 解析测试用的状态数据 |
| `resources/libapp/cli.py` | 核对状态包装与本课 CLI 处理函数的调用关系 |

测试脚本主动加载这三份文件，并提供模拟的包、设备及 EOS 命令上下文，因此不需要复制 `libapp/__init__.py` 或 `device.py`。`cli.py` 对 `eossdk` 的导入有缺失处理；本测试不执行 EOSSDK。硬件访问与装载对象均由测试模拟，测试结果只说明本地管理逻辑的行为。

这是供测试读取的源码子集，**不是完整 BVL FDK**：其中没有板级工程、网口 IP、构建与打包规则，也不能用于生成 PDI、制作 SWIX 或替代交换机上的管理库。取得完整开发包后，设备应用仍须按其版本与许可要求构建。

保留各源码文件的原始版权声明，并附上完整的上游 [BSD-3-Clause 许可](LICENSE.md)。2026-09-18 只进行了来源、字节和依赖核对；实际测试结果由章节运行记录登记。
