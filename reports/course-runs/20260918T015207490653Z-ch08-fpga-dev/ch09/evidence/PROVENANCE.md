# 第10章 2026-08-20 现场仿真证据来源

这些文件均由同一轮 `20260820T031742Z-10-verilator-live` 在 `.101` 上重新编译
tracked RTL 与 C++ harness 后生成。该轮覆盖正常 pipeline、两次 VCD、RTL assertion
mutant、独立 scoreboard mutant 与 midstream reset；不是旧证据的阅读副本。

| 课程资产 | 本轮原始文件 | SHA-256 |
| --- | --- | --- |
| `market-pipeline.log` | `raw/remote/market-pipeline-run1.log` | `f5f372f3a18601d7047572e7b106ec74370de1c64cd6fe790ebc9cfeb4b3cea8` |
| `vcd-audit.json` | `raw/remote/vcd-audit-run1.json` | `420474c01e4178d0d1689bc647d0ecb728401ca7033b99a2eb9c3009ce626743` |
| `vcd-sha256.txt` | `raw/remote/vcd-sha256.txt` | `2f5184e0b6361c99ffde6eda3fdb793a1550aba135b07823424fb3d72d144462` |
| `market_pipeline-run1.vcd` | `raw/remote/market_pipeline-run1.vcd` | `5d587d271f57d7c707af64fcb4817856b29777c45cf33a81873f2532f4187e53` |
| `market_pipeline-run2.vcd` | `raw/remote/market_pipeline-run2.vcd` | `5d587d271f57d7c707af64fcb4817856b29777c45cf33a81873f2532f4187e53` |
| `assert-mutant.log` | `raw/remote/assert-mutant.log` | `bfc43a7c96f3d1f301b2a9275d75c4781f0e7929f0421f745a0d4b52cadb63d4` |
| `scoreboard-mutant.log` | `raw/remote/scoreboard-mutant.log` | `d183a46cf00d14c51bc3654c832bf08cb6ecfbb813bdf4846fd5b4bc7fc7e4f3` |
| `reset-boundary.json` | `raw/remote/reset-boundary.json` | `3cd90542d709c08f3cb2f728892525635e619e178d270ef6dcab92b05d2f0efc` |

完整现场树位于
`Documents/reports/newdoc-full-live-20260820/live/verilator/20260820T031742Z-10-verilator-live/`。
其中 `raw/remote-console.log` 保存版本、13 个 case、3 个 stall、VCD 审计、两类
mutant 被预期检测以及 reset PASS 的连续输出；完整构建日志、覆盖文件和 reset VCD
也保留在 `raw/remote/`。

本轮重新使用的 tracked 源文件及 SHA-256：

| tracked 源文件 | SHA-256 |
| --- | --- |
| `../market_pipeline.sv` | `feec7c419c81ac1c68b8b67af58b59b8d5a2ca551e2df04470478d1d4085d963` |
| `../sim_main.cpp` | `bbe1d30cab2abea0e31272980b34666ed2a5efb366efc254b2f3bd5e5e4be5f4` |
| `../audit_vcd.py` | `d768bc34c58ef6f0bc1aee2a97082a4c590339c5d0674c330c3e576046293f06` |
| `../market_pipeline_assert.sv` | `0c8c2a4fd3ffacf0d248d956d88788f81b502d049b725cb356c4ca103f296d16` |
| `../random_scoreboard.cpp` | `331c3e8609e49fde8bf17e401b023dfb9813762553af0733b8165274e875667d` |
| `../market_pipeline_reset.sv` | `14809799a358ea6eb5425faad3d14be208ac350c5ea90af758058aa7667f809c` |
| `../reset_scoreboard.cpp` | `82b95768f4e50ddb03d7f5b581f7647853dcb0f136c600b839ef875de7a805ec` |

证据边界仍是 Verilator software cycle model，不外推为 FPGA 板卡烧录、Fmax、资源、
功耗、真实 I/O 或线速性能。
