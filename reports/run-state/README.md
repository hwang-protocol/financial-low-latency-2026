# FLLE Run State — 运行态说明

> STATUS: ACTIVE STRUCTURE  
> INITIALIZED: 2026-07-21  
> CURRENT RUN STATE: 以本目录中除 README 外的状态文件为准

本目录只保存真实连续工作流需要重复加载的小型状态。此 README 不是运行态；目录中没有其他文件时才表示尚未开始真实运行。存在其他状态文件时，应逐一读取其 `RUN_ID`、状态、范围和恢复点，不能由 README 猜测当前现场。

## 创建规则

实际开始运行时才生成：

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
```

为该工作流创建含义明确的状态文件，例如 `<purpose>.env`、`<purpose>.json` 或 `<purpose>.md`。序列化格式可以不同，但至少记录这些语义字段：

```text
RUN_ID=<实际生成值>
PURPOSE=<用途>
PROFILE_ID=<本轮 profile>
STARTED_AT_UTC=<UTC 时间>
RESULT_DIR=<仓库相对结果目录>
STATUS=<ACTIVE|COMPLETED|FAILED|ABORTED>
```

## 约束

- 后续步骤加载已保存值，不在正文手工填写时间戳。
- 状态文件中的路径优先使用仓库相对路径；外部产物使用受控引用与校验值。
- profile、版本或目标改变且不再属于同一实验时，生成新 `RUN_ID`。
- 失败或中止时更新状态并关联坑本 ID，不删除现场。
- 不保存 secret、口令、私钥、token、license key 或临时高权限凭据。
- 单次结果不能提升为 PINS；只有经核验且跨运行稳定的环境事实才进入 PINS。
