# 00–08 课程迁移核查（2026-09-19）

核查源为 `/financial-low-latency`，目标为 `/qyt-fll`。范围是根目录 9 篇课程文章、实际引用的图片/来源说明，以及配套程序、脚本、离线安装和回归所需材料。用户明确排除 P4 课程。原项目未修改；本次没有提交或推送 Git，也没有连接实验设备。

## 结论

根目录扁平化、`assets/`、`apps/`、`artifacts/` 和 `reports/` 的路径调整整体合理。9 篇正文未发现图片或普通本地链接缺失，章节差异主要是目录改写与来源链接调整。不过，配套测试夹具、间接来源证据和校验清单存在漏迁，不能仅凭正文链接正常就认为迁移完成。

当前课堂根目录仍固定为 `/qyt-fll`。多数课堂脚本显式 `cd` 到此路径；公共库根据自身位置计算根目录。这一部署约定已补到 README，未宣称支持任意目录。

## 已发现并修复

| 问题 | 影响 | 处理 |
| --- | --- | --- |
| XDP 准备回归、RTL 恢复回归仍用原目录深度计算根目录 | 找到错误目录，RTL 回归无法启动 | 修正两处 `parents` 层级 |
| 3 份 2026-09-08 抓包 RUN 未迁入 | 第 02 章 IGMP、第 03 章输出回归找不到原始夹具 | 仅补回 `reports/20260908T124834Z-03-live-market`、`20260908T124946Z-03-market-paths`、`20260908T125046Z-03-live-order`，合计约 176 KiB；保留原字节 |
| FPGA 来源说明的间接链接失效 | 丢失来源核对与整板时序失败的边界 | 补回 U250 routed 诊断、两份小型审查证据和 FPGA 案例来源，修正相对链接 |
| 卡片/图片回归仍假定旧 P4 与第 09 章存在 | 无法检查当前课程，错误要求已退役页面与图片 | 改为检查 00–08 章结构、现役 XDP 命令/网页恢复卡；保留所需 RTL 辅助输出回归 |
| 保留下来的旧 XDP 串联入口依赖被排除的 P4 | 形成隐含依赖，继续把退役课程带回来 | 删除该旧入口及教师表项；当前 `.2` 接收端 XDP 入口不变。RTL 的只读交接检查只保留独立 `assets/common/filter-handoff-show.plan`，不需要 P4 编译器或 BMv2 |
| 制品总清单仍列 EOS 镜像、旧 P4 独立包 | 全量哈希检查必然报缺失 | 本地清单移除三项，原始登记保留在 `artifacts/NOT-MIGRATED.tsv`；现役课程无需这些文件 |
| 3 份缓存说明/清单已改路径，大小或哈希未更新 | TSV 与 SHA 清单不能对应本地字节 | 重新登记本地元数据；离线包二进制不改 |
| 图册、源码包及辅助说明的局部 SHA 未同步 | 局部自检失败 | 更新当前文件树的摘要；旧、新摘要见[对账](evidence/migration-current-checksum-updates-20260919.json)，历史 RUN 内的原始清单未重写 |
| `.gitignore`、`.gitattributes` 未迁入 | 大缓存和 Python 临时文件失去原有版本管理约束 | 迁入适用规则，保留 14 项精确恢复制品白名单，不把整个 reports 忽略 |

## 按当前课程排除的内容

- P4 正文、脚本与 BMv2 实验入口不迁入。清掉已复制的 124 个旧 P4 实验/状态条目、13 张独占教学图，及图册中的退役教学说明；[排除清单](evidence/migration-exclusions-20260919.json)记录具体路径。
- 工具缓存只保留 `base`、`builder`、`onload-build`、`xdp`、`ptp`、`verilator`、`observability` 七组。它们需要 **233 个包，共 548,859,198 字节**；移除 P4/BMv2 独占的 217 个包。新缓存目录为 `artifacts/blobs/course-packages/course-00-08-jammy-amd64-20260919/`。
- 原 v1/v2 缓存副本不再留在新项目；原包仍可在旧工程找到。[缓存派生记录](../artifacts/course-packages-migration-20260919.json)保存来源清单指纹、保留组和移除包名。七组使用原来的精确依赖列表、版本和包 SHA，没有重新下载或升级。
- 当前图、代码或测试依赖的历史记录继续保留。多章共用的历史复刷记录可能仍提到当时的 P4 章节，这是历史内容，不是现役入口。未对原始证据做全文替换。

## 本地验证

- 9 篇正文的 155 处图片引用及 SVG 可解析；42 个标为“需要运行”的 Bash 块通过语法检查。展示用的不完整代码节选不当作可执行脚本。
- 现役 XDP 的 5 张命令卡与脚本入口匹配，另有 1 张网页手动恢复卡；8 个 XDP/RTL 支持脚本的 19 个输出块、4 个阶段标题通过本地检查。
- 34 个课程配套回归脚本全部通过；首轮暴露的 3 项失败已分别修复并复测。第 03 章输出回放包含 28 个正常/失败/恢复场景。
- 另验证交易控制器 14 项、平台能力 3 项、FPGA 管理逻辑 16 项，均通过；后者使用真实上游 CSV 解析器和模拟硬件。
- 七组离线依赖从空 dpkg 状态、隔离网络环境解析通过；缺失传递依赖的反例被正确拒绝。
- 全量本地链接、Shell/Python 语法、软链接、FPGA 配套源码副本、制品及图片清单由下方复查入口检查。机器可读结果见[验证记录](evidence/migration-validation-20260919.json)。

从项目根目录运行：

```bash
python3 tools/check-course-migration.py --full
python3 artifacts/tools/check-course-package-cache.py
python3 assets/common/verify-filter-course-cards.py
python3 assets/common/verify-filter-output-labels.py
python3 assets/common/test-offline-packages.py
```

这些命令不部署课程、不登录远端、不修改交换机配置。

## 验证边界

这次证明的是本地迁移配套完整性及离线回归，不是新目录下的整课实机复刷。`reports/run-state/` 里的指针来自旧实验；第一次上课仍需从第 01、02 章核对环境、恢复部署，不把复制状态当作新执行结果。

FPGA 当前证据包含[整板时序失败诊断](evidence/ch09-u250-routed-diagnosis-20260919/README.md)，不能把行为仿真成功或生成 `.bit` 理解为时序和实卡收发已通过。SSH 私钥、厂商授权及外部 Vivado 安装不属于仓库内文件。大缓存多数受 Git 忽略，只有 Git checkout 不能替代完整的课前缓存。
