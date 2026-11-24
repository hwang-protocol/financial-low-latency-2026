# AWS 实验环境：从零搭建两台机器（2026-11-15）

这一篇记录实验用的两台 EC2 是**怎么建出来的**，每条命令都是当时实际执行过的。各章的实验命令写在对应章节的文件里。

- 地区：东京 `ap-northeast-1`，可用区 `ap-northeast-1c`
- 所有命令都在 **Windows 的 Git Bash** 里执行（本机已经装好 AWS CLI v2，并配置好凭证）

> **Git Bash 的坑：** Git Bash 会把以 `/` 开头的参数当成 Windows 路径改写，比如把 `/aws/service/...` 改成 `C:/Program Files/Git/aws/service/...`。所以下面每段开头都有 `export MSYS_NO_PATHCONV=1`，关掉这个改写。`AWS_PAGER=""` 让 aws 命令直接输出结果，不进入翻页器。

---

## 第 1 步：确认账号和现有资源

```bash
export AWS_PAGER="" MSYS_NO_PATHCONV=1; R=ap-northeast-1

# 现在用的是哪个 IAM 身份
aws sts get-caller-identity --query '{Arn:Arn}' --output text

# 这个地区已经有哪些机器（确认不会误动 vpn-tokyo）
aws ec2 describe-instances --region $R \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`]|[0].Value]' \
  --output text

# c7i.large 在哪些可用区有货
aws ec2 describe-instance-type-offerings --region $R --location-type availability-zone \
  --filters Name=instance-type,Values=c7i.large --query 'InstanceTypeOfferings[].Location' --output text
```

**这一步在干嘛：** 动手前先看清楚账号里有什么。`--query` 用的是 JMESPath 语法，只挑出关心的字段，否则输出是一大坨 JSON。

## 第 2 步：找 Ubuntu 22.04 的系统镜像（AMI）

```bash
# Canonical 官方账号 099720109477 发布的最新 Ubuntu 22.04 镜像
aws ec2 describe-images --region $R --owners 099720109477 \
  --filters 'Name=name,Values=ubuntu/images/hvm-ssd*/ubuntu-jammy-22.04-amd64-server-*' \
  --query 'sort_by(Images,&CreationDate)[-1].[ImageId,Name]' --output text
# → ami-0eb22196b50d52cfd  ubuntu/images/hvm-ssd-gp3/ubuntu-jammy-22.04-amd64-server-...

# 默认 VPC 里有哪些子网
aws ec2 describe-subnets --region $R --filters Name=vpc-id,Values=vpc-0af0d7d10bc5485e1 \
  --query 'Subnets[].[SubnetId,AvailabilityZone,DefaultForAz]' --output text
# → 选了 1c 的 subnet-058f2e15c807d7996
```

**为什么指定 owner：** 镜像市场里有很多人上传的“Ubuntu”，只认 Canonical 官方的账号 ID 才安全。

## 第 3 步：密钥、安全组、置放群组

```bash
export AWS_PAGER="" MSYS_NO_PATHCONV=1; R=ap-northeast-1; VPC=vpc-0af0d7d10bc5485e1

# 1) 把本机已有的公钥导入成 AWS 密钥对（私钥不出本机）
aws ec2 import-key-pair --region $R --key-name flle-lab-key \
  --public-key-material "fileb://C:/Users/<你>/.ssh/ec2_vpn_key.pub"

# 2) 建安全组（相当于防火墙）
SG=$(aws ec2 create-security-group --region $R --vpc-id $VPC --group-name flle-lab-sg \
      --description "FLLE trading lab" --query GroupId --output text)
# → sg-0f4ccad66b2e195d0

# 放行：我的 IP 能 SSH(22) 和看网页(8088)；组内两台机器之间所有流量都放行
aws ec2 authorize-security-group-ingress --region $R --group-id $SG --ip-permissions \
  "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=<你的公网IP>/32}]" \
  "IpProtocol=tcp,FromPort=8088,ToPort=8088,IpRanges=[{CidrIp=<你的公网IP>/32}]" \
  "IpProtocol=-1,UserIdGroupPairs=[{GroupId=$SG,Description=lab-internal}]"

# 后来补的：允许从跳板机 ec2-tokyo 所在的安全组 SSH 进来
aws ec2 authorize-security-group-ingress --region $R --group-id $SG --ip-permissions \
  "IpProtocol=tcp,FromPort=22,ToPort=22,UserIdGroupPairs=[{GroupId=sg-0a5611cce9f200c88,Description=ssh-via-vpn-tokyo}]"

