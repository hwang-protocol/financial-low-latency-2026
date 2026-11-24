# Socket实现位置与中英文图名

2026-09-09；DEC-413；DRAFT / NOT FROZEN。

用户连续要求：把接口兼容与实现位置的解释写得更短、控制加粗；普通内核和Onload两处都显示Socket；图名采用中文（英文）。正文已压短，旁路段及两行表取消额外Markdown加粗，保留硬件分工和内核资源管理。Onload图两处标“套接字（Socket）接口实现”，业务侧为“套接字调用”，库框加高；普通收包与总结图改“中断（IRQ）”“批量收包（NAPI）”，主图接收队列增加Socket中文名。独立高级延伸编号保持。

[AMD Onload透明接入](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency)支持接口兼容与库实现的说明；[AMD VNIC](https://docs.amd.com/r/en-US/ug1586-onload-user/Virtual-Network-Interface-VNIC)支持硬件分流和隔离资源；[AMD CTPIO](https://docs.amd.com/r/en-US/ug1586-onload-user/CTPIO)核对X2专门发送路径。没有把协议栈整体移到网卡，也未将硬件能力的存在包装成此次连接的实测性能贡献。正文不展开CTPIO新机制，留第六部分。

验证：三图XML、800/1200目视、77处文字边界、12箭头固定12×12头部和两端12px间隙通过。全章15表/HTML、11章74卡、08～10章18执行卡和24图片引用通过；SHA29/214项匹配。正文仍十图，实验代码和输出与本轮修改前逐字一致。diff空白检查通过。[最终收据](evidence/socket-labels-20260909.json)；较早纯文字阶段收据socket-wording为中间状态，最终以本收据为准。

本轮没有实机操作、重采或新RUN；无PINS事实漂移或新增坑本。待提交：正文、三SVG、教师说明、两级README/SHA、DECISIONS/FREEZE-LEDGER/NEXT-AI-HANDOFF、本报告与两份收据。前轮改动保持，AI未提交/推送。

建议提交说明：`docs: clarify Socket implementations and bilingual diagram labels`。
