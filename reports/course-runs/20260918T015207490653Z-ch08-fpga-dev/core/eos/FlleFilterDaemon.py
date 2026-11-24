#!/usr/bin/env arista-python
# Adapted: Copyright (c) 2023 Arista Networks, Inc. All rights reserved.
# BSD-3-Clause; see ../LICENSE-Arista-BSD-3-Clause.txt. Not tested on EOS.
import json
from pathlib import Path
import sys
import eossdk
from flle_filter import libapp
from flle_filter.eos.filter_control import FilterControl
from flle_filter.eos.filter_rpc import FilterRpc

APPDIR = Path("/opt/apps/flle_filter")


class FlleFilterDaemon(eossdk.AgentHandler, eossdk.TimeoutHandler, libapp.daemon.StatusMixin):
    def __init__(self, sdk):
        self.agent_manager = sdk.get_agent_mgr()
        eossdk.AgentHandler.__init__(self, self.agent_manager)
        eossdk.TimeoutHandler.__init__(self, sdk.get_timeout_mgr())
        self.controller = self.rpc = None

    def on_initialized(self):
        self.status.clear()
        self.status["running"] = False
        try:
            image = APPDIR / "fpga/flle_filter-bvl.pdi"
            ports = APPDIR / "fpga/flle_filter-bvl-ports.json"
            if not image.is_file() or not ports.is_file():
                raise RuntimeError("Missing built BVL PDI / its FDK port definition")
            targets = libapp.device.get_fpga_devices(board_standard="bvl", identifier="Fpga1")
            if len(targets) != 1:
                raise RuntimeError("Expected one BVL FPGA")
            self.controller = FilterControl(targets[0], libapp.register_file.RegisterFile,
                                            str(APPDIR / "fpga/flle_filter_registers.csv"))
            self.controller.start(str(image), json.loads(ports.read_text()))
            self.rpc = FilterRpc(self.controller)
            self.status["session"] = self.rpc.session
            self.on_timeout()
        except Exception as error:
            self.fail(error)

    def on_timeout(self):
        try:
            self.controller.poll()
            self.status["running"] = self.controller.ready
            self.status["image_state"] = self.controller.fpga.profile_state() or "loading"
        except Exception as error:
            self.fail(error)
            return
        self.timeout_time_is(eossdk.now() + 0.1)

    def fail(self, error):
        self.timeout_time_is(eossdk.never)
        self.status["running"] = False
        self.status["error"] = str(error)
        self.rpc = None
        if self.controller:
            try:
                self.controller.stop()
            except Exception as cleanup_error:
                self.status["cleanup_error"] = str(cleanup_error)

    def on_agent_enabled(self, enabled):
        if not enabled:
            # Restore the test bench's external bypass before disabling.
            self.fail("disabled")
            self.agent_manager.agent_shutdown_complete_is(True)

    def on_agent_rpc(self, command):
        if self.rpc is None:
            return json.dumps({"ok": False, "error": "Application is not ready"})
        return self.rpc.handle(command)


if __name__ == "__main__":
    sdk = eossdk.Sdk("FlleFilterDaemon")
    daemon = FlleFilterDaemon(sdk)
    sdk.main_loop(sys.argv)