# 3) 置放群组：cluster 策略让两台机器尽量放在同一机架附近，网络延迟最低
aws ec2 create-placement-group --region $R --group-name flle-lab-pg --strategy cluster
```

**知识点：**
- `IpProtocol=-1` 表示所有协议。`UserIdGroupPairs` 指“来自某个安全组的机器”，比写死 IP 更好，IP 变了也不用改
- **置放群组（placement group）** 是 AWS 里最接近“两台机器插在同一台交换机上”的东西。课程里 `.1` 和 `.2` 直连 Arista 交换机，这里用 cluster 置放群组模拟

## 第 4 步：开两台 c7i.large

```bash
export AWS_PAGER="" MSYS_NO_PATHCONV=1; R=ap-northeast-1
aws ec2 run-instances --region $R --image-id ami-0eb22196b50d52cfd --instance-type c7i.large --count 2 \
  --key-name flle-lab-key --security-group-ids sg-0f4ccad66b2e195d0 --subnet-id subnet-058f2e15c807d7996 \
  --placement GroupName=flle-lab-pg \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=40,VolumeType=gp3,DeleteOnTermination=true}' \
  --metadata-options HttpTokens=required \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Project,Value=flle-lab}]' \
  --query 'Instances[].InstanceId' --output text
# → i-0c8565112268f92fb  i-0872ca5de433c6364

# 起名字，方便在控制台认
aws ec2 create-tags --region $R --resources i-0c8565112268f92fb --tags Key=Name,Value=flle-exchange-1 Key=Role,Value=exchange
aws ec2 create-tags --region $R --resources i-0872ca5de433c6364 --tags Key=Name,Value=flle-trader-2  Key=Role,Value=trader

# 等到 running，再看 IP
aws ec2 wait instance-running --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364
aws ec2 describe-instances --region $R --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364 \
  --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value,InstanceId,State.Name,PrivateIpAddress]' --output text
```

| 参数 | 意思 |
|---|---|
| `--count 2` | 一次开两台 |
| `VolumeSize=40,VolumeType=gp3` | 40 GB 硬盘。ITCH 行情文件就有 562 MB，加上编译，默认 8 GB 不够 |
| `HttpTokens=required` | 强制用 IMDSv2 访问元数据，安全最佳实践 |
| `DeleteOnTermination=true` | 删机器时硬盘一起删，不会遗留收费硬盘 |

## 第 5 步：配置 SSH 别名

本机 `~/.ssh/config` 加了三段（IP 用占位符代替）：

```sshconfig
Host ec2-tokyo                 # 跳板机（就是 vpn-tokyo，只借道，不改它）
    HostName <跳板机公网IP>
    User ubuntu
    IdentityFile ~/.ssh/ec2_vpn_key

Host flle-ex1                  # 扮演课程的 .1 交易所
    HostName 172.31.10.43      # 内网 IP，停机再开也不会变
    User ubuntu
    IdentityFile ~/.ssh/ec2_vpn_key
    ProxyJump ec2-tokyo
    StrictHostKeyChecking accept-new

Host flle-tr2                  # 扮演课程的 .2 交易员
    HostName 172.31.12.156
    User ubuntu
    IdentityFile ~/.ssh/ec2_vpn_key
    ProxyJump ec2-tokyo
    StrictHostKeyChecking accept-new
```

**为什么用跳板：** 公网 IP 每次停机再开都会变，内网 IP 不会。经过跳板机用内网 IP 连，`~/.ssh/config` 就不用每次改。之后 `ssh flle-tr2` 就能直接登录。

验证：

```bash
for h in flle-ex1 flle-tr2; do ssh $h 'hostname; lsb_release -ds; nproc; ip -br addr | grep -v ^lo'; done
ssh flle-ex1 'ping -c 20 -i 0.2 -q 172.31.12.156 | tail -2'
```

## 日常：开机、改机型、停机

```bash
export AWS_PAGER="" MSYS_NO_PATHCONV=1; R=ap-northeast-1
EX=i-0c8565112268f92fb; TR=i-0872ca5de433c6364

# 看状态
aws ec2 describe-instances --region $R --instance-ids $EX $TR \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name]' --output text

# 改机型（必须先停机）：第 04 章要 4 个 vCPU
aws ec2 modify-instance-attribute --region $R --instance-id $TR --instance-type '{"Value":"c7i.xlarge"}'

# 开机并等 SSH 可用
aws ec2 start-instances --region $R --instance-ids $EX $TR
aws ec2 wait instance-running --region $R --instance-ids $EX $TR

# 停机（停了只收硬盘费）
aws ec2 stop-instances --region $R --instance-ids $EX $TR
aws ec2 wait instance-stopped --region $R --instance-ids $EX $TR
aws ec2 modify-instance-attribute --region $R --instance-id $TR --instance-type '{"Value":"c7i.large"}'   # 改回
```

> **注意：** 别把 `i-0159ac80a3eef4443`（vpn-tokyo）写进任何开关机命令里。
