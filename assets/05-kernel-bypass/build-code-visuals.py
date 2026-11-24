#!/usr/bin/env python3
"""Rebuild the chapter's editable SVGs and complete, numbered source reader."""
from pathlib import Path
from html import escape as e
import hashlib
import json
import tarfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
IMAGES = ROOT / 'images/course-visuals/05-diagrams'
INK = '#163047'; MUTED = '#52677c'; BLUE = '#1769c2'; TEAL = '#078576'


class Drawing:
    def __init__(self, title, subtitle, color, badge, height=1370):
        self.items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">{e(title)}</title><desc id="desc">{e(subtitle)}。蓝色为发送，绿色为接收；编号对应完整源码阅读页。</desc>',
                      '<defs>']
        for name, fill in [('tx', BLUE), ('rx', TEAL), ('muted', '#8193a6')]:
            self.items.append(f'<marker id="{name}" viewBox="0 0 12 12" markerWidth="12" markerHeight="12" refX="0" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L12 6 L0 12 Z" fill="{fill}"/></marker>')
        self.items += ['</defs>', f'<rect width="1200" height="{height}" rx="22" fill="#f4f7fb"/>', '<g font-family="Noto Sans CJK SC,Microsoft YaHei,sans-serif">']
        self.box(28, 24, 1144, 100, '#ffffff', '#e2e9f0')
        self.icon('chip', 49, 48, color)
        self.text(110, 66, title, 32, INK, 700)
        self.text(110, 101, subtitle, 20, MUTED)
        self.box(995, 43, 153, 45, color, color, 22)
        self.text(1071, 73, badge, 18, '#ffffff', 700, 'middle')

    def text(self, x, y, s, size=22, color=INK, weight=400, anchor='start', mono=False):
        family = ' font-family="DejaVu Sans Mono,monospace"' if mono else ''
        self.items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}"{family}>{e(s)}</text>')

    def box(self, x, y, w, h, fill='#fff', stroke='#dce6ef', radius=16):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    def icon(self, name, x, y, color=BLUE):
        paths = {
            'chip': '<rect x="8" y="8" width="32" height="32" rx="6"/><rect x="17" y="17" width="14" height="14" rx="2"/><path d="M16 0v8m16-8v8M16 40v8m16-8v8M0 16h8m-8 16h8m32-16h8m-8 16h8"/>',
            'plug': '<path d="M16 3v12m16-12v12M10 15h28v7a14 14 0 0 1-28 0zm14 21v10"/>',
            'code': '<rect x="2" y="5" width="44" height="36" rx="6"/><path d="m17 16-7 7 7 7m14-14 7 7-7 7m-9-17-5 21"/>',
            'loop': '<path d="M39 14A18 18 0 0 0 8 15m31-9v10H29M9 34a18 18 0 0 0 31-1M9 42V32h10"/>',
            'stack': '<path d="m24 4 22 11-22 11L2 15zm-22 22 22 11 22-11M2 36l22 11 22-11"/>',
            'nic': '<rect x="2" y="7" width="42" height="30" rx="5"/><rect x="8" y="15" width="15" height="13" rx="2"/><path d="M29 16h9m-9 8h9M9 37v7m7-7v7m7-7v7m7-7v7m7-7v7"/>',
            'server': '<rect x="4" y="4" width="40" height="17" rx="4"/><rect x="4" y="27" width="40" height="17" rx="4"/><path d="M12 12h3m8 0h13M12 35h3m8 0h13"/>',
            'shield': '<path d="m24 2 19 8v13c0 12-11 20-19 23C16 43 5 35 5 23V10zm-9 22 6 6 12-13"/>',
        }
        self.items.append(f'<g class="flat-icon" transform="translate({x} {y})" fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</g>')

    def line(self, x1, y1, x2, y2, kind='tx', dashed=False):
        # Coordinates specify the desired tip, already 14px outside the target.
        import math
        length = math.hypot(x2-x1, y2-y1)
        ex=x2-12*(x2-x1)/length; ey=y2-12*(y2-y1)/length
        color={'tx': BLUE, 'rx': TEAL, 'muted': '#8193a6'}[kind]
        dash=' stroke-dasharray="6 6"' if dashed else ''
        self.items.append(f'<path class="flow" d="M{x1} {y1} L{ex} {ey}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="butt" marker-end="url(#{kind})"{dash}/>')

    def code(self, x, y, w, lines):
        self.box(x, y, w, 24+len(lines)*29, '#132d43', '#132d43', 9)
        for i, s in enumerate(lines): self.text(x+14, y+29+i*29, s, 19, '#e9f4ff', weight=700, mono=True)

    def queue(self, x, y, label, color):
        self.text(x, y, label, 22, color, 700)
        for i in range(5):
            self.box(x+i*36, y+17, 29, 38, '#e3eff9' if color==BLUE else '#dff4ee', color, 4)
        self.text(x, y+86, '描述符指向报文缓冲区', 18, MUTED)

    def save(self, name):
        (IMAGES/name).write_text('\n'.join(self.items+['</g></svg>'])+'\n')


