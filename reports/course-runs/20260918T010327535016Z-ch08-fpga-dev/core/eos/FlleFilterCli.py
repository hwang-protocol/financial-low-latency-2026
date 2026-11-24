# Adapted: Copyright (c) 2023 Arista Networks, Inc. All rights reserved.
# BSD-3-Clause; see ../LICENSE-Arista-BSD-3-Clause.txt. Not tested on EOS.
import CliExtension
import json
import time
import uuid
from flle_filter import libapp


class ShowStatus(libapp.cli.ShowEnabledBaseCmd):
    daemon = "FlleFilterDaemon"

    def handler(self, ctx):
        result = super().handler(ctx)
        daemon = ctx.getDaemon(self.daemon)
        result["detail"] = libapp.cli.status_as_dict(daemon.status) if daemon else {}
        return result

    def render(self, data):
        super().render(data)
        for name, value in data["detail"].items():
            print("{}: {}".format(name, value))


class Disabled(CliExtension.CliCommandClass):
    def handler(self, ctx):
        ctx.daemon.config.disable()

    def noHandler(self, ctx):
        ctx.daemon.config.enable()

    defaultHandler = handler


def request(ctx, operation):
    daemon = ctx.getDaemon("FlleFilterDaemon")
    if daemon is None or not daemon.config.isEnabled():
        raise RuntimeError("Enable flle_filter first")
    status = libapp.cli.StatusAccessor(daemon.status)
    if not status.get("running", False):
        raise RuntimeError("FPGA is not ready")
    command = json.dumps({"operation": operation, "id": uuid.uuid4().hex,
                          "session": status["session"], "deadline": time.monotonic() + 5})
    try:
        # Official EOS SDK API; exactly one call, with no automatic retry here.
        reply = json.loads(CliExtension.agentRpc(ctx, "FlleFilterDaemon", command))
    except Exception as error:
        raise RuntimeError("Command outcome unknown; no retry sent. Check show flle_filter status, restore external bypass, then disabled / no disabled") from error
    if not reply["ok"]:
        raise RuntimeError(reply["error"])
    return reply["result"]


class ArmOnce(CliExtension.CliCommandClass):
    def handler(self, ctx):
        print(json.dumps(request(ctx, "arm-once")))


class Disarm(CliExtension.CliCommandClass):
    def handler(self, ctx):
        print(json.dumps(request(ctx, "disarm")))


class ShowCounters(CliExtension.ShowCommandClass):
    def handler(self, ctx):
        return request(ctx, "show")

    def render(self, data):
        for name, value in data.items():
            print("{}: {}".format(name, value))


def Plugin(ctx):
    CliExtension.registerCommand("disabled", Disabled, namespace="flle.filter")
    CliExtension.registerCommand("show_filter_status", ShowStatus, namespace="flle.filter")
    CliExtension.registerCommand("arm_once", ArmOnce, namespace="flle.filter")
    CliExtension.registerCommand("disarm", Disarm, namespace="flle.filter")
    CliExtension.registerCommand("show_filter_counters", ShowCounters, namespace="flle.filter")
