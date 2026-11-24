# Arista 官方 LANZ 客户端的课程读取入口

- 官方库：https://github.com/aristanetworks/goarista/tree/master/lanz
- 固定版本：`v0.0.0-20251201112602-a373d7c9f0d9`，提交 `a373d7c9f0d9de57f4e1fcfe9adc868c7104f9cd`。
- 编译器：Go `1.24.13`；Google Protobuf 运行库：`v1.36.10`。
- `client.Run(events)` 由官方库读取长度、读满记录、调用官方 Protobuf 解码并自动重连。`main.go` 不实现帧拆分或 Protobuf 解码，只通过生成的 getter 取字段并格式化。
- `WithConnector` 是官方扩展接口，本课仅用它给网页报告连接/断开状态。原始字节仍交给官方客户端读取和解码；上游源码没有补丁。

## 下载、构建与使用

本目录已有固定版本的 `go.mod` / `go.sum`。课前在有 Go 的管理机执行：

```bash
go mod download
go mod vendor
bash build.sh
./flle-lanz-reader -version
./flle-lanz-reader -addr 10.1.1.253:50001 -count 2
```

`-count` 只计拥塞记录，配置与连接提示不计数；默认 `0` 持续读取，无拥塞时等待。`-json` 输出一行一个对象，供 `lanz_stream_collector.py` 维护原有事件列表和 HTTP 接口。该 Python 文件不再处理 LANZ 二进制。

## 离线恢复

管理机缓存位于 `artifacts/blobs/arista/lanz-reader-v1/`。Git 精确保存静态二进制、带 vendor/许可证的源码包和构建记录。Go 安装包仅用于维护时重新编译，课堂运行不依赖它。第二章上线入口将读取工具安装到 `.101:/opt/flle/lanz-reader-v1/`；旧第四章快照使用同一入口的 `--prepare-capabilities` 补齐。运行 ③ 在改现场配置之前先核对已安装工具，随后启动官方读取工具与原网页接口。`.101` 无需 Go 编译器或网络下载。

源码包解压后可运行 `GO_BIN=/path/to/go bash build.sh` 离线重建。`vendor` 由固定版本的 `go mod vendor` 生成，不手工更改官方包；依赖原始摘要记录在 `go.sum`。

## 时间字段

适配器 v1.1 明确限定本课 DCS-7150S / EOS 4.23.16M-2GB：`timestamp_raw` 保留官方解码值，`timestamp_tick_us=10` 表示每刻度 10 µs，`timestamp_us=timestamp_raw×10` 用于显示 UTC 时刻。官方 SDK 只解码，不代做单位换算。EOS 手册对 config/congestion 单位的描述不一致，此处以本机时钟和同批 EOS 记录核对，不外推其他机型。终端 duration 是交换机的独立字段，不能用有 10 µs 粒度的 S/E 时刻差替代。

## 验证边界

已跑 Arista LANZ 包的六项上游测试；本课回环 TCP 测试覆盖拆分、合并、重连与字段输出；Python 集成测试覆盖官方读取结果进入原 HTTP API、清空历史及 SIGTERM 后关闭子进程和连接。未以这些模拟事件冒充 7150 实测。v1.1 已于 2026-09-17 完成 7150 / TRex 实跑：10k=0，25k累计163次，EOS与接收器最近80条逐条一致；网页实际显示与展开检查通过。记录见 `refs/evidence/lanz-display-fix-20260917/`。
