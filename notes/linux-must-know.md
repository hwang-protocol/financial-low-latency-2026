# Linux 必背知识点

面向网络工程师、SRE、低延迟方向。按重要程度分三级：

- ⭐⭐⭐ 必须熟练，面试和日常工作天天用
- ⭐⭐ 要会，遇到问题时能想起来
- ⭐ 低延迟方向加分项

---

## 1. 文件与目录 ⭐⭐⭐

| 命令 | 作用 | 常用写法 |
|---|---|---|
| `pwd` / `cd` / `ls` | 当前目录、切换目录、列文件 | `ls -lah`（详细、含隐藏文件、人类可读大小） |
| `cp` / `mv` / `rm` / `mkdir` | 复制、移动或改名、删除、建目录 | `cp -r`、`rm -rf`（小心！）、`mkdir -p a/b/c` |
| `cat` / `less` / `head` / `tail` | 看文件内容 | `tail -f /var/log/syslog`（实时跟踪日志） |
| `find` | 按条件找文件 | `find / -name "*.conf" 2>/dev/null` |
| `ln -s` | 建软链接 | `ln -s /opt/app/current /opt/app/live` |
| `du` / `df` | 目录占用、磁盘剩余 | `du -sh *`、`df -h` |
| `tar` | 打包解包 | `tar -czf x.tgz dir/`、`tar -xzf x.tgz` |

**目录结构要知道：**

| 目录 | 放什么 |
|---|---|
| `/etc` | 配置文件 |
| `/var/log` | 日志 |
| `/home`、`/root` | 用户家目录 |
| `/tmp` | 临时文件，重启可能被清空 |
| `/proc`、`/sys` | 内核实时信息，不是真实文件（CPU、内存、网卡状态都从这里读） |
| `/usr/bin`、`/usr/local/bin` | 程序 |
| `/dev` | 设备文件 |

---

## 2. 文本处理 ⭐⭐⭐

排查日志、处理命令输出全靠这几个。

| 命令 | 作用 | 例子 |
|---|---|---|
| `grep` | 按内容搜索 | `grep -rn "ERROR" /var/log/`、`grep -v`（反选）、`grep -i`（忽略大小写）、`grep -E`（正则） |
| `awk` | 按列取数据 | `awk '{print $1, $3}'`、`awk -F: '{print $1}' /etc/passwd` |
| `sed` | 替换文本 | `sed -i 's/old/new/g' file` |
| `sort` / `uniq` | 排序、去重计数 | `sort \| uniq -c \| sort -rn`（统计出现次数最多的） |
| `cut` / `wc` | 截取列、计数 | `wc -l`（数行数） |
| `xargs` | 把输出变成参数 | `find . -name "*.log" \| xargs rm` |

**管道和重定向：**

```bash
cmd1 | cmd2          # 管道：cmd1 的输出给 cmd2
cmd > file           # 覆盖写入
cmd >> file          # 追加
cmd 2> err.log       # 只重定向错误输出
cmd > all.log 2>&1   # 正常输出和错误输出都写进文件
cmd &> /dev/null     # 全部丢掉
```

---

## 3. 权限与用户 ⭐⭐⭐

```
-rwxr-xr--  1 alice dev  1024 file
│└┬┘└┬┘└┬┘
│ │  │  └── 其他人：r--  = 4
│ │  └───── 组：    r-x  = 5
│ └──────── 所有者：rwx  = 7
└────────── 类型：- 文件，d 目录，l 链接
```

| 命令 | 作用 |
|---|---|
| `chmod 755 file` / `chmod +x file` | 改权限 |
| `chown user:group file` | 改所有者 |
| `sudo` / `su -` | 临时用 root 执行 / 切换成 root |
| `id` / `whoami` | 看自己是谁、属于哪些组 |
| `useradd` / `passwd` / `usermod -aG group user` | 建用户、改密码、加入组 |

**必须记住：** r=4、w=2、x=1；目录要有 `x` 才能进入；`/etc/passwd` 存用户信息，`/etc/shadow` 存密码哈希。

---

## 4. 进程与服务 ⭐⭐⭐

| 命令 | 作用 |
|---|---|
| `ps aux` / `ps -ef` | 看所有进程 |
| `top` / `htop` | 实时看 CPU、内存占用 |
| `kill PID` / `kill -9 PID` | 正常结束 / 强制杀掉 |
| `pgrep` / `pkill` | 按名字找进程、杀进程 |
| `nohup cmd &` | 后台运行，退出终端也不停 |
| `jobs` / `fg` / `bg` / `Ctrl+Z` | 前后台切换 |
| `systemctl start/stop/restart/status/enable xxx` | 管理系统服务 |
| `journalctl -u xxx -f` | 看某个服务的日志 |

