# 总结图的中断与读取顺序

2026-09-09；DEC-414；DRAFT / NOT FROZEN。

第6节总结图原把中断标⑤，容易使读者按编号认为读取在通知之前。现改①DMA写入、②IRQ通知、③④处理器取数与处理、⑤应用读取。箭头ID/标签/描述、图内阅读提示及正文alt/图注同步；A～D四等待点、图形和连线路径保持。按常见中断驱动路线讲解，不把这一顺序推广到所有主动轮询场景。

验证：800/1200目视、32处文字边界、五箭头编号与源目角色对应、12×12头部与两端12px间隙通过。全章15表/HTML、11章74卡与08～10章18执行卡/24图片引用通过，SHA29/214项匹配，diff空白检查通过。正文仍十图，其他九个img标签与全部实验代码/输出保持。见[验证收据](evidence/receive-order-20260909.json)。

无设备操作、实验重跑、新RUN或新PINS事实。待提交为正文、总结SVG、教师说明、两级图册README/SHA、DECISIONS/FREEZE-LEDGER/NEXT-AI-HANDOFF、本报告与收据；前轮改动保持。AI未提交或推送。

建议提交说明：`docs: order receive diagram around interrupt notification`。
