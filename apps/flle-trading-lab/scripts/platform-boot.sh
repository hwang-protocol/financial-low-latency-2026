#!/usr/bin/env bash
# Sourced by transport_labctl.sh on .2. Persistent activation, per-RUN recovery.
platform_boot_enable() {
  test "$CONTROL_LOCAL" = 1
  test -s "$CONTROL_DIR/experiment-profile"
  grep -Exq 'SOFTWARE|TRANSPORT' "$CONTROL_DIR/experiment-profile"
  install -d -m 755 /var/lib/flle /usr/local/libexec
  cat >/usr/local/libexec/flle-platform-boot.tmp <<'BOOT'
#!/usr/bin/env bash
set -Eeuo pipefail
IFS= read -r run </var/lib/flle/active-platform
[[ "$run" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || exit 2
exec /bin/bash "/var/tmp/flle-trading-lab-$run/control/apps/flle-trading-lab/scripts/transport_labctl.sh" boot "$run"
BOOT
  chmod 755 /usr/local/libexec/flle-platform-boot.tmp
  mv -f /usr/local/libexec/flle-platform-boot.tmp /usr/local/libexec/flle-platform-boot
  cat >/etc/systemd/system/flle-platform-boot.service <<'UNIT'
[Unit]
Description=Restore the deployed FLLE trading platform after boot
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/libexec/flle-platform-boot
Restart=on-failure
RestartSec=15s
TimeoutStartSec=15min
TimeoutStopSec=30s

[Install]
WantedBy=multi-user.target
UNIT
  printf '%s\n' "$RUN_ID" >/var/lib/flle/active-platform.tmp
  mv -f /var/lib/flle/active-platform.tmp /var/lib/flle/active-platform
  systemctl daemon-reload
  systemctl enable flle-platform-boot.service
  systemctl is-enabled --quiet flle-platform-boot.service
  printf 'platform_autostart=ENABLED host=10.1.1.2 run_id=%s retry_seconds=15\n' "$RUN_ID"
}

platform_boot_disable() {
  # Retiring one RUN must never disable a different platform's boot activation.
  if test -f /var/lib/flle/active-platform &&
      test "$(cat /var/lib/flle/active-platform)" = "$RUN_ID"; then
    systemctl disable flle-platform-boot.service
    rm -- /var/lib/flle/active-platform
    echo 'platform_autostart=DISABLED'
  fi
}

platform_boot_restore() {
  test "$CONTROL_LOCAL" = 1
  test "$(cat /var/lib/flle/active-platform)" = "$RUN_ID"
  local profile host
  IFS= read -r profile <"$CONTROL_DIR/experiment-profile"
  case "$profile" in SOFTWARE|TRANSPORT) ;; *) echo 'invalid saved platform profile' >&2; return 2;; esac
  # Fail before touching live processes if a peer has not finished booting.
  # systemd retries the entire attempt; there is no fixed VM boot-order timeout.
  for host in "$EXCHANGE_HOST" "$OBSERVER_HOST"; do
    "${SSH[@]}" "$host" "test -d '$RUN_DIR' && test -r /proc/sys/kernel/random/boot_id" || return 1
  done
  "${SSH[@]}" "$EXCHANGE_HOST" "ip -4 -o addr show dev ens64np0 | grep -Fq ' 20.1.1.1/24 '" || return 1
  ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 ' || return 1
  local checker="$SCRIPT_DIR/verify-book-handoff.py"
  # Installing/starting the unit on an already healthy platform preserves it.
  if verify_controller_identity >/dev/null 2>&1 &&
      verify_gateway_identity >/dev/null 2>&1 &&
      python3 "$checker" http://10.1.1.101:8088 --profile "$profile" --timeout 3 >/dev/null 2>&1; then
    echo "platform_boot=ALREADY_READY profile=$profile"
    return 0
  fi
  case "$profile" in
    SOFTWARE)
      platform_start_software
      # A peer may have started replay before this VM joined it.
      # Preserve the software profile's strategy setting while rebuilding books.
      if ! python3 "$checker" http://10.1.1.101:8088 --profile SOFTWARE --timeout 3 >/dev/null 2>&1; then
        restart_exchange_replay
      fi
      ;;
    TRANSPORT) "$0" start "$RUN_ID" ;;
  esac
  python3 "$checker" http://10.1.1.101:8088 --profile "$profile" --timeout 30
  printf 'platform_boot=READY profile=%s run_id=%s\n' "$profile" "$RUN_ID"
}
