#!/usr/bin/env python3
"""Keep A/B source memberships alive for exactly the tcpdump process lifetime."""
import argparse
import os
import socket


GROUPS = ("233.74.125.32", "233.74.125.33")
SOURCE = "20.1.1.1"


def join_market(interface_ip):
    membership = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for group in GROUPS:
            request = b"".join(socket.inet_aton(ip) for ip in (group, interface_ip, SOURCE))
            membership.setsockopt(socket.IPPROTO_IP,
                                  getattr(socket, "IP_ADD_SOURCE_MEMBERSHIP", 39), request)
        # exec keeps this socket open; tcpdump exit (including SIGKILL) releases
        # only these memberships. There is no separate background join process.
        os.set_inheritable(membership.fileno(), True)
        return membership
    except BaseException:
        membership.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("source_port", type=int)
    args = parser.parse_args()
    if not 1 <= args.source_port <= 65535:
        parser.error("invalid market source port")
    membership = join_market("20.1.1.2")
    print("[行情订阅] 临时加入 A / B 两组，只接收 20.1.1.1；抓包退出后自动释放。", flush=True)
    try:
        os.execv("/usr/bin/tcpdump", [
            "tcpdump", "-i", "ens64np1", "-nn", "-j", "adapter_unsynced",
            "--time-stamp-precision=nano", "-s", "0", "-w", args.output,
            f"udp and src host {SOURCE} and src port {args.source_port}",
        ])
    finally:
        membership.close()


if __name__ == "__main__":
    main()
