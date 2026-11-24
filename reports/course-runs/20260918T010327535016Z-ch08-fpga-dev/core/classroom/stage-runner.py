#!/usr/bin/env python3
"""Run one classroom card from .111; preserve its output and remote work."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = Path('/financial-low-latency')
REPORTS = REPO / 'Documents/reports'
DEFAULT_STATE = REPORTS / 'run-state/ch08-fpga-dev.env'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
       'root@10.1.1.101']
STAGES = {
    '1.1': ('operations/1.1-distribute.sh', '分发源码与准备共享工具'),
    '1.2': ('remote/1.2-check.sh', '自动核对开发机与本轮材料'),
    '1.3': ('remote/1.3-install.sh', '安装本轮开发工具'),
    '3.1': ('remote/3.1-compile.sh', '编译 RTL 与测试环境'),
    '3.2': ('remote/3.2-simulate.sh', '运行功能仿真'),
    '3.3': ('remote/3.3-management.sh', '测试管理逻辑'),
    '3.4': ('remote/3.4-synthesize.sh', '综合过滤数据通路'),
    '3.5': ('remote/3.5-synthesize-registers.sh', '综合控制寄存器'),
    '3.6': ('operations/3.6-collect.sh', '保存本轮完整结果'),
}


def read_state(path):
    state = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        values = shlex.split(value)
        if len(values) != 1:
            raise ValueError('运行态字段格式错误: ' + key)
        state[key] = values[0]
    run = state['RUN_ID']
    if not re.fullmatch(r'\d{8}T\d{6}(?:\d{6})?Z-ch08-fpga-dev', run):
        raise ValueError('RUN_ID 格式不符；从 1.1 重新准备')
    expected = {'FLLE_DEV': '/opt/flle-ch08-dev/' + run,
                'FLLE_CORE': '/opt/flle-ch08-dev/' + run + '/core',
                'RESULT_DIR': str(REPORTS / 'course-runs' / run)}
    for key, value in expected.items():
        if state.get(key) != value:
            raise ValueError('运行态路径不符: ' + key)
    if state.get('PURPOSE') != 'ch08-fpga-development':
        raise ValueError('运行态用途不符')
    return state


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        raise SystemExit('用法: stage-runner.py ' + '|'.join(STAGES))
    stage = sys.argv[1]
    script_name, title = STAGES[stage]
    script = HERE / script_name
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    state_path = Path(os.environ.get('FLLE_CH08_STATE', str(DEFAULT_STATE))).resolve()
    error = None
    state = {}
    try:
        ips = subprocess.check_output(['ip', '-4', '-o', 'address', 'show'], text=True)
        if not re.search(r'\binet 10\.1\.1\.111/', ips):
            raise RuntimeError('本入口必须在 .111 执行')
        if stage == '1.1':
            run = stamp + '-ch08-fpga-dev'
            state = {'RUN_ID': run, 'FLLE_DEV': '/opt/flle-ch08-dev/' + run,
                     'RESULT_DIR': str(REPORTS / 'course-runs' / run)}
        else:
            state = read_state(state_path)
        attempt = Path(state['RESULT_DIR']) / 'steps' / (stamp + '-' + stage)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        error = str(exc)
        attempt = REPORTS / 'ch08-entry-errors' / (stamp + '-' + stage)
    attempt.mkdir(parents=True, exist_ok=False)
    transcript = attempt / 'classroom.log'
    metadata = {'stage': stage, 'started_at_utc': stamp, 'state_file': str(state_path),
                'run_id': state.get('RUN_ID'), 'script': script_name,
                'stage_exit': None, 'capture_exit': None}
    with transcript.open('w', buffering=1) as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + '\n')

        def execute(command, stdin=None):
            emit('$ ' + shlex.join(command))
            with subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, bufsize=1,
                                  env=env) as proc:
                for line in proc.stdout:
                    emit(line.rstrip('\n'))
                return proc.wait()

        emit(f'{socket.gethostname()} / 第 {stage} 步 · {title}')
        emit('===== 本步开始：自动执行并保存输出 =====')
        emit('[执行位置] 对: 操作终端 .111，开发机 .101  证: 下面保留命令及原始返回')
        emit('本步记录目录: ' + str(attempt))
        env = os.environ.copy()
        env.update(FLLE_CH08_STATE=str(state_path),
                   FLLE_CH08_PUBLISH_CURRENT='1' if state_path == DEFAULT_STATE else '0')
        rc = 1
        try:
            if error:
                raise RuntimeError(error)
            shutil.copy2(script, attempt / script.name)
            metadata['script_sha256'] = hashlib.sha256(script.read_bytes()).hexdigest()
            if stage == '1.1':
                env['FLLE_CH08_RUN_ID'] = state['RUN_ID']
            if script_name.startswith('remote/'):
                command = SSH + ['bash', '-s', '--', state['FLLE_DEV'] + '/dev.env']
                with script.open('rb') as source:
                    rc = execute(command, stdin=source)
            else:
                command = ['bash', str(script)]
                rc = execute(command)
            metadata['stage_exit'] = rc
            if script_name.startswith('remote/'):
                emit('===== 保存开发机工作记录到 .111 =====')
                emit('[结果留存] 对: 收回截至本步的 work 目录  证: 即使本步失败也尝试保存日志')
                capture = ('set -eu; cd ' + shlex.quote(state['FLLE_DEV']) +
                           '; if test -d work; then tar -czf - work; '
                           'else tar -czf - --files-from /dev/null; fi')
                command = SSH + [capture]
                emit('$ ' + shlex.join(command) + ' > remote-work.tgz')
                with (attempt / 'remote-work.tgz').open('wb') as archive:
                    fetched = subprocess.run(command, stdout=archive, stderr=subprocess.PIPE)
                if fetched.stderr:
                    emit(fetched.stderr.decode(errors='replace').rstrip())
                metadata['capture_exit'] = fetched.returncode
                if fetched.returncode:
                    rc = rc or fetched.returncode
                else:
                    emit('已保存开发机累计工作文件: ' + str(attempt / 'remote-work.tgz'))
        except (OSError, RuntimeError) as exc:
            emit('执行错误: ' + str(exc))
            rc = rc or 1
        emit('===== 本步结束 =====')
        emit(f'步骤退出码: {metadata["stage_exit"]}; 结果收回退出码: {metadata["capture_exit"]}')
        if rc:
            emit('本步未完成；保留以上错误与日志，修正后重跑本卡。')
        else:
            emit('本步执行完成；核对以上返回后，再执行下一张卡。')
        emit('终端完整记录: ' + str(transcript))
    metadata['exit_code'] = rc
    (attempt / 'receipt.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    checksums = []
    for path in sorted(attempt.iterdir()):
        if path.is_file():
            checksums.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
    (attempt / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
    return rc if rc >= 0 else 128 - rc


if __name__ == '__main__':
    sys.exit(main())
