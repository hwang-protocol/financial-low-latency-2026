本目录不是第三幕结果。

`ptp mode boundary` 写完立刻 `show ptp` 仍是 `Disabled`，`monitor session` 也还停在 `Unknown`。脚本把瞬时状态当成失败并恢复。这两项都要等进程起来：正式入口改为轮询到 `Boundary Clock` 和 `Rx Only` / `active`。

交易未停，交换机已恢复，startup 未写。
