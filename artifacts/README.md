# FLLE Local Artifact Vault

## 第九章 U250 官方参考源码

`blobs/ch09-u250-reference/open-nic-shell-940907fc99fc8d73dbea0028b3a23095a660a42a.tar.gz` 是 AMD/Xilinx OpenNIC 官方固定版本源码缓存，215 个文件、29,014,489 字节。源地址、摘要和验证边界见 [来源清单](ch09-u250-reference-source.json)。未修改上游文件，未验证发布者签名，也未执行 Vivado 2026.1 板级构建。仅保留 Git 清单不能保证忽略目录中的包字节随快照恢复。

用户要求通过官方地址亲手下载、解压并使用 Vivado GUI；缓存服务于维护恢复，不替代这条教学步骤。自制 GUI 启动器及 flle-u250-reference.zip 已撤回，不作为交付物。

## 第八章离线开发工具缓存

`.111` 保留 `blobs/ch08-fpga-dev/`，向可恢复快照的 `.101` 开发机分发 Icarus 11.0-1.1、YoWASP Yosys 0.69.0.0.post1233、固定 Python 依赖及离线 pip 引导包。11 个安装包加 requirements 共 30,628,183 字节；逐文件来源、版本和摘要见 [清单](ch08-fpga-dev-cache.json)，目标机条件和安装命令见 [说明](ch08-fpga-dev-cache.md)。缓存依赖 `.101` 已有 Ubuntu 22.04 amd64 基础库，不是从空系统解析的系统依赖闭包。

恢复 `.101` 快照后，按课程步骤从 `.111` 重新分发和安装；`.101` 的快照不会携带或恢复 `.111` 上的缓存。包字节仍被 Git 忽略，未加入 `GIT-BACKUP-SHA256SUMS`；只有 Git 清单时不能视为已有缓存。新增文件已登记到总 `ARTIFACTS.tsv` 和 `SHA256SUMS`，目录内另有可独立核对的相对路径 `SHA256SUMS`。PyPI wheel 与官方 TLS 元数据中的 SHA-256 一致；发布者独立签名未验证。

## 第六章官方 LANZ 客户端

`blobs/arista/lanz-reader-v1/` 保存静态读取工具、包含未修改官方 vendor 的源码包和构建记录，三项进入 Git 精确恢复清单。依赖是 Arista `goarista/lanz`（a373d7c9f0d9）与 Google Protobuf 1.36.10，Go 1.24.13 构建。官方 Go 安装包已缓存并与官方下载摘要核对，仍被 Git 忽略；课堂只部署已编译文件，无需编译器或公网。离线源码包重建逐字节一致，本地 TCP/网页接续测试通过；v1.1于2026-09-17实测10k无事件、25k累计163次，EOS与接收器一致。适配器保留原始10µs刻度并换算UTC时刻，未修改官方SDK。


## 第五章 Socket／Onload 打标更新

`blobs/x2522/ch05-four-path/posix-qos-v1/` 保存已编好的增量客户端、构建记录和摘要合同。第二章上线入口从 `.111` 分发到 `.2` 的 `posix-runtime/flle-posix-qos-v1/`，Kernel Socket 与 Onload 共用它；默认 DSCP 0。原 v13 包、TCPDirect、DPDK 和 Exchange 保持；第五章准备 B 只核对并启用已准备的程序。旧第四章快照由第二章入口加 `--prepare-capabilities` 一次补齐。

构建入口：`apps/flle-trading-lab/releases/posix-qos-v1/build.py`；以 v13 固定源码加 `client.patch` 构建，课堂不下载、不编译。已通过本机回环 TCP/包头测试；尚未在 X2522 上完成 Onload 打标和交换机 QoS 重跑。下文 v13 数字属于更新前记录。

当前部署更新为 **v13**：单一 Socket 行情接收、Nasdaq 组播频道与本机分发；控制服务在 `.2`。v12 保留为既有性能 RUN 的历史闭包。v13 七个应用输出两次隔离构建逐字一致；DPDK 下单源码未变，复用 v12 的 DPDK ELF 与厂商运行库。下方 v12 正式性能样本不作为新架构的重新测量。修改与功能验收见 [流量修改报告](../refs/FLLE_Traffic_Revision_2026-09-08.md)。

