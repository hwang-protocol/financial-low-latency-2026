# FLLE Local Artifact Vault

这个目录用于在 VM 快照恢复后复用已经下载的大文件，避免重复访问外部站点。

- 大文件仍默认放入受忽略的 `artifacts/blobs/`；但当前第06章的最小恢复闭包按 `GIT-BACKUP-SHA256SUMS` 精确加入 Git 白名单。不得用删除整条 ignore 规则的方式把历史包和无关镜像一起提交。
- `ARTIFACTS.tsv` 的 `local_path` 以 `artifacts/` 为基准；`REMOTE_ONLY@host:/path` 表示只完成远端盘点、没有复制到 vault。
- 可审计的来源、版本、大小、SHA-256、信任状态和现场路径写入 `ARTIFACTS.tsv`。来源无法从现场证据确认时必须写 `UNKNOWN`。
- `VERIFIED_BYTES` 只表示本地字节与登记哈希一致，不代表发布者身份可信。
- TLS、签名或官方 checksum 未闭环的文件必须使用 `UNTRUSTED_EXPERIMENT_ONLY` 或下述同等明确的受限信任状态，不能标成 publisher verified。
- 口令、license key、私钥、token 和受限凭据不得进入 artifact vault 或 manifest。
- 厂商镜像只供本实验环境内部恢复使用，不从本项目对外分发。
- 不允许为了“补齐”vault 无版本地抓取文件或把整个已安装系统目录冒充上游源码。可重复构建的课程运行包可以收纳其精确解析到的共享库闭包，但必须登记 OS/架构、每个文件摘要、源码/包来源和实机运行边界。
- `.deb` 单文件不是依赖闭包。现役课堂工具使用下述已核验的专用离线包组；其他历史 `.deb` 不自动具备该保证。

## Git 持久恢复闭包

用户确认持久管理机本身也可能恢复，不能继续把 VM 本地 `artifacts/blobs/` 当作唯一副本。当前 Git 白名单只覆盖第06章从干净 checkout 直接部署固定应用、验签源码与在必要时重建当前内核 Onload 模块所需的 5 个不可变文件：

| 文件 | 作用 |
| --- | --- |
| `blobs/x2522/onload/v9.0.2/onload-9f330e7-vm-2522-01.tgz` | 准备 A 的固定 Onload 源码；内核变化时用于重编模块 |
| `blobs/x2522/ch06-four-path/v5/flle-ch06-four-path-v5-build-inputs-x86_64-jammy.tgz` | TCPDirect / F-Stack 头文件与实际链接的静态库闭包 |
| `blobs/x2522/ch06-four-path/v12/BUILD-PROVENANCE.json` | 构建主机、输入摘要、命令和 source→ELF 映射 |
| `blobs/x2522/ch06-four-path/v12/flle-ch06-four-path-v12-source.tgz` | 17 文件应用与 DPDK 生命周期源码闭包 |
| `blobs/x2522/ch06-four-path/v12/flle-ch06-four-path-v12-x86_64-jammy-runtime.tgz` | 三种 Trader、Exchange、工具、F-Stack 配置与运行库 |

这 5 项合计 `32663167 bytes / 31.15 MiB`，最大单文件约 `24.5 MB`。当前管理环境没有 Git LFS，因此它们以普通 Git 二进制对象保存，`.gitattributes` 禁止文本转换、合并和无意义 diff。含第三方头文件与静态库的远端必须是获得授权的私有仓库；不得因进入 Git 就扩大分发范围。

从 Git 恢复后先在仓库根目录执行：

```bash
sha256sum -c artifacts/GIT-BACKUP-SHA256SUMS
```

只有 5/5 通过，才允许进入第06章准备 A～C。v1～v11 历史运行包、行情大样本、系统软件镜像和其他章节缓存仍默认忽略；它们不属于本次“当前第06章可直接运行 / 可重建”闭包。未来若要加入新的持久制品，必须同时更新 `.gitignore` 精确白名单、`GIT-BACKUP-SHA256SUMS`、`ARTIFACTS.tsv` 与本说明，不能只执行 `git add -f`。

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

第06章当前固定闭包使用 v12 应用与控制源码，继承 v5 的厂商构建输入：

