# 第零部分：CPU、缓存与操作系统基础——低延迟之前的热路径

## 为什么同一段程序会忽快忽慢

一条行情到达网卡后，程序还要读取、解析和处理它。**本章看四个等待点：取数据、准备内存、等 CPU（处理器）执行、收包交给程序。**

**把服务器想成一间厨房。** 食材送到了，还要存放、取用和处理；主厨可能在找食材，也可能正在忙别的任务。程序中频繁执行的一串处理步骤，叫“热路径”，像厨房里做菜时反复走过的路线。我们先看厨房内部怎样工作，再回到收货口看通知怎样传进来。

**学完本章：** 能借这间厨房解释四个等待点，并通过一个小实验，看内存何时真正准备好。具体耗时留到第四部分测量。

本章依据 Linux 内核文档、Intel 优化手册与 AMD Onload 文档，来源见文末“延伸阅读”。

## 本章路线

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">本章导航</span> <span style="font-weight:700;color:#581c87;">沿厨房里的问题走完七步；各节导航卡标出当前步骤。</span></div>

| 学习步骤 | 所属部分 | 厨房里的问题 |
| --- | --- | --- |
| 1. 内核边界 | 谁管资源、数据在哪 | 谁分配厨房里的空间和工具？ |
| 2. 缓存与局部性 | 谁管资源、数据在哪 | 食材在手边，还是要去仓库取？ |
| 3. 内存地址 | 编号怎样对应位置 | 库存编号怎样对应到货架？ |
| 运行 ①：第一次往每页写数据，看见缺页 | 编号怎样对应位置 | 领到编号时，空位就准备好了吗？ |
| 4. 调度 | 谁通知、何时处理 | 食材备齐，何时轮到主厨处理？ |
| 5. 通知与收包 | 谁通知、何时处理 | 食材送到后，经过谁的处理？ |
| 6. 一页总结 | 总结 | 食材送到后，哪些地方还会等？ |

## 1. 内核边界：应用通过系统调用使用硬件

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 谁管资源、数据在哪</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：原理讲解　这一步回答：谁分配厨房里的空间和工具？　进度：全章第 1 / 7 项 · 这一部分第 1 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">1. 内核边界</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">2. 缓存与局部性</span></div>

这间厨房有一个总控台，负责分配存放食材的空间和可用工具。服务器里的内核承担类似职责：程序需要内存和网卡等资源时，通过操作系统提供的入口申请。

| 厨房里的角色 | 计算机里的名称 | 做什么 |
| --- | --- | --- |
| 总控台 | **内核（Kernel）** | 管理 CPU、内存和设备资源 |
| 申请窗口 | **系统调用（System Call）** | 接收程序提出的资源或收发请求 |
| 照说明书操作设备的人 | **驱动（Driver）** | 由 CPU 执行的软件，把操作落实到设备 |

图中的 **NIC** 是网卡，**PCIe** 是网卡等设备与主机连接的通道。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">内核边界 · 请求向下，结果向上</div>
<img src="images/course-visuals/00-diagrams/00-01-kernel-boundary.png" alt="应用通过read、write、send、recv系统调用提出请求，CPU执行Linux内核代码来管理处理器、内存和网卡等资源的分层图" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">沿图从上往下看：应用提出请求，内核安排资源，驱动操作设备；绿色箭头表示结果返回。read/write 是读写，send/recv 是发送和接收。</div>
</div>

**用户态**像在自己的工位上干活；**内核态**像到总控台办事。它们是 CPU 执行代码时不同的权限范围。程序通过系统调用提出请求，由操作系统的内核负责处理。

| 层级 | 本课程中的例子 | 能做什么 |
| --- | --- | --- |
| 用户态 | 行情解析、交易逻辑 | 处理自己的数据，需要系统资源时发起申请 |
| 内核态 | 分配 CPU、管理内存、处理网络协议 | 内核运行时可以管理系统资源 |
| 驱动 | Solarflare X2522 网卡的 `sfc` 驱动、Broadcom 网卡的 `bnxt_en` 驱动 | 本课网卡由这些驱动控制 |