- `blobs/x2522/ch05-four-path/v13/BUILD-PROVENANCE.json`：6518 字节，SHA-256 `b7b0a019c72819812589df936369b40194ce7b71ebef34d1d025175a41a666a7`。
- `blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-source.tgz`：49425 字节，SHA-256 `1cbae2786192ac16c39b1ebbdb7a19101b99a532430903839de39a8f0fa62bc7`。
- `blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-x86_64-jammy-runtime.tgz`：24678373 字节，SHA-256 `0e5d77fef1e4891b9f2220681c18162da6c605ea5619ea00e28022f23281dc00`。


这个目录用于在 VM 快照恢复后复用已经下载的大文件，避免重复访问外部站点。

- 大文件仍默认放入受忽略的 `artifacts/blobs/`；但当前第05章的最小恢复闭包按 `GIT-BACKUP-SHA256SUMS` 精确加入 Git 白名单。不得用删除整条 ignore 规则的方式把历史包和无关镜像一起提交。
- `ARTIFACTS.tsv` 的 `local_path` 以 `artifacts/` 为基准；`REMOTE_ONLY@host:/path` 表示只完成远端盘点、没有复制到 vault。
- 可审计的来源、版本、大小、SHA-256、信任状态和现场路径写入 `ARTIFACTS.tsv`。来源无法从现场证据确认时必须写 `UNKNOWN`。
- `VERIFIED_BYTES` 只表示本地字节与登记哈希一致，不代表发布者身份可信。
- TLS、签名或官方 checksum 未闭环的文件必须使用 `UNTRUSTED_EXPERIMENT_ONLY` 或下述同等明确的受限信任状态，不能标成 publisher verified。
- 口令、license key、私钥、token 和受限凭据不得进入 artifact vault 或 manifest。
- 厂商镜像只供本实验环境内部恢复使用，不从本项目对外分发。
- 不允许为了“补齐”vault 无版本地抓取文件或把整个已安装系统目录冒充上游源码。可重复构建的课程运行包可以收纳其精确解析到的共享库闭包，但必须登记 OS/架构、每个文件摘要、源码/包来源和实机运行边界。
- `.deb` 单文件不是依赖闭包。现役课堂工具使用下述已核验的专用离线包组；其他历史 `.deb` 不自动具备该保证。

## Git 持久恢复闭包

当前 Git 恢复清单共 14 项：Onload 源码、v5 构建输入、v12 历史源码/构建记录/运行包，现役 v13 源码/构建记录/运行包、Socket/Onload 更新包，以及 LANZ 官方 SDK 读取工具的二进制/源码包/构建记录。精确路径以 `GIT-BACKUP-SHA256SUMS` 和 `.gitignore` 白名单为准；当前部署使用 v13，v12 用于核对历史实验。

从项目根目录执行：

```bash
sha256sum -c artifacts/GIT-BACKUP-SHA256SUMS
```

14/14 通过表示持久恢复文件齐全。2026-09-12 已将四路径目录、文件名和现役解包目录统一为 `ch05`。运行程序、厂商库和配置内容保持不变；重打包后的摘要已同步登记。旧版本归档内部的原始目录和构建日志用于历史追溯，不作为课堂部署入口。重打包工具为 `artifacts/tools/relocate-four-path-chapter05.py`，迁移对账见 [记录](../refs/evidence/chapter05-artifact-relocation-20260912.json)。

大文件仍使用普通 Git 二进制对象，`.gitattributes` 禁止文本转换、合并及二进制文本 diff。不要扩大 `.gitignore` 白名单；厂商依赖仅限授权私有仓库和本实验环境使用。

## 信任状态边界

