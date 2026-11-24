# FLLE 大文件与容器镜像预热清单

> 状态：`2026-08-20 课程顺序重跑时重新核对；本表用于锁定预热载荷身份，不把旧快照运行态当作当前运行态`  
> 阈值：普通预热载荷的单文件大小必须 `>=10,000,000 bytes`  
> 范围：四台 Ubuntu VM 的阿里云 APT 源；`.1/.2/.11` 只放大文件；`.101` 另只允许安装 Docker、Docker Compose 并拉取镜像

这份清单回答四件事：字节原来从哪里来、现在放在哪里、怎样送达、以后哪一章使用。它也明确记录预热没有做什么，防止把“文件或镜像已经在本机”误写成“课程软件已经配置完成”。

## 普通大文件逐项清单

Ubuntu 包由目标 VM 直接通过 HTTPS 从阿里云 Jammy 仓库下载；TRex 由跳板机现有受控 blob 经管理网 `scp` 送到 `.11`。表中的 SHA-256 均在目标 VM 上复核。

| 目标 VM | 绝对路径 / 文件 | 字节数 | SHA-256 | 原始来源与送达方式 | 课程用途 |
| --- | --- | ---: | --- | --- | --- |
| `.1` | `/opt/flle/prewarm/apt/cpp-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 10,000,304 | `5243177370b810cc40341801a3b8def6cdd7477ac765862f7727a868629947a3` | 阿里云 Ubuntu Jammy；VM 直接 HTTPS 下载 | 第6章编译 Onload/TCPDirect 时注入 APT cache |
| `.1` | `/opt/flle/prewarm/apt/g++-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 11,424,396 | `ddbaa04f056637caa11798750638bf4586c8b273719fd1bee70d0ecb3d872b94` | 同上 | 同上 |
| `.1` | `/opt/flle/prewarm/apt/gcc-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 20,143,406 | `5422307110e695d62a2574c8b765bf38d48b2ed520206e5b7d2b9081a68008f3` | 同上 | 同上 |
| `.2` | `/opt/flle/prewarm/apt/cpp-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 10,000,304 | `5243177370b810cc40341801a3b8def6cdd7477ac765862f7727a868629947a3` | 阿里云 Ubuntu Jammy；VM 直接 HTTPS 下载 | 第6章编译 Onload/TCPDirect 时注入 APT cache |
| `.2` | `/opt/flle/prewarm/apt/g++-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 11,424,396 | `ddbaa04f056637caa11798750638bf4586c8b273719fd1bee70d0ecb3d872b94` | 同上 | 同上 |
| `.2` | `/opt/flle/prewarm/apt/gcc-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 20,143,406 | `5422307110e695d62a2574c8b765bf38d48b2ed520206e5b7d2b9081a68008f3` | 同上 | 同上 |
| `.11` | `/opt/flle/prewarm/trex/v3.08.tar.gz` | 284,092,535 | `d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f` | 归因 URL `https://trex-tgn.cisco.com/trex/release/v3.08.tar.gz`；跳板机 `artifacts/blobs/trex/3.08/v3.08.tar.gz` 经 `scp` 送达 | 第07章 QoS / LANZ 受控负载；当前只有归档 hash 信任边界，没有 publisher 签名 |
| `.101` | `/opt/flle/prewarm/apt/cpp-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 10,000,304 | `5243177370b810cc40341801a3b8def6cdd7477ac765862f7727a868629947a3` | 阿里云 Ubuntu Jammy；VM 直接 HTTPS 下载 | 第5章 C++，第9/10章复用编译器 |
| `.101` | `/opt/flle/prewarm/apt/g++-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 11,424,396 | `ddbaa04f056637caa11798750638bf4586c8b273719fd1bee70d0ecb3d872b94` | 同上 | 同上 |
| `.101` | `/opt/flle/prewarm/apt/gcc-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 20,143,406 | `5422307110e695d62a2574c8b765bf38d48b2ed520206e5b7d2b9081a68008f3` | 同上 | 同上 |
| `.101` | `/opt/flle/prewarm/p4/gfortran-11_11.4.0-1ubuntu1~22.04.3_amd64.deb` | 11,197,620 | `ee65e9a01021dde724545d35c94b584a7d5d1e65f36faab48358f2ac0d6980da` | 阿里云 Ubuntu Jammy；在隔离 APT 目录解析 P4 fresh 依赖后直接下载 | 第9章 P4 工具链大依赖 |
| `.101` | `/opt/flle/prewarm/p4/libclang-cpp14_1%3a14.0.0-1ubuntu1.1_amd64.deb` | 12,053,266 | `462546f6149fbef99b47f3e1e01e0743d256ae279337c7f89a80a976dfd02175` | 同上 | 同上 |
| `.101` | `/opt/flle/prewarm/p4/libicu-dev_70.1-2_amd64.deb` | 11,604,612 | `1923e57f02a96595e2111c203dbb660f4c5abae46d7bee83a0ccb8b002eb6fc3` | 同上 | 同上 |
| `.101` | `/opt/flle/prewarm/p4/libllvm14_1%3a14.0.0-1ubuntu1.1_amd64.deb` | 23,967,046 | `9044b614a6c7fb6262e7cbeb13dc731fc0c92bed96281c1a3920dd706442ee8e` | 同上 | 同上 |
| `.101` | `/opt/flle/prewarm/p4/llvm-14_1%3a14.0.0-1ubuntu1.1_amd64.deb` | 12,692,892 | `174282e5c85c7b31fbfcc3aa7193488ccec53bc50003c42f70ad1e56ba75d59f` | 同上 | 同上 |
| `.101` | `/opt/flle/prewarm/p4/p4lang-p4c_1.2.4.2-3_amd64.deb` | 42,790,678 | `01bbb2de771b165e5c881bf2e365facc78335a32ffb08a48288e7332834064fe` | `download.opensuse.org/repositories/home:/p4lang/xUbuntu_22.04/`；临时校验 OBS key 后，在隔离 APT 目录直接下载 | 第9章 P4C；临时 source/key 下载完成即删除 |

P4 fresh 依赖解析共发现约 277 MB 的候选下载，但只把上表中达到阈值的 6 个包留下；`p4lang-bmv2`、PI 和其余依赖都低于阈值，刷到第9章时在线安装。

## `.101` Docker 与镜像清单

`.101` 从阿里云 Jammy 安装 `docker.io 29.1.3-0ubuntu3~22.04.2`、`docker-compose-v2 2.40.3+ds1-0ubuntu1~22.04.1`，以及 APT 自动解析的运行依赖 `containerd 2.2.1-0ubuntu1~22.04.2`、`runc 1.3.4-0ubuntu1~22.04.1`。这四项是本轮唯一允许预装的软件。

| 镜像标签 | 本地内容大小（bytes） | 已验证内容 digest / image ID | 官方来源与实际拉取路径 | 课程用途 |
| --- | ---: | --- | --- | --- |
| `quay.io/prometheus/prometheus:v2.31.2` | 74,733,637 | `sha256:05128da5ddc760fef7760b93da9883611426658b0dd707ee8d7886923487b472` | Prometheus 官方 Quay，直接 `docker pull` | 第4章 Prometheus；后续绿色卡经 SSH + CAT 写入 Compose YAML 后创建服务 |
| `quay.io/prometheus/node-exporter:v1.3.1` | 10,347,719 | `sha256:f2269e73124dd0f60a7d19a2ce1264d33d08a985aed0ee6b0b89d0be470592cd` | Prometheus 官方 Quay，直接 `docker pull` | 第4章 Node Exporter |
| `grafana/loki:3.7.2` | 47,660,888 | `sha256:800ec439ed2692b79c5a1fe17a6d2955f8999ad5d05f0276c6e4a10ac11cc491` | 官方 Docker Hub digest；Docker Hub 数据面 EOF 后，按同一 amd64 digest 经 `docker.m.daocloud.io` 拉取并加官方标签 | 第4章 Loki |
| `grafana/grafana:13.1.0` | 377,931,181 | `sha256:6ea068891652aa6a65ca9065c26b89de939653803c836426970305c11fd00534` | 官方 Docker Hub digest；按同一 amd64 digest 经 `docker.m.daocloud.io` 拉取并加官方标签 | 第4章 Grafana |

Docker 镜像位于 Docker 自己的内容寻址存储（`/var/lib/docker`），不是人为复制的 tar 文件。镜像的内容 digest 与官方 amd64 digest一致；传输镜像只改变下载路径，不改变被 digest 锁定的内容。

## 预热实际做了什么、没有做什么

| 项目 | 快照中实际状态 |
| --- | --- |
| Ubuntu APT | 四台 VM 的 Jammy base/updates/backports/security 已切到阿里云并完成 `apt-get update`；这是用户明确允许的基础配置 |
| 普通预热 | 只保留上表达到阈值的 `.deb` 和 TRex 归档；下载日志、临时 key/source、临时 GPG home 和 VM 内校验清单已删除，校验值集中保存在本文 |
| `.101` 容器能力 | 只安装 Docker、Docker Compose 及必需运行依赖，只拉取四个镜像；容器数量必须为 0 |
| Compose 配置 | **VM 上没有 Compose YAML，也没有 `/opt/flle/compose`**；完整 YAML 直接写在第4章绿色卡中，执行卡片时经 SSH 登录并用 CAT heredoc 写入VM，不用 `scp` |
| 课程软件 | 没有安装 GCC/G++、Onload、TCPDirect、P4C、BMv2、PI、Verilator、TRex、Prometheus、Node Exporter、Loki 或 Grafana 原生包 |
| 运行态 | 没有创建/启动容器，没有启用课程服务，没有加载课程驱动，没有改数据口/IP，没有分配 hugepage，没有挂 XDP，没有改交换机 |

## 快照后如何使用

学生不手工处理本表中的文件。对应章节最早需要软件时，绿色准备卡先验证这里固定的大小和 SHA/digest，再把本地大 `.deb` 注入 APT cache 或使用已拉取镜像；小包仍从阿里云或已验签第三方源在线获取。第4章绿色卡全文内嵌 Compose YAML，通过 SSH 登录 `.101` 后用 CAT heredoc 写入，只用 `docker compose` 启动观测栈，不用 `scp` 配置，也不提供 `docker run` 路径。

## 2026-08-20 当前使用边界复核

本表中的大小、SHA-256、镜像 digest 与交付路径继续作为准备卡的输入合同；现役 00–10 顺序重跑时，各章准备卡实际复核所需载荷并完成安装或启动，不能再把“课程软件未安装、容器数为 0”写成当前现场结论。

当前课程态由各章现役 RUN 分层证明：第 4 章确认 `.101` 的 Prometheus、Node Exporter、Loki、Grafana 均 ready；第 5/6/7/9/10 章分别确认编译器、Onload/TCPDirect、linuxptp 与 TRex、P4、Verilator 载荷可用。第07～09章各自归还临时在线资源，第10章只做离线仿真；原第11、12章 RUN 只作历史证据。预热清单只证明载荷身份和来源，现场是否干净仍必须读取对应现役实验的退出收据。