CONFIGS = [
 dict(key='K', file='05-kernel-socket-path.svg', title='Kernel Socket · 代码怎样进入内核', subtitle='对照基线：Socket 进入 Linux 内核；后面三图沿同一位置比较。', color=BLUE, badge='sfc 管理网卡',
      init=[('等待并取出订单', ['order_queue_.front(...)'], '条件变量唤醒订单线程'), ('按需创建连接对象', ['::socket(...)'], '已有连接时复用'), ('建立 TCP 连接', ['::connect(...)'], '只完成 TCP 握手')],
      send=['send_soup(...)','  → send_all(...)','  → ::send(...)'], recv=['recv_soup(...)','  → recv_all(...)','  → ::recv(...)'],
      left='订单线程 · 应用代码', middle='Linux 内核', stack='内核 TCP/IP', tx=['组装 TCP/IP 报文','发送缓冲与重传状态'], rx=['校验、排序、确认','交付 Socket 接收缓冲'], driver='sfc 驱动',
      wait=['K4 · 没有完整回报时怎么办？','阻塞 recv 等待；数据到达后，','内核唤醒线程，继续收满所需字节。'],
      benefit='标准接口、成熟工具；每次收发需要进入内核网络栈。', resource='连接和字节流由 Linux 管理；send 返回表示数据被接受，不表示对端已成交。'),
 dict(key='O', file='05-onload-order-path.svg', title='Onload · 同一份代码，换一个调用落点', subtitle='对照 Kernel：Socket 代码保持，TCP 收发改由进程内的 Onload 库处理。', color=TEAL, badge='sfc 管理网卡',
      init=[('加载用户态库', ['onload --profile=latency'], '用此启动项运行 flle-trader'), ('等待并取出订单', ['order_queue_.front(...)'], '应用订单线程保持原写法'), ('按需创建连接', ['::socket / ::connect'], '已有连接时复用')],
      send=['send_soup(...)','  → send_all(...)','  → ::send(...)'], recv=['recv_soup(...)','  → recv_all(...)','  → ::recv(...)'],
      left='订单线程 · 原 Socket 代码', middle='同一进程 · Onload 库', stack='用户态 TCP/IP', tx=['库接管 send 调用','处理 TCP 状态与报文'], rx=['库处理接收事件','通过 recv 交回字节'], driver='Onload / VI',
      wait=['O4 · 谁推进事件？','Onload 库按配置轮询或等待；','业务代码继续按原接口收发。'],
      benefit='保持原来的 Socket 写法，减少受支持连接逐包经过内核网络栈的处理。', resource='内核模块 / sfc 分配 VI 资源；加速收发使用已分配队列，未加速连接走内核。'),
 dict(key='Z', file='05-tcpdirect-order-path.svg', title='TCPDirect · 应用主动推进收发', subtitle='对照 Onload：改用 ZF 接口，由应用显式推进收发事件。', color='#8055b4', badge='sfc 管理网卡',
      init=[('等待并取出订单', ['order_queue_.front(...)'], '业务层沿用订单队列'), ('按需创建用户态栈', ['zf_stack_alloc(...)'], '已有栈和连接时复用'), ('发起 TCP 连接', ['zft_connect(...)'], 'reactor 推进连接握手')],
      send=['send_all(...)','  → zft_send_single(...)'], recv=['recv_all(...)','  → zft_zc_recv(...)','  → zft_zc_recv_done(...)'],
      left='订单线程 · 显式 ZF 调用', middle='同一进程 · ZF 库', stack='用户态 TCP/IP', tx=['提交待发送字节','维护连接和重传状态'], rx=['借出接收缓冲区','应用消费后归还'], driver='ZF / VI',
      wait=['Z4 · 暂无进展时继续推进','zf_reactor_perform(stack_)','处理事件 → 再尝试发送 / 接收。'],
      benefit='更直接地控制事件与缓冲区；应用需要写循环、处理返回值并归还缓冲区。', resource='内核模块 / sfc 分配 VI；本课仍将接收字节复制到 Soup 解析缓冲区。'),
 dict(key='D', file='05-dpdk-fstack-order-path.svg', title='DPDK + F-Stack · 由轮询循环驱动', subtitle='对照前三路：改用 ff_* 与 PMD，vfio-pci 接管网卡。', color='#b56a12', badge='vfio-pci 接管',
      init=[('初始化网络栈', ['ff_init(...)'], '初始化 F-Stack 与 DPDK'), ('发起 TCP 连接', ['ff_socket / ff_connect'], '连接进度由事件循环推进'), ('运行轮询循环', ['ff_run(drive_entry, this)'], '回调处理业务与网络事件')],
      send=['maybe_start_order()','  → flush_tx()','  → ff_send(...)'], recv=['drain_rx()','  → ff_recv(...)','  → process_soup(...)'],
      left='轮询线程 · drive() 回调', middle='F-Stack + DPDK', stack='用户态 TCP/IP', tx=['F-Stack 处理 TCP','net_sfc_efx PMD 发包'], rx=['PMD 轮询收包','F-Stack 还原 TCP 字节流'], driver='DPDK PMD',
      wait=['D4 · 本课如何交接订单？','DEQUE_CV → 桥接线程 → 交接区','轮询线程取单，ff_run 持续推进。'],
      benefit='直接控制用户态报文处理；本课还包含桥接与轮询线程之间的交接成本。', resource='VFIO 建立设备访问与 DMA 映射；IOMMU 检查网卡访问内存的范围。'),
]


