# 第五章 POSIX QoS 增量客户端

在固定 v13 源码上应用 `client.patch`，只构建 Kernel Socket／Onload 共用的 `flle-trader`。原 v13 包、TCPDirect、DPDK 与普通软件课客户端不改。

## 维护者构建

在已有 GCC 11 的 Ubuntu 22.04 amd64 编译环境中运行：

```bash
python3 apps/flle-trading-lab/releases/posix-qos-v1/build.py \
  --compiler g++-11 --output /tmp/flle-posix-qos-build
```

也可用 `--compiler /path/to/g++-11 --sysroot /path/to/extracted-debs` 指向离线缓存解出的工具链。本轮实际使用 `.111` 的 Jammy v2 缓存，构建时仅写 `/tmp` 和仓库。脚本固定校验原源码摘要，生成完整源文件、构建记录、文件清单和运行包；发布新字节必须同步 `flle_trading/posix_qos.py` 的固定合同及 vault 清单，不能覆盖 v13。

## 使用与验证

第五章准备 B 调用 `scripts/prepare-posix-qos.sh` 分发。`ORDER_DSCP|GET` 查询；`ORDER_DSCP|46|PID` 设置，`ORDER_DSCP|0|PID` 恢复。管理线程发请求，空闲订单线程执行 Socket 操作；超时取消未执行请求，不在计时收发路径里读文件或调用 setsockopt。

`test_client.py` 需要本机回环套接字及 CAP_NET_RAW，用 `FLLE_QOS_TEST_BINARY` 指定解包后的 ELF。覆盖真实包头、同连接切换、无连接默认值、PID 不符拒绝、忙时拒绝、重连与正式测量门控；不接触实验 VM。

本轮为 LOCAL PASS，X2522 Onload / Arista QoS 现场重跑仍待确认。历史性能读数不能当作更新后的重测结果。