**要理解：**
- 常见信号：`SIGTERM`(15) 让程序优雅退出，`SIGKILL`(9) 直接杀、不能被拦截，`SIGHUP`(1) 常用于重新加载配置
- 僵尸进程（Z）：进程已结束，但父进程还没回收它
- `load average` 三个数分别是 1、5、15 分钟的平均负载，和 CPU 核数比较才有意义

---

## 5. 网络 ⭐⭐⭐（网络工程师重点）

| 命令 | 作用 | 替代了哪个老命令 |
|---|---|---|
| `ip addr` / `ip a` | 看 IP 和网卡 | `ifconfig` |
| `ip link set eth0 up/down` | 开关网卡 | |
| `ip route` | 看路由表 | `route -n` |
| `ip neigh` | 看 ARP 表 | `arp -a` |
| `ss -tulnp` | 看哪些端口在监听、被哪个进程占用 | `netstat -tulnp` |
| `ping` / `traceroute` / `mtr` | 连通性、路径、持续测丢包和延迟 | |
| `dig` / `nslookup` | DNS 查询 | |
| `curl -v` / `wget` | 测 HTTP | |
| `nc -zv host port` | 测端口通不通 | `telnet host port` |
| `tcpdump` | 抓包 | |
| `ethtool eth0` | 看网卡速率、驱动、统计 | |
| `iptables` / `nft` | 防火墙规则 | |

**tcpdump 必背：**

```bash
tcpdump -i eth0 -nn host 1.2.3.4 and port 443
tcpdump -i eth0 -nn -w cap.pcap -c 1000 udp port 42121
tcpdump -r cap.pcap -nn
tcpdump -i any -nn 'tcp[tcpflags] & tcp-syn != 0'
```

**配置文件：** `/etc/hosts`（本机域名解析）、`/etc/resolv.conf`（DNS 服务器）、`/etc/netplan/`（Ubuntu 网络配置）、`/etc/ssh/sshd_config`（SSH 服务配置）。

**要理解：** TCP 三次握手和四次挥手、TCP 状态（`LISTEN`、`ESTABLISHED`、`TIME_WAIT`、`CLOSE_WAIT`）、MTU、默认网关、子网掩码。

---

## 6. SSH ⭐⭐⭐

```bash
ssh-keygen -t ed25519                 # 生成密钥
ssh-copy-id user@host                 # 把公钥装到对方机器
ssh -i key.pem user@host              # 指定私钥登录
ssh -J jump user@target               # 经过跳板机
ssh -L 8088:10.0.0.5:8088 user@host   # 本地端口转发（把远端服务带到本机）
ssh -R 2222:localhost:22 user@host    # 反向转发
scp file user@host:/path/             # 复制文件
rsync -avz dir/ user@host:/path/      # 增量同步，比 scp 好用
```

`~/.ssh/config` 写别名，`~/.ssh/authorized_keys` 存允许登录的公钥。权限要正确：`~/.ssh` 是 700，私钥是 600。

---

## 7. 软件包 ⭐⭐

| 发行版 | 命令 |
|---|---|
| Ubuntu / Debian | `apt update`、`apt install xxx`、`apt remove xxx`、`dpkg -l` |
| RHEL / Rocky / CentOS / Amazon Linux | `dnf install xxx`（老版本用 `yum`）、`rpm -qa` |

---

## 8. 磁盘与内存 ⭐⭐

| 命令 | 作用 |
|---|---|
| `free -h` | 内存使用（注意 `available` 列，不是 `free` 列） |
| `df -h` / `du -sh` | 磁盘剩余 / 目录大小 |
| `lsblk` / `blkid` | 列出磁盘和分区 |
| `mount` / `umount` / `/etc/fstab` | 挂载、开机自动挂载 |
| `iostat -x 1` / `vmstat 1` | 磁盘 IO、整体系统状态 |

**要理解：** Linux 会把空闲内存拿来做缓存（buff/cache），所以 `free` 很小不代表内存不够；swap；OOM Killer（内存耗尽时内核会杀进程）。

---

## 9. 日志与排障 ⭐⭐⭐

| 命令 / 位置 | 看什么 |
|---|---|
| `journalctl -xe` / `journalctl -u nginx --since "10 min ago"` | systemd 日志 |
| `/var/log/syslog`（Ubuntu）、`/var/log/messages`（RHEL） | 系统日志 |
| `/var/log/auth.log` / `/var/log/secure` | 登录记录 |
| `dmesg -T` | 内核消息（网卡、驱动、OOM 都在这里） |
| `last` / `who` / `w` | 谁登录过、现在谁在线 |
| `strace -p PID` | 看进程在做哪些系统调用 |
| `lsof -i :8080` / `lsof -p PID` | 谁占了端口、进程打开了哪些文件 |