def draw_path(c):
    d=Drawing(c['title'],c['subtitle'],c['color'],c['badge'],height=1400)
    heading='连接准备与启动' if c['key']=='D' else '首笔取单后按需建连，后续复用'
    d.text(40,161,c['key']+'1 · '+heading,23,c['color'],700)
    for i,(title,code,note) in enumerate(c['init']):
        x=40+i*386
        d.box(x,181,348,178)
        icons={'K':['loop','code','plug'],'O':['code','loop','plug'],'Z':['loop','stack','plug'],'D':['code','plug','loop']}
        d.icon(icons[c['key']][i],x+14,197,c['color'])
        d.text(x+76,223,title,23,INK,700)
        # Keep the complete 48px icon above the code block, including its stroke.
        d.code(x+12,260,324,code)
        d.text(x+14,344,note,18,MUTED)
        if i<2: d.line(x+352,286,x+372,286,'muted')
    d.items.append('<g transform="translate(0 30)">')
    d.box(40,355,498,637,'#edf4fc','#d7e5f4')
    d.box(582,355,270,637,'#eaf5f1' if c['key']!='K' else '#edf0f5','#d7e5e3')
    d.box(896,355,264,637,'#fff','#d7e5f4')
    d.text(58,391,c['left'],23,INK,700)
    d.text(600,390,c['middle'],19,INK,700)
    d.icon('nic',911,372,c['color']);d.text(975,404,'X2522',26,INK,700)
    d.text(60,440,c['key']+'2 · 发出本笔订单',25,BLUE,700)
    d.code(60,460,456,c['send'])
    d.text(75,606,{'K':'send 调用：用户态 → 内核态','O':'send 调用由 libonload 接手','Z':'应用显式调用 ZF 收发接口','D':'ff_send 把字节交给 F-Stack TCP'}[c['key']],19,MUTED)
    d.icon('stack',600,407,BLUE)
    d.text(600,493,c['stack'],24,BLUE,700)
    for i,s in enumerate(c['tx']):d.text(600,530+i*33,s,19,MUTED)
    d.text(600,611,c['driver'],21,BLUE,700)
    d.queue(927,487,'TX · 发送资源',BLUE)
    d.text(927,605,'排队后从端口发送',18,MUTED)
    d.line(524,550,568,550)
    d.line(860,550,882,550)
    d.text(60,720,c['key']+'3 · 取回成交回报',25,TEAL,700)
    d.code(60,741,456,c['recv'])
    d.text(75,884,'字节齐全后，解析 Soup / OUCH',19,MUTED)
    d.icon('stack',600,710,TEAL)
    for i,s in enumerate(c['rx']):d.text(600,788+i*33,s,19,MUTED)
    d.text(600,883,c['driver'],21,TEAL,700)
    d.queue(927,768,'RX · 接收队列',TEAL)
    d.text(927,886,'网卡 DMA 写入缓冲区',18,MUTED)
    d.line(888,829,866,829,'rx')
    d.line(574,829,552,829,'rx')
    if c['key'] in ('O','Z'):
        d.text(924,643,'小包可用 CTPIO',18,c['color'])
        d.text(924,670,'整包到卡后发送',18,MUTED)
        d.text(924,697,'事件队列报告收发进展',18,MUTED)
    elif c['key']=='D':
        d.text(924,652,'PMD 管理描述符',18,c['color'])
        d.text(924,680,'轮询完成状态',18,MUTED)
    else:
        d.text(924,652,'sfc 管理描述符',18,c['color'])
        d.text(924,680,'中断 / NAPI 处理接收',18,MUTED)
    d.box(40,1012,812,236,'#fff','#dce6ef')
    d.icon('loop',58,1038,c['color'])
    d.text(123,1052,c['wait'][0],23,INK,700)
    if c['key']=='D':
        for i,label in enumerate(['DEQUE_CV','桥接线程','交接区','轮询线程']):
            x=64+i*196
            d.box(x,1096,154,60,'#fff8e9','#dfc497',10)
            d.text(x+77,1133,label,21,INK,600,'middle')
            if i<3:d.line(x+158,1126,x+182,1126,'muted')
        d.text(66,1194,'ff_run 反复调用 drive()，继续未完成的发送和接收。',22,MUTED)
        d.text(66,1226,'交接结构属于本课客户端；不是所有 DPDK 程序的固定写法。',20,MUTED)
    else:
        first,second,forward,back={
            'K':('::recv(...)','内核等待 / 唤醒','暂无数据','数据可读，调用返回后继续解析'),
            'O':('Socket 收发调用','Onload 库处理事件','进入库','无数据时先轮询，最长 100 ms，再阻塞等待'),
            'Z':('尝试发送 / 接收','zf_reactor_perform(stack_)','暂无进展','处理事件后，再次尝试收发'),
        }[c['key']]
        d.box(64,1100,250,60,'#eef5fb','#bed3e5',10)
        d.box(444,1100,380,60,'#eff6f4','#b8d9ce',10)
        d.text(189,1137,first,22,INK,600,'middle')
        d.text(634,1137,second,21,INK,600,'middle',mono=c['key']=='Z')
        d.line(322,1130,430,1130,'tx');d.text(376,1092,forward,19,MUTED,400,'middle')
        d.items.append('<path class="flow" d="M634 1168 V1216 H189 V1186" fill="none" stroke="#078576" stroke-width="3" stroke-linecap="butt" marker-end="url(#rx)"/>')
        d.text(402,1200,back,19,MUTED,400,'middle')
    d.box(896,1054,264,94,'#e6edf6','#bdcddd')
    d.icon('server',912,1070,BLUE);d.text(974,1090,'Exchange',23,INK,700);d.text(974,1125,'TCP 订单 / 回报',17,MUTED)
    d.line(996,997,996,1040,'tx');d.line(1080,1046,1080,1006,'rx')
    d.text(40,1289,c['benefit'],23,INK,700)
    d.icon('shield',40,1303,'#6a8295');d.text(103,1335,c['resource'],19,MUTED)
    d.items.append('</g>')
    d.save(c['file'])