- `USER_PROVIDED_EXECUTION_VERIFIED`：用户提供的字节已做本环境执行回归；不代表发布者签名已验证。
- `UPSTREAM_GIT_ATTRIBUTED_LOCAL_ARCHIVE_NO_SIGNATURE`：可关联干净 Git commit，但 archive 是现场生成字节，tag/发布者签名未验证。
- `VENDOR_METADATA_SIGNATURE_KEY_UNAVAILABLE`：包内签名元数据存在且 payload digest 正常，但现场没有公钥，不能称为签名通过。
- `APT_CACHE_REPOSITORY_ATTRIBUTED_NO_STANDALONE_SIGNATURE`：来源由本机 APT policy 归因；本次没有归档并重验完整 repository metadata/signature chain。
- `ORIGIN_UNKNOWN_HASH_ONLY`：只证明现场文件及其 SHA-256；精确下载来源未知。
- `OFFICIAL_PUBLIC_SAMPLE_DERIVED_BYTE_PRESERVING_FILTER`：输入可追到官方公开样本，当前文件是本课依赖感知过滤器产生的字节保真子集；表示来源和派生过程可审计，不表示该子集由发布者单独签名。
- `LOCAL_DERIVATION_MANIFEST_HASH_VERIFIED`：本地派生清单已经按登记 SHA 验证；其结论仍须与被描述的输入、输出及生成工具共同复核。
- `LOCAL_BUILD_LINK_VERIFIED_NOT_HARDWARE_RUNTIME_VERIFIED`：编译产物可追到已登记源码和固定构建参数，并已从新目录完成重链接检查；尚未取得目标网卡上的运行收据，不能写成硬件数据面已通过。
- `LOCAL_BUILD_SOURCE_CLOSURE_HASH_VERIFIED`：本地归档精确覆盖本次应用构建使用的 Makefile、源码树和构建合同，并已按登记 SHA 验证；不表示它是发布者签名的源码发行版，也不自动覆盖运行控制脚本。
- `LOCAL_BUILD_INPUT_CLOSURE_HASH_VERIFIED`：本地归档固定了本次应用链接实际消费的头文件和静态库字节，并通过内部清单与登记 SHA 验证；它只支持重建本地应用，不表示这些静态库已从上游源码可复现构建。
- `LOCAL_BUILD_PROVENANCE_HASH_VERIFIED`：本地构建记录把固定输入、命令、构建日志摘要与输出二进制摘要连起来，并已按登记 SHA 验证；它不是可复现构建证明，记录中的运行验收仍须由独立 RUN 完成。
- `LOCAL_BUILD_X2522_FOUR_ORDER_PATHS_RUNTIME_VERIFIED`：固定运行包可追到登记源码和 Jammy 构建合同，已验签内部 manifest，并在 X2522 上完成四种 SoupBinTCP/OUCH 真单、VFIO/PMD 收据和最终交还；它只覆盖本课程固定 VM/内核/网卡环境，不等于通用发行包或生产认证。
- `REMOTE_ONLY_*`：只读盘点结果，不是本地备份，也不进入 `SHA256SUMS`。

以下 v12 闭包用于追溯历史实验；现役部署使用 v13，并继承 v5 的厂商构建输入：

- 源码闭包 `blobs/x2522/ch05-four-path/v12/flle-ch05-four-path-v12-source.tgz`，size=`47549`，SHA-256=`4e79723b1cb0aaf4f137072fce638a969a4ea56c94f7eb8cb5ca6de3ba46903e`；
- 构建输入闭包仍为 `blobs/x2522/ch05-four-path/v5/flle-ch05-four-path-v5-build-inputs-x86_64-jammy.tgz`，size=`4504944`，SHA-256=`eabe97e149377fcf12c10081b25228930d96f4745fdd1ecea3eb4aa83ff46c4e`；
- 构建记录 `blobs/x2522/ch05-four-path/v12/BUILD-PROVENANCE.json`，size=`6693`，SHA-256=`796c83ef23944fac595e2c9f718007d7038acadf34c07c54a1e74081a75badc8`；
- 运行包 `blobs/x2522/ch05-four-path/v12/flle-ch05-four-path-v12-x86_64-jammy-runtime.tgz`，size=`24530127`，SHA-256=`163618ccbb99d272d1f4703822781984d754c690d23fba5503e503486e33c9f3`。