**排障思路（面试常问“服务器很慢怎么办”）：**

1. `uptime`：看负载
2. `top`：CPU 被谁吃了？`wa` 高说明在等磁盘
3. `free -h`：内存够不够，有没有在用 swap
4. `df -h`：磁盘满了没有
5. `iostat -x 1`：磁盘忙不忙
6. `ss -s`、`ss -tan`：连接数、有没有大量 `TIME_WAIT` 或 `CLOSE_WAIT`
7. `dmesg -T | tail`：内核有没有报错
8. `journalctl` 和应用日志

---

## 10. Shell 脚本基础 ⭐⭐

```bash
#!/usr/bin/env bash
set -euo pipefail                  # 出错就停、未定义变量报错、管道中任何一步失败都算失败

NAME="world"
echo "hello $NAME"

if [ -f /etc/hosts ]; then echo "exists"; fi

for host in ex1 tr2; do
  ssh "$host" uptime
done

result=$(date +%F)                  # 把命令输出存进变量
echo $?                             # 上一条命令的退出码，0 表示成功
```

**定时任务：** `crontab -e`，格式是 `分 时 日 月 周 命令`，例如 `*/5 * * * * /path/script.sh` 表示每 5 分钟执行一次。

**环境变量：** `export PATH=$PATH:/opt/bin`；写进 `~/.bashrc` 才能永久生效。

---

## 11. 低延迟方向加分项 ⭐

这门课 00、04、05、07 章会用到。

| 主题 | 命令 / 位置 | 作用 |
|---|---|---|
| CPU 信息 | `lscpu`、`nproc`、`cat /proc/cpuinfo` | 核数、NUMA、超线程 |
| NUMA | `numactl --hardware`、`numactl --cpunodebind=0 --membind=0 cmd` | 让程序用离网卡近的 CPU 和内存 |
| 绑核 | `taskset -c 2 cmd`、`taskset -p PID` | 把线程固定在某个 CPU 上 |
| CPU 隔离 | 内核启动参数 `isolcpus=`、`nohz_full=`、`rcu_nocbs=` | 不让其他进程打扰交易线程 |
| 中断 | `cat /proc/interrupts`、`/proc/irq/*/smp_affinity` | 网卡中断交给哪个 CPU 处理 |
| 调频 | `cpupower frequency-set -g performance` | 让 CPU 一直跑满频率 |
| 内核参数 | `sysctl -a`、`/etc/sysctl.d/`，例如 `net.core.rmem_max` | 网络缓冲区等调优 |
| 大页内存 | `/proc/meminfo` 里的 `HugePages`，`/sys/kernel/mm/hugepages/` | DPDK 需要 |
| 网卡调优 | `ethtool -c`（中断合并）、`ethtool -g`（收发队列长度）、`ethtool -S`（详细统计，看丢包） | |
| 性能分析 | `perf stat`、`perf top`、`perf record` | 缓存未命中、分支预测失败、热点函数 |
| 实时调度 | `chrt -f 50 cmd` | 用实时优先级运行 |
| 内核旁路 | `onload`、DPDK 的 `dpdk-devbind.py` | 绕过内核协议栈收发包 |
| eBPF / XDP | `bpftool`、`ip link set dev eth0 xdp obj prog.o` | 在驱动层处理包 |

---

## 12. 面试高频概念题

1. 进程和线程的区别？
2. 软链接和硬链接的区别？
3. `kill -9` 和 `kill` 的区别？
4. 怎么看哪个进程占用了 8080 端口？（`ss -tulnp | grep 8080` 或 `lsof -i :8080`）
5. 磁盘满了，但 `du` 加起来没那么大，为什么？（文件已删除，但还有进程开着它：`lsof | grep deleted`）
6. `TIME_WAIT` 过多是什么原因？
7. 用户态和内核态是什么？一次 `recv()` 系统调用发生了什么？
8. 什么是 load average？
9. 开机流程：BIOS/UEFI → GRUB → 内核 → systemd → 服务
10. 什么是 inode？`df -i` 满了会怎样？
11. 中断和轮询的区别？（低延迟必问）
12. 什么是上下文切换，为什么它会增加延迟？

---

## 建议的练习方式

- 在 AWS 实验机上（`flle-ex1` / `flle-tr2`）实际敲一遍，比背更有效
- 每天用 `man 命令` 或 `命令 --help` 查一个没用过的参数
- 遇到问题先按第 9 节的排障顺序走一遍，养成习惯