空间申请好后，主厨可以在自己的工位上取用食材；程序也能在分到的范围内读写内存，不必每次访问都重新申请。所以下一节看：取数据这件事本身要等多久？

## 2. 缓存与局部性：数据在手边，还是要去远处取

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 谁管资源、数据在哪</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：原理讲解　这一步回答：食材在手边，还是要去仓库取？　进度：全章第 2 / 7 项 · 这一部分第 2 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">1. 内核边界</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">2. 缓存与局部性</span></div>

总控台分好了空间，接着看食材放哪里。主厨手边有，就能直接拿；手边没有，就要去更远的地方取。CPU 读取数据也有类似差别。

一个 CPU 内有执行指令的**核心（Core）**，相当于实际动手的主厨。**缓存（Cache）** 是核心附近的小容量存储，像手边备料区；**主内存（RAM）** 像后厨仓库。

缓存通常分成 L1、L2、L3 几级，数字越小，通常越靠近核心、容量越小。先看图，再理解为什么位置会影响等待。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">存储层级 · 主厨手边的缓存与后厨主内存</div>
<img src="images/course-visuals/00-diagrams/00-memory-workbench.svg" alt="CPU从缓存或主内存取得计算所需数据；用厨师、抽屉和储物区解释等待的来源" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">先看数据离核心有多近。数据在哪层找到，就从哪层拿；箭头表示位置关系，不是每次必须依次走完的步骤。磁盘只作距离对比，正常报文处理使用缓存和主内存。</div>
</div>