def draw_vi_ctpio():
    d=Drawing('VI 与 CTPIO · 资源与发送方式',
              'VI 提供网卡收发资源；CTPIO 改变 CPU 把报文交给网卡的方式。',
              TEAL, 'X2522 / Onload', height=1260)
    d.text(40,164,'① 应用仍写 Socket；Onload 库使用 VI',24,TEAL,700)
    d.box(40,190,300,174)
    d.icon('code',56,207,BLUE);d.text(116,239,'你的交易程序',24,INK,700)
    d.code(56,264,268,['send_all → ::send','recv_all → ::recv'])
    d.box(402,190,300,174,'#e8f5f1','#bdded2')
    d.icon('chip',418,207,TEAL);d.text(478,239,'Onload 库',24,INK,700)
    d.text(423,294,'CPU 执行 TCP/IP 处理',21,INK,700)
    d.text(423,330,'使用队列，读取事件',21,MUTED)
    d.box(770,190,390,228,'#fff','#b4d9cf')
    d.icon('nic',789,202,TEAL);d.text(850,235,'VI · 一套收发资源',24,INK,700)
    rows=[('TX','发送队列 / 发送入口',BLUE),('RX','接收队列 → 收包缓冲',TEAL),('EVQ','事件队列 → 收发进展','#8055b4')]
    for i,(label,desc,color) in enumerate(rows):
        y=255+i*47
        d.box(789,y,68,34,'#f1f6fa',color,6)
        d.text(823,y+24,label,19,color,700,'middle')
        d.text(871,y+25,desc,20,INK,700)
    d.line(348,286,388,286,'tx');d.line(394,331,354,331,'rx')
    d.line(710,286,756,286,'tx');d.line(762,331,716,331,'rx')
    d.text(40,407,'蓝色：发送方向　绿色：回报方向',19,MUTED)
    d.box(40,439,1120,61,'#eef2fa','#d6e0ef',12)
    d.text(60,476,'sfc 与配套内核模块先分配资源；Onload 库使用它们，业务代码无需直接操作网卡队列。',22,INK,700)
    d.text(40,544,'② 同一个 VI，可使用不同的发送方式',24,TEAL,700)

    def node(x,y,icon,title,detail,color):
        d.box(x,y,300,110,'#fff','#d2dfec',12)
        d.icon(icon,x+16,y+10,color)
        d.text(x+77,y+40,title,23,INK,700)
        d.text(x+18,y+86,detail,20,MUTED)

    d.box(40,569,1120,225,'#edf4fd','#ccddf3')
    d.text(60,605,'DMA 发送 · 网卡从主机内存读取报文',24,BLUE,700)
    node(60,627,'chip','CPU / Onload 库','准备报文与 TX 描述符',BLUE)
    node(450,627,'stack','主机内存','保存待发送的报文',BLUE)
    node(840,627,'nic','X2522 网卡','DMA 取回报文，再发送',BLUE)
    d.line(368,683,436,683,'tx');d.line(758,683,826,683,'tx')
    d.text(60,771,'描述符告诉网卡报文在哪里；网卡经 PCIe 发起 DMA 读取。',21,INK,700)

    d.box(40,819,1120,225,'#e9f7f1','#badfcf')
    d.text(60,855,'CTPIO 发送 · CPU 经 PCIe 把报文推到网卡',24,TEAL,700)
    node(60,877,'chip','CPU / Onload 库','读出待发送的小报文',TEAL)
    node(450,877,'plug','PCIe 写入','CPU 把报文直接写向网卡',TEAL)
    node(840,877,'nic','X2522 发送端','本课整包到卡后发送',TEAL)
    d.line(368,933,436,933,'tx');d.line(758,933,826,933,'tx')
    d.text(60,1021,'减少等待网卡 DMA 取报文的环节；不符合条件时仍可使用 DMA。',21,INK,700)

    d.text(40,1092,'③ 对本课代码有什么影响？',24,TEAL,700)
    d.box(40,1116,1120,107,'#fff','#d6e0eb')
    d.text(62,1156,'业务仍调用 send / recv；VI 的操作与 CTPIO 的选择发生在 Onload 库内部。',23,INK,700)
    d.text(62,1195,'CTPIO 只涉及发送；接收仍由网卡 DMA 写入缓冲区，再由库处理回报。',22,MUTED)
    d.save('05-onload-vi-ctpio.svg')