- 源码闭包 `blobs/x2522/ch06-four-path/v12/flle-ch06-four-path-v12-source.tgz`，size=`47549`，SHA-256=`4e79723b1cb0aaf4f137072fce638a969a4ea56c94f7eb8cb5ca6de3ba46903e`；
- 构建输入闭包仍为 `blobs/x2522/ch06-four-path/v5/flle-ch06-four-path-v5-build-inputs-x86_64-jammy.tgz`，size=`4504944`，SHA-256=`6caa8e25a4228751872b8b96ed1cff260532fd73ab4fcb14f1d85cb7e7baf451`；
- 构建记录 `blobs/x2522/ch06-four-path/v12/BUILD-PROVENANCE.json`，size=`6693`，SHA-256=`796c83ef23944fac595e2c9f718007d7038acadf34c07c54a1e74081a75badc8`；
- 运行包 `blobs/x2522/ch06-four-path/v12/flle-ch06-four-path-v12-x86_64-jammy-runtime.tgz`，size=`24530127`，SHA-256=`163618ccbb99d272d1f4703822781984d754c690d23fba5503e503486e33c9f3`。

preflight `20260901T145319Z` 与正式 RUN `20260901T150724Z` 验证了 v12 manifest、四路真实成交、4×4 Williams 平衡、17,600 笔账本闭合、X2522 IOMMU/PMD/ULL 收据和最终交还。正式 schema 为 v13，balanced analysis 为 v10；16,000/16,000 正式样本均为 `Executed`。v1～v11 继续留盘作方法演进或失败证据，不再承担当前课堂性能结论。

核对当前机完整本地 vault 时运行：

```bash
(cd artifacts && sha256sum -c SHA256SUMS)
```

`SHA256SUMS` 列当前控制节点实际保存的完整本地 vault；干净 Git checkout 只保证 `GIT-BACKUP-SHA256SUMS` 中的第06章 5 项恢复闭包。远端 VM 中存在但尚未复制的文件只登记在 `ARTIFACTS.tsv`，不进入 checksum 清单。

新增非 Git 恢复制品后还必须逐文件确认忽略规则：

```bash
find artifacts/blobs -type f -print0 | xargs -0 -n1 git check-ignore -q
```

## 课堂工具离线缓存（DEC-384）

当前保留在 `.111` 的 `blobs/course-packages/jammy-amd64-20260907-v2/` 包含 450 个包，合计 700,219,134 字节。权威清单为 [course-packages-jammy-amd64.json](course-packages-jammy-amd64.json)，逐包记录版本、来源、SHA-256 和依赖组；适用 Ubuntu 22.04 amd64，Onload/XDP 内核工具限定 `5.15.0-164-generic`。缓存字节仍被 Git 忽略，不能把只有清单的 checkout 当作已有安装包。

课前在本机运行 `python3 artifacts/tools/check-course-package-cache.py`。第一章准备 A 也执行此检查，缺包时当场报错；课堂安装器只校验、通过管理网分发、从临时本地 APT 源安装，显式禁止下载和卸载，不使用目标机公网源。已经装好精确版本时只核对，不重复安装。

九组工具为基础诊断、Builder、Onload 构建依赖、XDP、PTP、P4 编译端、BMv2 运行端、Verilator、Prometheus/Grafana。每组依赖从空 dpkg 状态解析，并在隔离网络命名空间中验证可解；不会将“目标机已有依赖”误当成缓存完整。P4 发布源公钥 SHA 沿用已有固定值，下载包与保存的 APT 索引 SHA-256 一致；Grafana 字节沿用原 vault 固定 SHA，不提升其已有信任等级。

重建缓存是课前维护工作：保存 Ubuntu/P4 的索引、签名、公钥与解析输出后，`tools/fetch-course-packages.py <bundle>` 根据已解析的精确 URI/版本补包，`tools/seal-course-packages.py <bundle>` 生成清单。不得在课堂入口调用这两个维护工具。更新包版本或快照内核后，应建立新的版本目录并重新做离线闭包与现场安装验证。

行情大样本、Onload 源码、固定交易运行包、TRex 归档继续使用本 vault 原有路径与指纹。完整性能比较保留正式采样时长；离线缓存消除的是准备工具时不可控的公网等待。
