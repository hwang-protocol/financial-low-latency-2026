#!/usr/bin/env python3
"""Validate receipts before displaying bounded, data-derived classroom results."""
from pathlib import Path
import importlib.util
import json
import re
import sys

spec = importlib.util.spec_from_file_location('classroom', Path(__file__).with_name('classroom-output.py'))
classroom = importlib.util.module_from_spec(spec); spec.loader.exec_module(classroom)


HEADERS = {
    'prepare': ['vm-2522-02 / build', '===== 查构建自测与正常放行 =====',
                '[RTL] 对: 六项自测通过 / 真实行情尚未丢包  证: 发令前先确认过滤路径正常',
                '$ bash Documents/newDoc/assets/09-verilator/08a-prepare-rtl-filter.sh'],
    'arm': ['vm-2522-02 / control', '===== 查一次丢包指令 =====',
            '[block] 对: 指令已消费 / 现场暂停  证: 发令与下一步查看分开',
            '$ bash Documents/newDoc/assets/09-verilator/08b-arm-rtl-filter.sh'],
    'verify': ['vm-2522-02 / verify', '===== 查丢弃与缺失序号 =====',
               '[Feed] 对: 同一序号 / 缺口1 / 拒单  证: 过滤判决与接收结果一致',
               '$ bash Documents/newDoc/assets/09-verilator/08c-verify-rtl-filter.sh'],
    'restore': ['vm-2522-02 / restore', '===== 查行情与交易恢复 =====',
                '[恢复] 对: 健康行情 / 两笔成交 / 净持仓不变  证: 实验结束后可继续交易',
                '$ bash Documents/newDoc/assets/09-verilator/08d-restore-rtl-filter.sh'],
}


def heading(action):
    return '\n'.join(HEADERS[action])+'\n'


def require(condition, message):
    if not condition: raise ValueError(message)


def read(out, name):
    return (out/'raw'/name).read_text()


def data(out, name):
    return json.loads(read(out, name+'.json'))


def context(out, name, health, session=None):
    obj = data(out, name)
    require(obj['market_mode'] in {'MULTICAST_A', 'MULTICAST'} and obj['replay']['status'] == 'PAUSED', 'classroom path/playback changed')
    require(obj['feed']['integrity'] == health and obj['feed']['path'] == 'UNICAST', 'unexpected receiver state')
    require(obj['health']['trader_auto']['status'] == 'ONLINE', 'receiver offline')
    require(obj['session'] == obj['feed']['session'], 'receiver session mismatch')
    if session is not None: require(obj['session'] == session, 'session changed between stages')
    return obj


def adapter(out, name, drops):
    text = read(out, name+'.log')
    require(text.splitlines().count('adapter_ready mode=allow remaining_drops=0') == 1, 'missing initial allow state')
    rows = [line for line in text.splitlines() if line.startswith('rtl_drop ')]
    arms = [line for line in text.splitlines() if line.startswith('adapter_arm ')]
    require(len(rows) == drops and len(arms) == drops, 'unexpected DROP/arm count')
    if drops:
        match = re.fullmatch(r'rtl_drop sequence=(\d+) remaining=0 drop_count=1', rows[0])
        require(match is not None, 'invalid DROP receipt')
        return int(match[1])
    return None


def gap(out, live=False):
    feed = data(out, 'feed-verify' if live else 'feed-gap')
    require(feed['trader_auto'] == 'ONLINE', 'receiver not online')
    sequence = adapter(out, 'adapter-verify' if live else 'adapter-armed', 1)
    f = feed['feed']
    require(f['integrity'] == 'GAP' and f['gap_size'] == 1 and f['next_expected'] == sequence,
            'DROP does not match exactly one missing message')
    require(f['trading_gate'] == 'INHIBITED_FEED_GAP', 'order gate not inhibited')
    snapshot = context(out, 'state-verify' if live else 'state-armed', 'GAP', feed['session'])
    require(snapshot['feed']['next_expected'] == sequence and snapshot['feed']['gap_size'] == 1,
            'paused snapshot differs from DROP')
    require(feed['session'] == data(out, 'feed-baseline')['session'], 'replay restarted since preparation')
    if live: require(feed['session'] == data(out, 'feed-gap')['session'], 'captured gap belongs to another session')
    return feed, sequence


