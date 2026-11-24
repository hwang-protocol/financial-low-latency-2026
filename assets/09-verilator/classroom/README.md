# 第九章开发机课堂步骤

先完成最新版第八章 1.1—1.3：`.111` 分发源码与离线包，`.101` 安装
Icarus、Verilator、gcc/g++ 和 make。第八章 `current.env` 必须含 `CH09_SRC`。
这些脚本不恢复 VM 快照，不控制交易系统，也不向行情网络发包。
只有 `collect.sh` 使用管理网 SSH/SCP，把开发结果收回 `.111`。

## 在 .101 分步执行

第一次从第八章分发的源码创建输入快照：

```bash
source /opt/flle-ch08-dev/current.env
bash "$CH09_SRC/classroom/2.1-workspace.sh"
```

后续每张卡先定位本轮源码，再执行表中的一个脚本；重新登录后也使用这两行：

```bash
source /opt/flle-ch09-dev/current.env
bash "$CH09_SRC/classroom/2.2-compile.sh"
```

| 脚本 | 做什么 |
| --- | --- |
| `2.1-workspace.sh` | 新建本轮目录，复制完整源码，记录工具和输入摘要 |
| `2.2-compile.sh` | 分别编译 adapter 和独立 RTL 回归程序，不运行 |
| `2.3-selftest.sh` | 运行六项 adapter 内部测试，不启动网络收发 |
| `2.4-regression.sh` | 运行 14 项 RTL 回归 |
| `b3.1-compile-registers.sh` | 用 Icarus 编译寄存器测试，用 Verilator 检查接口 |
| `b3.2-test-registers.sh` | 用 vvp 执行 110 项寄存器检查 |
| `b6.1-compile-host-tool.sh` | 用 gcc 严格编译 C 工具，不访问硬件 |
| `b6.2-test-host-tool.sh` | 运行五项参数保护测试，在访问 sysfs/MMIO 前拒绝错误输入 |

`/opt/flle-ch09-dev/current.env` 保存本轮位置。源码位于
`$CH09_TEST_DIR/src`，日志位于 `work/`，两个 C++ 构建目录为 `obj_core/`、
`obj_regression/`。每卡自加载运行态并校验输入；源码改变须重新执行 2.1，
生成新一轮，不覆盖原始输入摘要。重新编译会清除相应测试的通过标记。
2.1 新建 RUN 后先发布 `CH09_STATUS=PREPARING`，复制和记录完成才改为
`READY`；中途失败时先修复并重跑 2.1，后续卡会拒绝未就绪的一轮。
原来各 RUN 的目录与 `dev.env` 仍保留。

## 回到 .111 保存结果

2.3、2.4 都通过后执行；完成 B3、B6 后可以再执行一次：

```bash
bash /qyt-fll/assets/09-verilator/classroom/collect.sh
```

每次收集保存到 `reports/course-runs/$CH09_RUN/collection-<UTC>/`，
包括本轮源码、工具记录、日志和产物；旧收集包保留。收回后才恢复 `.101`
快照。快照恢复后先重做第八章准备，再新建第九章 RUN，不能沿用旧目录。
`COLLECTED` 表示两项核心测试通过且归档已收回；B3、B6 的可选结果按各自
日志和通过标记查看，不因归档成功就自动视为通过。

这些检查证明软件模型、寄存器接口与参数保护在测试输入下的行为；
不代表已运行 Vivado、构建器件镜像、装载真卡或实测网口。
