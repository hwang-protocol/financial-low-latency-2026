#!/usr/bin/env python3
"""用模拟命令检查准备 B 的课堂打印，不连接设备、不切换现场。"""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "assets/05-kernel-bypass/03-four-path-lab-ready.sh"
RUN_ID = "20260907T112313Z-02-trading-platform"
MOCKS = r"""
pgrep(){ return 1; }
ssh(){
  if [[ " $* " == *" root@10.1.1.1 "* ]]; then
    MOCK_EXCHANGE_READS=$(( ${MOCK_EXCHANGE_READS:-0} + 1 ))
    local pid=101
    if [[ "${MOCK_IDENTITY_DRIFT:-0}" = 1 && "$MOCK_EXCHANGE_READS" -gt 1 ]]; then pid=103; fi
    printf 'pid=%s start_ticks=100 boot_id=unit-boot\n' "$pid"
    printf 'aaaaaaaa  /var/tmp/unit/transport.deployed.sha256\n'
  else
    printf 'pid=102 start_ticks=200 boot_id=unit-boot\n'
    printf 'bbbbbbbb  /var/tmp/unit/source.sha256\n'
  fi
}
curl(){
  printf '%s\n' '{"mode":"SFC","transition":"READY","owner":"sfc","clients":{"trader_manual":{"health":{"status":"ONLINE"}},"trader_onload":{"health":{"status":"ONLINE"}},"trader_tcpdirect":{"health":{"status":"ONLINE"}}}}'
}
python3(){
  if [[ "$1" = *order-dscp.py ]]; then
    if [[ "${MOCK_DSCP_FAILURE:-0}" = 1 ]]; then echo 'client capability missing' >&2; return 1; fi
    echo 'DSCP=0'; return 0
  fi
  command python3 "$@"
}
bash(){
  if [[ "$1" = *prepare-posix-qos.sh ]]; then
    [[ "${3:-}" = --check ]] || { echo 'must not install in Chapter 05' >&2; return 90; }
    if [[ "${MOCK_INSTALL_FAILURE:-0}" = 1 ]]; then echo 'package digest mismatch' >&2; return 1; fi
    echo 'client package installed'; return 0
  fi
  if [[ "$1" = *transport_labctl.sh ]]; then
    if [[ "${MOCK_START_FAILURE:-0}" = 1 && "$2" = start ]]; then
      echo 'TRANSPORT_START_FAILED stage=configure_exchange_rss rc=1'
      return 1
    fi
    echo 'transport_labctl mocked'
    return 0
  fi
  command bash "$@"
}
"""


def main():
    """核对成功打印的分组说明和失败时不会出 READY。"""
    with tempfile.TemporaryDirectory(prefix="flle-lab-ready-test-") as temporary:
        work = Path(temporary)
        state = work / "reports/run-state"
        state.mkdir(parents=True)
        (state / "02-trading-baseline.env").write_text(
            f"RUN_ID={RUN_ID}\nRUN_DIR=/var/tmp/flle-trading-lab-{RUN_ID}\n"
        )
        mocks = work / "mocks.sh"
        mocks.write_text(MOCKS)
        script = work / "check.sh"
        script.write_text(
            SCRIPT.read_text().replace(
                "cd /qyt-fll", "cd " + shlex.quote(str(work)), 1
            )
        )
        env = dict(os.environ, BASH_ENV=str(mocks))
        run = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
        reports = list((work / "reports/course-runs" / RUN_ID / "profile-switches").iterdir())
        assert len(reports) == 1
        output = (reports[0] / "raw/result.txt").read_text()
        assert output == run.stdout
        assert output.startswith("准备 B：停掉普通客户端，换上测试客户端\n")
        assert "# 本步只换客户端，不下单。Exchange 和网页保持原进程。\n" in output
        assert f"platform_run={RUN_ID}\n" in output
        assert "# 第 02 章已经部署的交易平台，不另起一套系统。\n" in output
        assert "result=READY\n" in output
        assert "# 前三路测试客户端已就绪。\n" in output
        assert "profile=TRANSPORT\n" in output
        assert "# 已停掉普通 AUTO / MANUAL，换上路径测试客户端。\n" in output
        assert "clients=Kernel Socket, Onload, TCPDirect ONLINE; DPDK WAITING\n" in output
        assert "# 前三路在线；DPDK 等运行 ④ 再独占网卡。\n" in output
        assert "queue_mode=DEQUE_CV\n" in output
        assert "# 四路都用第 04 章的 deque + 互斥锁 + 条件变量。\n" in output
        assert "exchange_and_gui=UNCHANGED\n" in output
        assert "# 进程身份和文件清单与切换前一致。\n" in output
        assert "# 可以进入运行 ① 下单。\n" in output
        assert "===== 固定路径测试配置 =====" not in output
        failed = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True,
            env=dict(env, MOCK_IDENTITY_DRIFT="1"), timeout=10,
        )
        assert failed.returncode != 0
        assert "Exchange 进程身份已变化" in failed.stderr
        assert "result=READY" not in failed.stdout
        failed = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True,
            env=dict(env, MOCK_START_FAILURE="1"), timeout=10,
        )
        assert failed.returncode == 1
        assert "阶段：切换到路径测试客户端；退出码：1" in failed.stderr
        assert "TRANSPORT_START_FAILED stage=configure_exchange_rss rc=1" in failed.stderr
        assert "[完整记录]" in failed.stderr
        assert "result=READY" not in failed.stdout
        for flag, message in [('MOCK_INSTALL_FAILURE','核对第二章准备的测试客户端'),
                              ('MOCK_DSCP_FAILURE','核对客户端默认打标')]:
            failed = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                    env=dict(env, **{flag:"1"}), timeout=10)
            assert failed.returncode != 0 and message in failed.stderr
            assert "result=READY" not in failed.stdout
        assert "order_dscp=0" in output
        print("PASS lab-ready report, package/DSCP gates and identity-drift rejection")


if __name__ == "__main__":
    print("~~~~~~~~~~~~~~~~~~~~~准备 B 输出格式~~~~~~~~~~~~~~~~~~~~~")
    main()
