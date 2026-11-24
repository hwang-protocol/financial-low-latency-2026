# 第八章 .101 开发机离线工具缓存

2026-09-18 准备。缓存位于 `.111` 仓库的 `artifacts/blobs/ch08-fpga-dev/`，用于向可恢复快照的 `.101` 开发机分发工具。11 个安装包加 1 个固定版本清单，共 30,628,183 字节（约 29.21 MiB）；没有在 `.111` 安装或升级软件。

[机器可读清单](ch08-fpga-dev-cache.json)逐文件记录版本、字节数、SHA-256、来源 URL 和信任边界。缓存中的 `SHA256SUMS` 使用缓存根目录下的相对路径，传到 `.101` 后可独立核对。

| 用途 | 固定输入 | 来源与处理 |
|---|---|---|
| Verilog / SystemVerilog 仿真 | `iverilog 11.0-1.1`，Ubuntu amd64 deb | 复用本机 APT 缓存；大小和 SHA-256 与 Ubuntu APT 索引一致 |
| 本课 Python 管理逻辑测试 | `six 1.17.0`，纯 Python wheel | 从 [PyPI 固定发行版](https://pypi.org/project/six/1.17.0/)下载 |
| 可移植核心电路综合 | `yowasp-yosys 0.69.0.0.post1233` 及依赖 | 复用 pip HTTP 缓存，全部 wheel 重新与 [PyPI 发行元数据](https://pypi.org/project/yowasp-yosys/0.69.0.0.post1233/)中的 SHA-256 核对 |
| 无 pip 环境的离线引导 | `pip 25.2` wheel | Python 直接从 wheel 中加载 pip，再将固定工具安装到隔离 venv |

`requirements.txt` 原样复制本课 [local-tools-requirements.txt](../assets/08-arista-fpga-draft/local-tools-requirements.txt)，再追加 `six==1.17.0`。没有改动原清单。其余固定包为 `click 8.5.0`、`packaging 26.3`、`platformdirs 4.11.9`、`setuptools 84.0.0`、`wasmtime 47.0.1`、`wheel 0.48.0`、`yowasp-runtime 1.96`。

## 目标机条件

适用 Ubuntu 22.04 amd64、Python 3.10，目标快照实查为 Python 3.10.6。目标机需要 `make`、`dpkg`、`sha256sum`，以及可用的 `venv`、`ssl`、`zipimport` 标准库模块。无需预装 pip；无需联网下载 `get-pip.py`。安装 Icarus 需要 root 或 sudo 权限；Python 工具只写入独立 venv。

Icarus deb 的系统依赖是 `libbz2-1.0`、`libc6 >= 2.34`、`libgcc-s1 >= 3.3.1`、`libreadline8 >= 6.0`、`libstdc++6 >= 11`、`zlib1g >= 1:1.2.0`。主任务已只读核对 `.101` 上这些库存在且版本满足要求；精确版本写在 JSON 清单中。快照恢复或更换目标机后应重新检查。

缓存只包含这一个 deb 和完整的本课 Python wheel 依赖。它依赖目标机已有的 Ubuntu 基础库，**不是从空系统状态解析的 Ubuntu 全依赖闭包**。若基础库缺失，应先修复开发快照或使用已核验的系统工具缓存；这里的安装步骤不会访问公网补包。

可在 `.101` 只读检查基础条件：

```bash
dpkg --print-architecture
python3 --version
python3 -c 'import venv, ssl, zipimport; print("Python standard-library checks passed")'
command -v make dpkg sha256sum
dpkg-query -W -f='${Package} ${Version} ${Status}\n' \
  libbz2-1.0 libc6 libgcc-s1 libreadline8 libstdc++6 zlib1g
```

## 离线安装建议

以下命令供主任务编排到 `.101` 课堂步骤；本缓存准备子任务没有执行远端安装。假设缓存目录已通过管理网传到 `$HOME/flle-ch08-dev/cache`，开发目录可按正文统一调整。

```bash
FLLE_DEV="$HOME/flle-ch08-dev"
FLLE_CACHE="$FLLE_DEV/cache"
cd "$FLLE_CACHE"
sha256sum -c SHA256SUMS
sudo dpkg --dry-run --install "$FLLE_CACHE/deb/iverilog_11.0-1.1_amd64.deb"
sudo dpkg --install "$FLLE_CACHE/deb/iverilog_11.0-1.1_amd64.deb"
python3 -m venv --without-pip "$FLLE_DEV/venv"
PYTHONPATH="$FLLE_CACHE/wheels/pip-25.2-py3-none-any.whl" \
  "$FLLE_DEV/venv/bin/python" -m pip --isolated install \
  --no-index --no-cache-dir --find-links="$FLLE_CACHE/wheels" \
  -r "$FLLE_CACHE/requirements.txt"
"$FLLE_DEV/venv/bin/python" -m pip check
iverilog -V
vvp -V
"$FLLE_DEV/venv/bin/yowasp-yosys" -V
```

首次启动 YoWASP 会将 WebAssembly 程序编译为本机代码并写入运行缓存，可能比后续启动慢；这一步使用本地文件。它能综合本课可移植核心电路，不能替代 BVL 板级工程、Vivado、PDI 构建或真机验证。

## 核对与恢复边界

本次已完成全部安装包摘要核对、离线 pip 依赖解析，以及从 `pip 25.2` wheel 直接加载 pip 的检查。离线解析使用 `--dry-run --ignore-installed --no-index`，没有把 `.111` 已安装的包当作缓存依赖。`.101` 上的安装、仿真和综合运行结果由主任务另记。

关键摘要：

| 文件 | SHA-256 |
|---|---|
| `deb/iverilog_11.0-1.1_amd64.deb` | `56b2b91e23f51c571b8cf43ef2df3a137a1bf4b6bcbff0fa3463b5b89403a852` |
| `SHA256SUMS` | `46640355f35963cd3a31ae0d57450e2ff263b5c2a456a3333a9f3f129590d471` |

缓存二进制仍被现有 Git 规则忽略；只恢复 Git 中的清单不能恢复包字节。应保留 `.111` 缓存，丢失后按 JSON 内固定 URL 重取并核对固定 SHA-256。文件已追加登记到总 artifact 清单；Git 忽略规则和恢复白名单保持。
