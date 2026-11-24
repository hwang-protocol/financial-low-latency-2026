# FLLE 宿主机观测面

本目录是第四章使用的 provisioned 配置，不进入交易热路径：

| 文件 | 作用 |
| --- | --- |
| `prometheus.yml` | 每秒抓取 `.101:8088/metrics` |
| `grafana.ini` | 监听 `10.1.1.101:3000`，在隔离课程网开放匿名 Viewer |
| `grafana-datasource.yml` | 固定 `FLLE Prometheus` datasource |
| `grafana-dashboard-provider.yml` | 从本机目录加载课程 dashboard |
| `flle-trading-baseline.json` | 八块低延时课程面板 |
| `flle-software-hot-path.json` | 第五章真实 C++ 队列、线程交接与 CPU 放置面板 |

恢复与只读核对统一由 `../scripts/observabilityctl.sh` 完成。生产环境不得照搬匿名访问配置。