> “The latency of an Instruction with memory operand can vary greatly due to a number of factors, including data locality in the memory/cache hierarchy.”
>
> —— [Intel® 64 and IA-32 Architectures Optimization Reference Manual](https://www.intel.com/content/dam/doc/manual/64-ia-32-architectures-optimization-manual.pdf)

**原文翻译：** 带有内存操作数的指令，其延迟可能因多种因素而有很大差异，其中包括所需数据在内存和各级缓存中的位置。

**通俗解释：** “操作数”指一条指令要处理的对象。一条指令好比一道工序，操作数就是这道工序要处理的原料；通过内存地址找到这份原料，就称为内存操作数。例如“把某个地址里的值加 1”，这个地址里的值就是内存操作数。指令得先把它拿到手才能加，而它此刻是在主厨手边的缓存里，还是要去后厨仓库（主内存）取，会影响这条指令要等多久。

| 存放位置 | 可以怎样理解 | 需要记住什么 |
| --- | --- | --- |
| **寄存器（Register）** | 主厨手中正拿着的东西 | 核心执行指令时直接使用的小容量存储 |
| **L1 / L2 缓存** | 核心手边的台面与抽屉 | L1 更靠近核心；L2 通常更大 |
| **L3 缓存** | 多位主厨共用的备料区 | 常由多个核心共享 |
| **主内存** | 后厨仓库 | 容量较大，从这里取数据通常等待更久 |

在某一级缓存找到数据，叫**命中（Hit）**；没有找到，叫**未命中（Miss）**，还要到其他缓存或主内存中找。

缓存搬数据时，通常一次搬一整块连续的数据，这一块称为**缓存行（Cache Line）**。本课机器一行是 **64 字节（64 B）**，可以想成一次拿一小托盘。

本课机器的实测规格见[教师说明](assets/00-basics/TEACHER-NOTES.md#机器规格与历史记录)。这里先记住 64 B 这个搬运单位。

### 局部性：反复读取同一处，接着读取相邻位置

“局部性”用来描述程序访问数据的集中程度。可以先记住两种情况：

| 厨房里的动作 | 程序里的访问方式 | 技术名称 |
| --- | --- | --- |
| 刚用过盐，过一会儿又拿同一个盐罐 | 刚访问过的数据，很快再次访问 | 时间局部性 |
| 拿过盐罐，接着拿旁边的胡椒罐 | 访问某个地址后，又访问它附近的数据 | 空间局部性 |

例如，处理一条行情时，程序先读价格，再读数量。如果这两个字段在内存中的位置相邻，并且落在同一条缓存行里，取回这一条缓存行就能得到两个字段。

下图再加上序号和标记：`price` 是价格、`qty` 是数量、`seq` 是序号、`flags` 是标记。比较这四个字段放在同一条缓存行，还是分散在四条缓存行。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">局部性对照 · 相同字段，不同摆放</div>
<img src="images/course-visuals/00-diagrams/00-08-locality-patterns.png" alt="price、qty、seq和flags在一条64字节Cache Line中紧凑顺序摆放，与分散到四条Cache Line的对照图" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">左侧四个字段共用一条 64 B 缓存行；右侧分散到四条缓存行。图说明的是搬运范围：字段宽度为示意画法，实际收益取决于真实布局与访问模式。</div>
</div>

- **先后要读取的字段，放在相邻的内存位置：** 可能用较少缓存行取齐所需数据。
- **缓存的空间有限：** 程序读取许多其他数据时，缓存需要存放这些新数据，原来常读的数据副本就可能被替换。下次再读原来的数据，就得从其他缓存或主内存重新取得。

这张图展示四个字段分布在几条缓存行上。程序的实际耗时需要运行测量，第五部分会用相同任务比较不同写法。

## 3. 内存地址：程序里的地址怎样对应实际内存

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 编号怎样对应位置</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：原理讲解　这一步回答：库存编号怎样对应到货架？　进度：全章第 3 / 7 项 · 这一部分第 1 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">3. 内存地址</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ①：第一次往每页写数据，看见缺页</span></div>

食材已经有了存放位置，但任务单上记的可能只是库存编号。主厨要取到食材，还得知道“这个编号对应哪个货架”。

一个正在运行的程序叫**进程**。通常，每个进程都有自己的一套内存地址编号，称为**虚拟地址空间**；程序使用其中的**虚拟地址**来读取或写入数据。

这就像不同厨房各有一本库存账本：两本账本里都可以有“第 10 号”，但对应的货架位置可能不同。同样，两个进程使用相同的虚拟地址，也可能对应不同的实际内存位置。

实际内存位置用**物理地址**表示。程序访问数据时，系统和硬件负责把虚拟地址对应到物理地址，这个过程叫**地址翻译**。

对应关系按固定大小的块来记录，每块叫一**页**。本课机器的普通页是 **4 KiB（4096 字节）**，其中 1 KiB = 1024 字节。[Linux 页表文档](https://docs.kernel.org/mm/page_tables.html)说明了下面两个对象的分工：

| 对象 | 厨房比喻 | 保存什么 |
| --- | --- | --- |
| **页表（Page Table）** | 编号与货架位置的账本 | 虚拟页到物理页的映射，以及访问权限 |
| **地址翻译缓存（TLB）** | 手边记着常用对应关系的小纸条 | 近期用过的地址翻译结果，省去反复查账本 |

从图中的 **①** 开始，先查手边的小纸条，再按查找结果选择分支。图左侧列出常见路线；下面的表逐条解释每根编号箭头。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">地址翻译 · 从①出发，沿条件找到下一步</div>
<img src="images/course-visuals/00-diagrams/00-address-translation-numbered.svg" alt="七条编号箭头的地址翻译图：1查询TLB，2按翻译结果读写内存，3未命中时查页表，4查到记录后保存结果，5交给内核处理缺页，6修复后重试，7无法恢复则报告访问错误" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">紫色是查找，绿色是使用或保存可用记录，橙色是内核处理与重试，红色是访问无法继续。页表本身也保存在主内存中，这里单独画出它的查找职责。</div>
</div>

| <span style="white-space:nowrap;">编号</span> | 从哪里到哪里 | 什么时候走、具体做什么 |
| --- | --- | --- |
| **①** | 程序使用的虚拟地址 → TLB | 程序要读写一个地址时，硬件先查 TLB，看看是否已有可用的地址对应记录。 |
| **②** | 可用的翻译结果 → 主内存中的目标位置 | TLB 中已有可用记录，称为**命中（Hit）**。硬件据此找到物理地址，继续读写目标数据；实际取数据时可以利用上一节介绍的缓存。 |
| **③** | TLB → 页表 | TLB 中没有需要的记录，称为**未命中（Miss）**。硬件接着查页表；只要页表里的记录可用，就能取得翻译结果。 |
| **④** | 页表 → TLB | 查到可用记录后，硬件取得翻译结果，并通常把它保留在 TLB 中，方便后续复用。本次访问根据取得的结果继续到②。 |
| **⑤** | 页表 → 内核 | 映射尚未准备好，或访问权限需要处理时，硬件触发**缺页异常（Page Fault）**，由内核检查并处理。 |
| **⑥** | 内核 → 重新发起本次访问 | 内核成功准备页面、补好映射后，重试刚才的访问；从①再走一次，这次可以继续找到数据。 |
| **⑦** | 内核 → 访问无法继续 | 例如程序访问了无权使用的地址，内核无法为这次访问提供合法映射，就向程序报告访问错误。 |

图中⑤若能在内存中解决，称为次缺页（Minor Fault），例如首次写入时分配物理页；需要从存储设备读入数据，则称为主缺页（Major Fault）。

这里看的是**页**：每条地址对应记录管理一块内存，本课普通页为 **4 KiB**。上一节的**缓存行**是取数据时的搬运单位，本课为 **64 B**。一个管地址对应，一个管数据搬运。

使用**大页（HugePage）**，就像把账本改成按整排货架登记：同样多的内存可以用更少的记录来对应，TLB 也能用有限的记录覆盖更多内存。第六部分会配置大页。[Linux 大页文档](https://docs.kernel.org/admin-guide/mm/hugetlbpage.html)

下面用一个小实验观察图中的⑤：先申请一段内存，再往每一页写一次数据。我们对比写入前后的次缺页计数，看看增加了多少。

## 运行 ①：第一次往每页写数据，看见缺页

前三节都是理论。这一步用全章唯一的实验，把“**页面尚未准备好**”变成一个能在自己终端看到的数字。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 编号怎样对应位置</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：动手实验　这一步回答：领到编号时，空位就准备好了吗？　进度：全章第 4 / 7 项 · 这一部分第 2 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">3. 内存地址</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">运行 ①：第一次往每页写数据，看见缺页</span></div>

程序用 `mmap` 向内核申请内存，这是第 1 节“申请窗口”的一次使用。这里申请的内存不关联文件，称为**匿名内存**。先看图：按 A～E 从上往下读，左边是代码动作，右边是内存和计数的变化。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">首次写入 · 从申请地址到比较缺页计数</div>
<img src="images/course-visuals/00-diagrams/00-page-write-code-walkthrough.svg" alt="按A到E逐步解释Python首次写入实验：A申请128页匿名内存地址范围，B读取before，C每页首字节写1并对应前图5处理缺页和6重试，D读取after，E输出三项结果并关闭映射" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">本图 A～E 对应下面的代码注释；C 步中的⑤、⑥引用上一张地址翻译图。图中摘录关键代码，完整参数与表达式见下方脚本。</div>
</div>

图里的 `ru_minflt` 是操作系统为本进程记录的累计次缺页次数。B 保存写入前的 `before`，D 保存写入后的 `after`，两者相减就是这段时间的增长量。[计数器说明](https://man7.org/linux/man-pages/man2/getrusage.2.html)

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 运行 ①</span> <span style="font-weight:700;color:#14532d;">在【课程 Linux 终端】运行；只需 <code>python3</code>；影响范围仅限当前进程申请的这段内存，进程退出即释放；预计数秒。</span></div>

```bash
python3 - <<'PY'
import mmap
import os
import resource

# A. 读取系统页大小，并申请 128 页可读写的匿名内存。
page = os.sysconf("SC_PAGE_SIZE")
size = page * 128
# -1 与 MAP_ANONYMOUS：申请不关联文件的内存。
# MAP_PRIVATE 使用私有映射；PROT_READ/PROT_WRITE 允许程序读写。
buf = mmap.mmap(-1, size,
                flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE)
# B. 记下本进程累计的次缺页次数，作为比较起点。
# 计数覆盖整个进程，也包含 Python 自身发生的次缺页。
before = resource.getrusage(resource.RUSAGE_SELF).ru_minflt

# C. 从第 1 页开始，每次跨过一页，共访问 128 页。
for offset in range(0, size, page):
    # 每页的第一个字节写入数值 1；首次写入会让内核准备这一页。
    buf[offset] = 1

# D. 逐页写完后，再读取一次累计次数。
after = resource.getrusage(resource.RUSAGE_SELF).ru_minflt
# E. 输出页大小、写过的页数和计数增量，随后释放内存映射。
print("page_size=%d" % page)
print("touched_pages=%d" % (size // page))
print("minor_fault_delta=%d" % (after - before))
buf.close()
PY
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">实测样例 · 输出解读</span> <span style="font-weight:700;color:#581c87;">2026-08-25 在 <code>.101</code> 实测，RUN <code>20260825T045052Z-00-page-fault-shape</code>。三行输出依次是页大小、写过的页数和本进程次缺页增量。</span></div>

```text
page_size=4096
touched_pages=128
minor_fault_delta=128
```

| 字段 | 读法 |
| --- | --- |
| `page_size=4096` | 当前进程看到的页大小为 **4 KiB** |
| `touched_pages=128` | 每页写一次，共写过 128 页 |
| `minor_fault_delta=128` | 这次记录中，进程的次缺页次数增加了 128 |

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;">
<span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">关键现象</span>
<div style="font-weight:700;color:#164e63;margin-top:8px;"><strong>对照输出：</strong>看 <code>touched_pages</code> 和 <code>minor_fault_delta</code>：写过 128 页，次缺页增量应接近 128；样例中两项都是 128。</div>
<div style="font-weight:700;color:#164e63;margin-top:6px;"><strong>理解现象：</strong>程序先拿到一段可用地址，第一次往每页写数据时，内核才为这一页准备实际内存，并补上地址对应记录。这正是图中 C 步要观察的过程。</div>
<div style="font-weight:700;color:#164e63;margin-top:6px;"><strong>计数范围：</strong>这里统计的是整个进程，Python 自身的活动也可能让计数多几次，所以结果接近写过的页数即可。</div>
</div>

**下一线索：** 页面准备好，只代表数据可以被访问；处理行情的任务还要等 CPU 来执行。

## 4. 调度：准备好了，为什么还要等 CPU

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 谁通知、何时处理</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：原理讲解　这一步回答：食材备齐，何时轮到主厨处理？　进度：全章第 5 / 7 项 · 这一部分第 1 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">4. 调度</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">5. 通知与收包</span></div>

编号查清、食材备齐，任务单已经可以交给主厨；可主厨此刻可能正在处理另一道菜。程序同样可能已经准备好，却在等待 CPU。

**线程（Thread）** 是程序中可以被操作系统单独安排执行的任务，例如专门负责接收行情的任务。可以把线程想成一张任务单，CPU 核心是执行它的主厨。

内核中的**调度器（Scheduler）** 负责选择接下来运行的线程，相当于总控台的排班功能：决定主厨先接哪张已准备好的任务单。[Linux 调度器文档](https://docs.kernel.org/5.15/scheduler/sched-design-CFS.html)

线程已有工作、运行所需的条件也已满足，此时仍可能要等 CPU 的执行机会。**从准备好到真正开始执行之间的这段时间，就是这里要关注的调度等待。**

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">从候选线程到处理器 · 先看①～③</div>
<img src="images/course-visuals/00-diagrams/00-scheduler-thread-states.svg" alt="统一平面构图：左侧彩色标牌代表已准备好的候选线程，中间选择面板表示内核调度功能，右侧两个逻辑处理器执行线程。①等待并被选择，②③安排执行；下方较小区域表示④执行中等数据而暂停，⑤条件满足后回到候选线程等待再次安排。" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">①～③看开始前的等待，④⑤看执行中的暂停与恢复。</div>
</div>

| 箭头 | 读图 |
| --- | --- |
| **① 等待与选择** | 线程已准备好（可运行）；处理器可能正忙，仍需等待安排 |
| **②③ 开始执行** | 被选中的线程分别在逻辑处理器 0、1 上执行 |
| **④ 等待数据** | 执行中暂停等待（阻塞），保留执行状态 |
| **⑤ 条件满足** | 重新变为可运行，等待再次安排；之后从原处继续 |

切换线程时，系统保存当前线程的执行状态，再恢复另一个线程的状态，这叫**上下文切换（Context Switch）**；仍可运行的线程也可能被暂时切换下来。等调度、等数据都会影响任务耗时，后续实验再观察和比较这些延迟。

操作系统会给它看到的**逻辑 CPU**编号，例如 CPU0、CPU1。一个物理核心可能向系统呈现为两个逻辑 CPU，所以两个编号不一定代表两个独立核心。[Linux CPU 拓扑说明](https://docs.kernel.org/admin-guide/cputopology.html)

**CPU 亲和性（CPU affinity）** 规定线程允许在哪些逻辑 CPU 上运行。例如 `0-3` 表示允许使用编号 0 到 3 的逻辑 CPU，并不意味着独占它们。第五部分再比较把线程固定在哪些 CPU 上会有什么影响。

厨房内部的存放、查找和排班已经分清。现在回到收货口：新食材送到以后，要经过谁的处理，才能交到主厨手里？

## 5. 通知与收包：报文怎样交到程序手里

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 谁通知、何时处理</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：原理讲解　这一步回答：食材送到后，经过谁的处理？　进度：全章第 6 / 7 项 · 这一部分第 2 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">4. 调度</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">5. 通知与收包</span></div>

食材送到了，要先放好，再通知验收，最后摆到备菜台，主厨才能取用。普通收包也有这条交接链：报文放进内存，内核处理后，应用线程再读取。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">普通收包 · 从收货口到主厨</div>
<img src="images/course-visuals/00-diagrams/00-receive-kitchen-flow.svg" alt="普通收包厨房图：①网卡把报文放入主内存缓冲区；②中断像铃声，安排收包；③驱动按NAPI机制调用poll，一批一批处理已到内存的报文，再由网络栈处理协议；④套接字（Socket）的接收队列像备菜台；⑤应用线程像主厨，从中读取。" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">①先放好报文，再沿②③④⑤看交接。网卡收到、CPU开始处理、应用读到，是三个不同的时刻。</div>
</div>

| 图中编号与角色 | 在服务器里做什么 |
| --- | --- |
| **① 存货区** | 接收缓冲区是主内存中暂存报文的位置，网卡先把报文写进去 |
| **② 铃声：中断（IRQ）** | 通知有报文待处理；响应通知时先安排收包工作 |
| **③ 验收员：NAPI 批量收包** | NAPI 是内核安排网络事件处理的机制；驱动的 `poll` 查看已到内存的报文，一次可以处理多个。网络栈接着处理 TCP、UDP 等协议 |
| **④ 备菜台：套接字接收队列** | 存放待应用读取的接收数据；套接字（Socket）是程序收发数据的接口 |
| **⑤ 主厨：应用线程** | 获得执行机会后，读取数据，继续处理业务 |

**铃响只说明有货要收。** 批量验收、协议处理和应用读取都需要时间；一次通知可以对应一批报文，中断数与报文数没有固定比例。这些软件工作都由 CPU 执行。[Linux NAPI 文档](https://docs.kernel.org/networking/napi.html)

内核旁路（Kernel Bypass）可以让报文收发绕过内核网络栈的部分常规处理。OpenOnload 是用户态网络库，本课第六部分会配合 X2522 网卡使用它。下图区分网卡与软件的分工。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">内核旁路 · 网卡与软件的分工</div>
<img src="images/course-visuals/00-diagrams/00-onload-hardware-software.svg" alt="独立的OpenOnload分工图。左侧网卡硬件收发报文、分发队列，并用DMA写主机内存。右侧CPU执行软件：普通路径内核网络栈标有套接字（Socket）接口实现；Onload路径在应用进程内的库中也标有套接字（Socket）接口实现，业务代码标为套接字调用；库处理协议，①访问分配给它的网卡收发资源，②通过Socket接口交给同一进程内的业务代码。操作系统及驱动仍管理资源并处理未加速的收发。" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">程序调用同一个套接字接口，背后的收发处理一边在内核，一边在应用进程内的库。</div>
</div>

| 本图编号 | 分工 |
| --- | --- |
| ① 网卡与库配合 | 网卡把报文写入内存，库直接访问分给它的收发资源 |
| ② 库与业务代码配合 | 库处理协议，通过套接字接口交给业务代码 |

使用 Onload 时，程序仍调用原来的套接字接口。普通路径由内核网络栈处理 TCP/UDP；Onload 由应用进程内的库接手受支持的收发。两边的代码都由 CPU 执行。[AMD Onload 说明](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency)

网卡在硬件中分流、搬运报文；Onload 直接使用分给它的收发队列，资源由内核与驱动管理。[AMD 网卡资源说明](https://docs.amd.com/r/en-US/ug1586-onload-user/Virtual-Network-Interface-VNIC)

第六部分再用同一程序，对照普通路径与旁路路径的实际表现。

### 高级延伸：多队收货怎样分工

收货区有多队时，需要分别安排“分到哪队”和“由谁听铃”。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">高级延伸 · 接收队列与通知分工</div>
<img src="images/course-visuals/00-diagrams/00-rss-irq-extension.svg" alt="高级延伸独立图：①RSS按地址端口等字段的散列值把报文分到不同接收队列；②中断亲和性限定哪些CPU可以响应通知。队列与铃声的具体对应由设备和配置决定。" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">本图①看分队，②看听铃分工；后续网卡实验会分别观察它们。</div>
</div>

| 本图编号 | 分工与厨房比喻 |
| --- | --- |
| **① 接收队列（RX Queue）与 RSS** | 网卡通常按源／目的地址、端口等字段的散列值，把报文分到不同队列，像按编号分到不同收货队；思路类似交换机按流分担流量 |
| **② 多个通知入口与中断亲和性** | 不同铃声便于区分收包工作；中断亲和性限定哪些 CPU 可以响应某个通知，像指定谁负责听铃。队列、铃与 CPU 的对应关系由设备和配置决定 |

这些分工会在后续网卡实验中再次出现。[Linux RSS 与中断分工](https://docs.kernel.org/networking/scaling.html)

## 6. 一页总结：把四个等待点放回行情处理路径

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 总结</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">类型：回顾整理　这一步回答：食材送到后，哪些地方还会等？　进度：全章第 7 / 7 项 · 这一部分第 1 / 1 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">6. 一页总结</span></div>

回到开头那箱新食材：驱动先备好存放位置，并把位置写进清单；网卡照单把报文放进去。下面把这条收包路径与前面讲过的四个等待点放在一起。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<div style="font-weight:900;color:#0f172a;margin-bottom:8px;">行情处理路径 · 四个等待点各在哪里</div>
<img src="images/course-visuals/00-diagrams/00-packet-memory-notification.svg" alt="行情路径与四个等待点：常见中断驱动路径：①网卡按清单用DMA写入已准备好的主内存接收缓冲区；②中断通知CPU；③④CPU经缓存读取并处理数据；⑤应用线程读取并解析行情。通知与数据线分开。A取数据标在缓存与主内存之间；B准备内存标在申请和首次访问阶段，收包缓冲区提前备好；C等CPU执行标在处理器入口；D收包交给程序覆盖从通知到应用读取的整段。清单、存货区、手边台面、验收员和主厨对应前面的厨房角色。" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#475569;font-size:13px;margin-top:8px;">常见中断驱动路径：①写入内存 → ②中断通知 → ③④取数并处理 → ⑤应用读取。网卡收到、CPU开始处理、应用读到，是三个不同的时刻；A～D标出可能的等待。</div>
</div>

存货区、清单和照单放货分别对应以下三个术语，第一部分会继续使用它们：

| 图中角色 | 名字与职责 |
| --- | --- |
| **存货区** | **接收缓冲区（RX Buffer）**：主机内存中预先准备的空间，用来存放报文 |
| **位置清单** | **接收描述符（RX Descriptor）**：由驱动准备的记录，告诉网卡可把报文写到哪里 |
| **① 照单放货** | **直接内存访问（DMA）**：网卡直接把报文字节写入主机内存，这段搬运无需 CPU 逐字节复制 |

驱动先把缓冲区及相关记录准备好，再交给网卡使用；后续验收与业务处理仍要由 CPU 执行。[Linux DMA 指南](https://docs.kernel.org/core-api/dma-api-howto.html)

| 图中等待点 | 发生了什么 | 后续在哪里继续 |
| --- | --- | --- |
| **A · 取数据** | 当前缓存没有，还要去其他缓存或主内存找 | 第五部分运行②：比较“空间不够时再申请”和“事先备好反复用” |
| **B · 准备内存** | 程序申请或首次访问内存时，可能需要内核准备物理页与地址映射；收包缓冲区要提前备好 | 第六部分：用大页给用户态收发准备内存；地址查找见本章第 3 节 |
| **C · 等 CPU 执行** | 线程等执行机会，或执行中被换下 | 第五部分运行③④：比较等通知、主动查看任务和共用 CPU 的影响 |
| **D · 收包交给程序** | 从中断通知到应用读到报文，中间的处理与等待都需要时间 | 第六部分：比较经过内核与绕过部分内核处理的收发路线 |

**交给第一部分的问题：** 接下来去真实机器上认网卡、驱动和接线，再用抓包确认报文到了哪里。这样就能把本章的处理路线对应到具体设备。

## 理解检查

1. **页**和**缓存行**各自负责什么，本课机器的大小分别是多少？
2. 在普通收包路径中，网卡发出中断通知时，能否说应用已经处理完报文？后面还有哪些工作？
3. 使用内核旁路后，谁执行代码，谁管理内存和设备资源？

**参考要点：**

1. 页用于地址映射，本课普通页为 4 KiB；缓存行是缓存搬运连续数据的单位，本课为 64 B。
2. 不能。通知之后，内核还要处理收到的报文，通过套接字交给程序，应用线程再读取和处理；这些工作的时间需要分别看待。
3. 代码由 CPU 执行，操作系统仍管理资源；内核旁路减少的是报文收发经过的部分常规软件步骤。

## 清理与下一步

实验进程退出后，申请的内存自动释放。接着进入[第一部分：设备与接线](01-financial-low-latency-architecture.md)。

配套脚本与历史机器规格放在[教师说明](assets/00-basics/TEACHER-NOTES.md)。

## 延伸阅读

| 资料 | 继续查什么 |
| --- | --- |
| [Intel 优化手册](https://www.intel.com/content/dam/doc/manual/64-ia-32-architectures-optimization-manual.pdf) | 缓存、主内存与指令等待 |
| [Linux 内存管理](https://docs.kernel.org/admin-guide/mm/index.html) | 内存分配与映射 |
| [Linux 进程资源计数](https://man7.org/linux/man-pages/man2/getrusage.2.html) | 次缺页计数属于整个进程 |
| [Linux CPU 拓扑](https://docs.kernel.org/admin-guide/cputopology.html) | 逻辑 CPU 与物理核心的关系 |
| [Intel 64 and IA-32 Architectures Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) | CPU 架构、内存管理与中断 |
| [Linux 5.15 CFS Scheduler](https://docs.kernel.org/5.15/scheduler/sched-design-CFS.html) | 本课机器内核版本（5.15）对应的调度设计入口 |
| [Linux 页表](https://docs.kernel.org/mm/page_tables.html) | 虚拟地址、物理地址与映射 |
| [Linux 大页](https://docs.kernel.org/admin-guide/mm/hugetlbpage.html) | 大页的用途与配置边界 |
| [Linux NAPI](https://docs.kernel.org/networking/napi.html) | 通知之后怎样批量处理已到报文 |
| [Linux 网络扩展](https://docs.kernel.org/networking/scaling.html) | 接收队列、RSS与中断分工 |
| [Linux 中断](https://docs.kernel.org/core-api/irq/concepts.html) | 设备发出的中断请求 |
| [Linux DMA 指南](https://docs.kernel.org/core-api/dma-api-howto.html) | 驱动准备与设备直接读写内存 |
| [AMD Onload 路径对照](https://docs.amd.com/r/en-US/ug1586-onload-user/Contrasting-with-Conventional-Networking) | 普通收发与用户态收发的区别 |
| [AMD Onload 透明接入](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency) | 原程序的套接字调用如何由 Onload 库接手 |