def draw_pmd_queues():
    d=Drawing('PMD · 谁来操作网卡队列？',
              'F-Stack 处理 TCP，PMD 管理队列，网卡通过 DMA 搬运报文。',
              '#b56a12','收发分工',height=816)
    # Arrows show processing order, not a route that copies packet bytes through the PMD.
    d.items[1]=('<title id="title">PMD 的收发分工</title><desc id="desc">'
                '发送从左到右，接收从右到左；箭头表示处理先后。'
                'PMD 在主机 CPU 上操作描述符并检查完成事件，网卡 DMA 直接读写主机缓冲区。</desc>')
    for x,icon,title,note,color in [
        (40,'stack','F-Stack','用户态 TCP/IP 栈',BLUE),
        (430,'loop','DPDK PMD','用户态网卡驱动','#b56a12'),
        (820,'nic','X2522 网卡','执行报文收发',TEAL),
    ]:
        d.icon(icon,x+16,157,color)
        d.text(x+82,181,title,26,color,700)
        d.text(x+82,215,note,20,MUTED)
    d.text(40,260,'发送 → 先准备报文，再通知网卡取包',24,BLUE,700)
    for x in [40,430,820]:d.box(x,282,340,194,'#fff','#cbdff3')
    d.text(60,321,'① 组成 TCP/IP 报文',24,INK,700)
    d.icon('server',60,348,BLUE)
    d.text(126,371,'主机发送缓冲区',22,BLUE,700)
    d.text(60,443,'报文字节保存在这里',21,MUTED)
    d.text(450,321,'② 写 TX 描述符',24,INK,700)
    for i in range(6):d.box(450+48*i,345,36,36,'#e3eff9',BLUE,4)
    d.text(450,411,'记录缓冲地址与长度',22,INK,700)
    d.text(450,445,'通知网卡有报文待发',21,MUTED)
    d.text(840,321,'③ DMA 读取报文',24,INK,700)
    d.icon('nic',840,351,BLUE)
    d.text(906,374,'从主机缓冲区取包',21,BLUE,700)
    d.text(840,443,'网卡随后发到网络',21,MUTED)
    d.line(386,370,418,370,'tx');d.line(776,370,808,370,'tx')

    d.text(40,525,'接收 ← 网卡先写入缓冲区，再交给协议栈',24,TEAL,700)
    for x in [40,430,820]:d.box(x,548,340,194,'#fff','#bce0d4')
    d.text(840,587,'① DMA 写入报文',24,INK,700)
    d.icon('server',840,613,TEAL)
    d.text(906,637,'主机接收缓冲区',22,TEAL,700)
    d.text(840,709,'使用提前备好的缓冲区',21,MUTED)
    d.text(450,587,'② 轮询完成事件',24,INK,700)
    for i in range(6):d.box(450+48*i,610,36,36,'#dff4ee',TEAL,4)
    d.text(450,676,'找到已收到的报文',22,INK,700)
    d.text(450,710,'交给 F-Stack，并补 RX 缓冲',20,MUTED)
    d.text(60,587,'③ 处理 TCP 回报',24,INK,700)
    d.icon('stack',60,616,TEAL)
    d.text(126,637,'恢复 TCP 字节流',22,TEAL,700)
    d.text(60,709,'应用用 ff_recv 取回数据',21,MUTED)
    d.line(814,636,782,636,'rx');d.line(424,636,392,636,'rx')
    d.text(40,783,'箭头表示处理先后；描述符记录缓冲区信息，报文字节由网卡 DMA 直接读写。',22,MUTED)
    d.save('05-pmd-queues.svg')


