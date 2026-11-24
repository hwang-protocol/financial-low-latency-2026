#!/usr/bin/env python3
"""Display original VLAN20 rows; default strict checks serve automated preflight."""
import argparse
from pathlib import Path
import re


def inspect(text, members=False, check=True, configuration=False, ab=False):
    groups = ("233.74.125.32", "233.74.125.33") if ab else ("233.74.125.32",)
    def require(condition, message):
        if not condition and check:
            raise ValueError(message)
    sections = {}
    for command, body in re.findall(r"^\$ ([^\n]+)\n(.*?)(?=^\$ |\Z)", text, re.M | re.S):
        sections[command] = body
    if configuration:
        descriptions = {
            "configure terminal": ("第 1 条命令：进入配置模式", "后续 IGMP 设置在交换机的全局配置模式中执行。"),
            "ip igmp snooping": ("第 2 条命令：开启全局组播侦听", "启用交换机全局的 IGMP 侦听功能。"),
            "ip igmp snooping vlan 20": ("第 3 条命令：启用 VLAN20 组播侦听", "让 VLAN20 从主机报告中学习组地址与接收端口的关系。"),
            "ip igmp snooping vlan 20 querier address 20.1.1.254": ("第 4 条命令：设置查询报文源地址", "20.1.1.254 是查询报文的源 IP；行情组播目的地址为 " + " 与 ".join(groups) + "。"),
            "ip igmp snooping vlan 20 querier": ("第 5 条命令：启用 VLAN20 查询器", "定期询问哪些主机仍要接收组播，维持成员关系。"),
            "end": ("第 6 条命令：返回特权执行模式", "退出配置模式，随后用 show 命令查看实际状态。"),
        }
        print("10.1.1.253 / configure")
        for command, body in sections.items():
            if command not in descriptions:
                continue
            title, purpose = descriptions[command]
            print(f"===== {title} =====\n{purpose}\n$ {command}")
            # The transcript retains the CLI echo; display the command only once.
            rows = body.strip("\n").splitlines()
            if rows and rows[0] == command:
                rows = rows[1:]
            if rows:
                print("\n".join(rows))
    body = sections.get("show ip igmp snooping", "")
    match = re.search(r"^Vlan 20\s*:\s*\n(.*?)(?=^Vlan \d+\s*:|\Z)", body, re.M | re.S)
    require(match is not None, "没有找到 VLAN20 的 Snooping 状态")
    vlan = match[1] if match else ""
    print("10.1.1.253 / verify")
    print("===== 第 7 条命令：查 VLAN20 的组播转发方式 =====" if configuration else "===== 查 VLAN20 的组播转发方式 =====")
    print("[转发] 对: Enabled、pruning True、Flooding False  证: 按成员端口转发")
    print("$ show ip igmp snooping")
    print(match[0].splitlines()[0] if match else "（未找到 VLAN20 状态段）")
    for field, expected in (("IGMP snooping", "Enabled"), ("IGMP snooping pruning active", "True"), ("Flooding traffic to VLAN", "False")):
        row = re.search(r"^" + re.escape(field) + r"[ \t]*:[ \t]*(\S+)[ \t]*$", vlan, re.M)
        print(row[0] if row else "（未找到字段：" + field + "）")
        require(row is not None, "VLAN20 缺少字段: " + field)
        require(row is not None and row[1] == expected, field + " 应为 " + expected)
    print("===== 第 8 条命令：查谁发成员查询 =====" if configuration else "===== 查谁发成员查询 =====")
    print("[查询器] 对: VLAN20 / 20.1.1.254 / Switch  证: 交换机持续询问成员")
    print("$ show igmp snooping querier")
    rows = [line for line in sections.get("show igmp snooping querier", "").splitlines() if re.match(r"^20\s", line)]
    for line in rows:
        print(line)
    if not rows:
        print("（未找到 VLAN20 查询器）")
    require(any(len(row.split()) >= 4 and row.split()[1] == "20.1.1.254" and row.split()[-1] == "Switch" for row in rows), "VLAN20 查询器未就绪")
    if configuration:
        print("===== 第 9 条命令：查当前组播成员表 =====")
        print("按 VLAN、Group、Port-List 读出组与端口；平台尚未启动时，目标行情组可能没有成员。")
        print("$ show ip igmp snooping groups")
        body = sections.get("show ip igmp snooping groups")
        print(body.rstrip("\n") if body is not None else "（未找到组播成员表回执）")
        missing = [group for group in groups if body is not None and not re.search(r"^20\s+" + re.escape(group) + r"\s", body, re.M)]
        if missing:
            print("[成员说明] 当前回执未见 VLAN20 的 " + " 与 ".join(missing) + " 成员；平台启动并成功加组后，在运行 ①B 核对动态成员 Et2。")
    if members:
        print("===== 查行情组的成员端口 =====\n[成员] 对: VLAN20 / " + " 与 ".join(groups) + " / Dynamic / Et2  证: 接收者在 Trader 数据口")
        print("$ show ip igmp snooping groups")
        for group in groups:
            rows = [line for line in sections.get("show ip igmp snooping groups", "").splitlines() if re.match(r"^20\s+" + re.escape(group) + r"\s", line)]
            for line in rows:
                print(line)
            if not rows:
                print("（未找到 VLAN20 的 " + group + " 成员）")
            require(len(rows) == 1 and len(rows[0].split()) >= 5 and rows[0].split()[2] == "Dynamic" and rows[0].split()[4:] == ["Et2"], group + " 应只有动态成员端口 Et2")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--members", action="store_true")
    parser.add_argument("--ab", action="store_true", help="查看 A/B 两个行情组；默认只查 A 路")
    parser.add_argument("--configuration", action="store_true", help="按准备 C 顺序说明配置命令并显示成员表原文")
    parser.add_argument("--display", action="store_true", help="只展示观察值，由学员判断，不判定技术结论")
    args = parser.parse_args()
    try:
        inspect(Path(args.path).read_text(), args.members, check=not args.display, configuration=args.configuration, ab=args.ab)
    except ValueError as exc:
        raise SystemExit("IGMP 检查未通过: " + str(exc)) from exc
