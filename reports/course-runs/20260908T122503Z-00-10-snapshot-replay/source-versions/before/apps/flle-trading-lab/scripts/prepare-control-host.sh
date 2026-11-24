#!/usr/bin/env bash
# Deploy a Trader-owned management identity; private material stays on .2.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
KNOWN="$ROOT/Documents/newDoc/assets/common/ssh_known_hosts"
TMP="$(mktemp -d)"
trap 'rm -f "$TMP/public" "$TMP/known"; rmdir "$TMP"' EXIT
for host in 10.1.1.1 10.1.1.101 10.1.1.11; do
  ssh-keygen -F "$host" -f "$KNOWN" | sed '/^#/d' >>"$TMP/known"
done
test -s "$TMP/known"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  'set -eu; install -d -m 700 /root/.ssh; if test ! -f /root/.ssh/id_ed25519; then ssh-keygen -q -t ed25519 -N "" -C flle-trader-control -f /root/.ssh/id_ed25519; fi; cat /root/.ssh/id_ed25519.pub' >"$TMP/public"
scp -q "$TMP/known" root@10.1.1.2:/root/.ssh/flle-peer-hosts
ssh -o BatchMode=yes root@10.1.1.2 \
  'set -eu; touch /root/.ssh/known_hosts; cat /root/.ssh/flle-peer-hosts >>/root/.ssh/known_hosts; sort -u /root/.ssh/known_hosts -o /root/.ssh/known_hosts; chmod 600 /root/.ssh/known_hosts'
for host in 10.1.1.1 10.1.1.101 10.1.1.11; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    'set -eu; IFS= read -r key; test -n "$key"; install -d -m 700 /root/.ssh; touch /root/.ssh/authorized_keys; if ! grep -Fq "$key" /root/.ssh/authorized_keys; then printf '\''from="10.1.1.2",no-agent-forwarding,no-port-forwarding,no-X11-forwarding %s\n'\'' "$key" >>/root/.ssh/authorized_keys; fi; chmod 600 /root/.ssh/authorized_keys' <"$TMP/public"
done
ssh -o BatchMode=yes root@10.1.1.2 \
  'for host in 10.1.1.1 10.1.1.101 10.1.1.11; do ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 root@$host hostname; done'