def source_reader():
    archive=ROOT/'artifacts/blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-source.tgz'
    names=['posix_order_transport.cpp','common.hpp','tcpdirect_order_transport.cpp','dpdk_trader.cpp','trader.cpp','order_queue.hpp','nasdaq_protocol.hpp','order_transport.hpp']
    original={}
    with tarfile.open(archive) as t:
        for n in names: original[n]=t.extractfile('flle-trading-lab-v13-source/src/'+n).read().decode()
    addon=ROOT/'artifacts/blobs/x2522/ch05-four-path/posix-qos-v1/flle-posix-qos-v1-x86_64-jammy.tgz'
    with tarfile.open(addon) as t:
        for n in ('posix_order_transport.cpp','trader.cpp','order_transport.hpp'):
            original[n]=t.extractfile('flle-posix-qos-v1/source/src/'+n).read().decode()
    control=(ROOT/'apps/flle-trading-lab/scripts/transport_labctl.sh').read_text()
    original['start_sfc_clients.sh']='start_accelerated_clients() {'+control.split('start_accelerated_clients() {',1)[1].split('\nallocate_dpdk_user_ref_slot() {',1)[0]
    # Plain source copies let Markdown links open the exact taught version in the IDE.
    source_dir=HERE/'source-reading'
    source_dir.mkdir(exist_ok=True)
    for name,source in original.items():
        (source_dir/name).write_bytes(source.encode())
    # Exact source, with numbering outside the code. No copy masquerades as edited runtime source.
    groups=[('K1','posix_order_transport.cpp','  bool connect('),('K2','common.hpp','inline bool send_all('),('K3','common.hpp','inline bool recv_all('),('K4','common.hpp','    const auto received = ::recv('),
            ('O1','start_sfc_clients.sh','onload --profile=latency'),('O2','common.hpp','inline bool send_all('),('O3','common.hpp','inline bool recv_all('),
            ('Z1','tcpdirect_order_transport.cpp','  bool connect('),('Z2','tcpdirect_order_transport.cpp','  bool send_all('),('Z3','tcpdirect_order_transport.cpp','  bool recv_all('),('Z4','tcpdirect_order_transport.cpp','      zf_reactor_perform(stack_);'),
            ('D1','dpdk_trader.cpp','  int run('),('D2','dpdk_trader.cpp','  void flush_tx('),('D3','dpdk_trader.cpp','  void drain_rx('),('D4','dpdk_trader.cpp','  void bridge_loop(')]
    # Repeated calls need a function boundary, not a first match in the file.
    contexts={'Z4':'  bool send_all('}
    def anchor_line(label,name,needle):
        lines=original[name].splitlines()
        start=next(i for i,l in enumerate(lines) if contexts[label] in l) if label in contexts else 0
        return next(i+1 for i in range(start,len(lines)) if needle in lines[i])
    anchors={}; links=[]
    for label,name,needle in groups:
        number=anchor_line(label,name,needle)
        anchors.setdefault((name,number),[]).append(label)
        links.append(f'<a href="#{label}">{label} · {e(name)}:{number}</a>')
    editor_root='/' + str(source_dir.relative_to(ROOT))
    index=['# 第五章源码索引', '', '这些文件供阅读与图文对照。Socket／Onload 的 trader.cpp、posix_order_transport.cpp、order_transport.hpp 来自 posix-qos-v1 更新包；其余 C++ 文件逐字来自 v13 封存源码；`start_sfc_clients.sh` 仅摘录当前控制脚本中的启动函数。这里不参与编译、安装或启动。', '', '下面使用以项目根目录为起点的绝对链接，直接打开文件与对应行；对应磁盘目录为 `/qyt-fll/assets/05-kernel-bypass/source-reading/`。', '', '| 图中位置 | 原始源码 |', '|---|---|']
    for label,name,needle in groups:
        number=anchor_line(label,name,needle)
        index.append(f'| {label} | [{name}:{number}]({editor_root}/{name}#L{number}) |')
    index += ['', f'队列等待实现：[order_queue.hpp]({editor_root}/order_queue.hpp#L80)。', '', 'O4 的事件推进由外部 Onload 库实现；项目沿用 Socket 接口。完整浏览器阅读页与 SHA 映射位于上级目录。', '']
    (source_dir/'README.md').write_text('\n'.join(index))
    page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>第五章 · 图与完整源码对照</title>',
          '<style>html{scroll-padding-top:24px}body{margin:0;background:#f3f6fa;color:#17324a;font:17px/1.75 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:32px}h1{font-size:30px}nav{display:flex;gap:8px;flex-wrap:wrap}a{color:#1267ab}nav a{background:white;border:1px solid #d4e0ed;border-radius:7px;padding:4px 10px;font-size:14px}section{background:white;padding:22px;margin:24px 0;border-radius:14px}pre{max-height:720px;overflow:auto;background:#122c41;color:#e5f0fc;border-radius:10px;padding:14px 0;font:14px/1.7 "DejaVu Sans Mono",monospace}.line{display:block;padding:0 14px;min-height:24px}.line:target{background:#365478;outline:2px solid #58c4e5}.number{display:inline-block;width:48px;color:#99afc5;user-select:none}.label{color:#ffcd6e;font-weight:bold}.note{border-left:5px solid #18a389;padding:8px 16px;background:#e5f5ee}</style><main>',
          '<h1 id="top">第五章 · 图与完整源码对照</h1><p>图上 K / O / Z / D 分别对应 Kernel Socket、Onload、TCPDirect 和 DPDK + F-Stack。点击编号跳到真实函数；Socket／Onload 的 trader.cpp、posix_order_transport.cpp、order_transport.hpp 来自 posix-qos-v1 更新包，其余 C++ 来自 v13 封存源码；末尾启动函数来自当前控制脚本。每个代码窗可滚动阅读完整文件。行号和黄色编号属于阅读标记，图中调用省略了部分参数。</p>',
          '<p class="note" id="O4">先沿正文的图看调用关系，再读对应函数。Onload 沿用 K 的 Socket 代码；O4 的轮询/等待由外部 Onload 库实现。代码中的 send_all / recv_all 是本项目封装，并非 Linux 系统调用。</p>', '<nav>'+''.join(links)+'</nav>']
    for name,text in original.items():
        page.append(f'<section id="{name}"><h2>{e(name)}</h2><p>SHA-256：<code>{hashlib.sha256(text.encode()).hexdigest()}</code> · <a href="#top">返回页首</a></p><pre>')
        for i,line in enumerate(text.splitlines(),1):
            tags=anchors.get((name,i),[])
            labels=' '.join(tags)
            markers=''.join(f'<span id="{tag}"></span>' for tag in tags)
            page.append(f'<span class="line" id="{name}-L{i}">{markers}<span class="number">{i}</span>{e(line)}'+(f'  <span class="label">← {labels}</span>' if tags else '')+'</span>')
        page.append('</pre></section>')
    page.append('</main></html>')
    (HERE/'code-reading.html').write_text(''.join(page).replace('.line:target{', '.line:target,.line:has(:target){')+'\n')
    (HERE/'CODE-MAP.json').write_text(json.dumps({'posix_source_archive':str(addon.relative_to(ROOT)),'posix_source_archive_sha256':hashlib.sha256(addon.read_bytes()).hexdigest(),'source_archive':str(archive.relative_to(ROOT)),'source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'editor_source_directory':str(source_dir.relative_to(ROOT)),'source_files':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in original.items()},'anchors':[{'id':label,'file':name,'search':needle,'line':anchor_line(label,name,needle),**({'within':contexts[label]} if label in contexts else {})} for label,name,needle in groups]},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    for c in CONFIGS:draw_path(c)
    draw_vi_ctpio()
    draw_pmd_queues()
    source_reader()
    print('Built four code paths, VI/CTPIO and PMD diagrams, and complete source readers.')