preflight `20260901T145319Z` 与正式 RUN `20260901T150724Z` 验证了 v12 manifest、四路真实成交、4×4 Williams 平衡、17,600 笔账本闭合、X2522 IOMMU/PMD/ULL 收据和最终交还。正式 schema 为 v13，balanced analysis 为 v10；16,000/16,000 正式样本均为 `Executed`。v1～v11 继续留盘作方法演进或失败证据，不再承担当前课堂性能结论。

核对当前机完整本地 vault 时运行：

```bash
(cd artifacts && sha256sum -c SHA256SUMS)
```

`SHA256SUMS` 列当前控制节点实际保存的完整本地 vault；干净 Git checkout 只保证 `GIT-BACKUP-SHA256SUMS` 中的 14 项恢复文件。远端 VM 中存在但尚未复制的文件只登记在 `ARTIFACTS.tsv`，不进入 checksum 清单。

新增非 Git 恢复制品后还必须逐文件确认忽略规则：

```bash
find artifacts/blobs -type f -print0 | xargs -0 -n1 git check-ignore -q
```

## 课堂工具离线缓存（DEC-384）

当前保留在 `.111` 的 `blobs/course-packages/course-00-08-jammy-amd64-20260919/` 包含 233 个包，合计 548,859,198 字节。权威清单为 [course-packages-jammy-amd64.json](course-packages-jammy-amd64.json)，逐包记录版本、来源、SHA-256 和依赖组；适用 Ubuntu 22.04 amd64，Onload/XDP 内核工具限定 `5.15.0-164-generic`。缓存字节仍被 Git 忽略，不能把只有清单的 checkout 当作已有安装包。

课前在本机运行 `python3 artifacts/tools/check-course-package-cache.py`。第一章准备 A 也执行此检查，缺包时当场报错；课堂安装器只校验、通过管理网分发、从临时本地 APT 源安装，显式禁止下载和卸载，不使用目标机公网源。已经装好精确版本时只核对，不重复安装。

七组工具为基础诊断、Builder、Onload 构建依赖、XDP、PTP、Verilator、Prometheus/Grafana。P4/BMv2 及其独占依赖已从当前清单移除。每组依赖从空 dpkg 状态解析，并在隔离网络命名空间中验证可解；不会将“目标机已有依赖”误当成缓存完整。包版本、来源和 SHA-256 沿用原清单；Grafana 字节沿用原 vault 固定 SHA，不提升其已有信任等级。

重建缓存是课前维护工作：保存 Ubuntu 的索引、签名、公钥与解析输出后，`artifacts/tools/fetch-course-packages.py <bundle>` 根据已解析的精确 URI/版本补包，`artifacts/tools/seal-course-packages.py <bundle>` 生成清单。不得在课堂入口调用这两个维护工具。更新包版本或快照内核后，应建立新的版本目录并重新做离线闭包与现场安装验证。

行情大样本、Onload 源码、固定交易运行包、TRex 归档继续使用本 vault 原有路径与指纹。完整性能比较保留正式采样时长；离线缓存消除的是准备工具时不可控的公网等待。

当前总登记与总 SHA 清单仅列 00–08 课程所需的七组缓存。裁剪依据、原清单指纹和移除包名见 [迁移清单](course-packages-migration-20260919.json)。原 v1/v2 缓存保留在旧项目，不再复制到本项目。

## 迁移后的本地清单范围

`SHA256SUMS` 与 `ARTIFACTS.tsv` 描述本项目的本地文件。未迁入的 EOS 镜像、退役 P4 独立安装包保留在 [未迁入记录](NOT-MIGRATED.tsv)，不作为当前课程的缺包，也不参与本地完整性检查。路径改动过的缓存说明已重新登记大小和哈希。

本地 00–08 配套全量检查：`python3 tools/check-course-migration.py --full`。该检查不部署、不安装、不连接设备。