def render(action, out):
    if action == 'prepare':
        test = classroom.render('selftest', read(out, 'build-and-selftest.txt'))
        required = 'rtl_selftest=PASS allow=1 target_drop=1 second_pass=1 locate_mismatch_pass=1 stock_mismatch_pass=1 type_f_pass=1\n'
        require(test == required, 'six selftests did not all pass')
        adapter(out, 'adapter-prepared', 0)
        baseline = data(out, 'feed-baseline')
        require(baseline['trader_auto'] == 'ONLINE' and baseline['feed']['integrity'] == 'HEALTHY', 'baseline is not healthy')
        snapshot = context(out, 'state-prepared', 'HEALTHY', baseline['session'])
        require(snapshot['feed']['gap_size'] == 0 and snapshot['feed']['trading_gate'] == 'OPEN', 'baseline is not open')
        return (heading('prepare')+test+
                'adapter_ready mode=allow remaining_drops=0\n本次策略丢包数：0\n'+
                classroom.render('feed', json.dumps(baseline))+
                '重放已暂停；下一步由你执行发令脚本。\n')
    if action == 'before-arm':
        baseline = data(out, 'feed-baseline')
        context(out, 'state-before-arm', 'HEALTHY', baseline['session'])
        adapter(out, 'adapter-before-arm', 0)
        return 'before_arm=PASS\n'
    if action in {'arm', 'gap', 'verify'}:
        feed, seq = gap(out, live=action != 'arm')
        if action == 'arm':
            return (heading('arm')+read(out, 'block-command.txt')+
                    '重放已短暂运行并暂停，现场已保留；下一步查看丢包与缺口。\n')
        if action == 'gap': return 'gap_precheck=PASS\n'
        gate = data(out, 'order-gate')
        require(gate['http_status'] == 400 and gate['error'] == 'FEED_NOT_HEALTHY', 'order was not rejected')
        require(data(out, 'gui-gap-contract')['result'] == 'PASS', 'GUI contract failed')
        return (heading('verify')+
                f'rtl_drop sequence={seq} remaining=0 drop_count=1\n'+
                classroom.render('feed', json.dumps(feed))+classroom.render('gate', json.dumps(gate))+
                '丢弃序号 = 缺失序号，丢弃数 = 缺口数 = 1。现场仍暂停；讲解后执行恢复。\n')
    if action == 'restore':
        require(read(out, 'adapter-stop.txt').strip() == 'adapter_stopped=1 control_absent=1', 'adapter cleanup not confirmed')
        orders = data(out, 'post-restore-orders'); state = data(out, 'state-restored')
        require(orders['result'] == 'PASS' and len(orders['orders']) == 2 and
                all(order['result'] == 'ORDER_EXECUTED' for order in orders['orders']), 'recovery orders failed')
        positions = orders['position_AAPL']
        require(len(positions) == 2 and positions[0] == positions[1], 'position not restored')
        saved = json.loads((out/'session.json').read_text())
        require(state['market_mode'] == saved['original_mode'] and state['replay']['status'] == saved['original_playback'], 'original mode/playback not restored')
        require(state['feed']['integrity'] == 'HEALTHY' and state['feed']['trading_gate'] == 'OPEN', 'final feed not healthy')
        require(orders['feed']['integrity'] == 'HEALTHY' and orders['feed']['trading_gate'] == 'OPEN' and
                orders['feed']['session'] == state['feed']['session'], 'order receipts belong to another or unhealthy session')
        return (heading('restore')+read(out, 'adapter-stop.txt')+
                classroom.render('orders', json.dumps(orders))+
                '行情发送与播放方式已恢复，临时过滤进程已退出。\n')
    raise ValueError('unknown stage')


if __name__ == '__main__':
    try: print(render(sys.argv[1], Path(sys.argv[2])), end='')
    except (ValueError, KeyError, TypeError, OSError) as exc: sys.exit('回执检查失败：'+str(exc))
