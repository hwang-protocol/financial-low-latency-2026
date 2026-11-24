"""Course control logic. Tested locally; not validated on EOS or FPGA hardware.

The board adapter must provide coherent register readback and write-one pulses.
Only the daemon owns this controller, so commands are serialized, not persisted.
"""
import time

APP_ID = 0x464C4C45
COMMAND_ADDRESS = 1  # Word index, matching flle_filter_registers.csv.


class FilterControl:
    def __init__(self, fpga, register_factory, csv_path, clock=time.monotonic):
        if fpga.board_standard != "bvl" or fpga.image_type != "pdi":
            raise RuntimeError("This application requires a BVL / PDI FPGA")
        self.fpga, self.register_factory, self.csv_path = fpga, register_factory, csv_path
        self.clock, self.regs = clock, None
        self.ready, self.loading, self.owns_image = False, False, False

    def start(self, image, port_def, timeout=120):
        if not image.endswith(".pdi") or not port_def:
            raise ValueError("Provide the built PDI and its real FDK port definition")
        self.ready, self.loading, self.regs = False, False, None
        self.deadline = self.clock() + timeout
        # Return to EOSSDK's event loop while the hardware is being configured.
        self.fpga.load_image(image, blocking=False, port_def=port_def)
        self.owns_image = True
        self.loading = True

    def poll(self):
        if not self.loading:
            return
        state = self.fpga.profile_state()
        if state == "applied":
            self.regs = self.register_factory(self.csv_path, self.fpga.communicator)
            self._check_id()
            self._write_once(2)  # Every start begins disarmed, never auto-arms.
            self.ready, self.loading = True, False
        elif self.clock() >= self.deadline:
            raise RuntimeError("FPGA configuration failed or timed out: {}".format(state))

    def _check_id(self):
        if self.regs.read_reg("app_id") != APP_ID:
            self.ready = False
            raise RuntimeError("Unexpected FPGA application ID; refusing register writes")

    def _require_ready(self):
        if not self.ready or self.fpga.profile_state() != "applied":
            raise RuntimeError("FPGA is not ready")
        self._check_id()

    def _write_once(self, value):
        # RegisterFile.write_reg retries exceptions. A retry of ARM could create
        # another quota after a dropped frame, so use one communicator call.
        try:
            self.fpga.communicator.write_reg(COMMAND_ADDRESS, value)
        except Exception:
            self.ready = False
            raise RuntimeError("Write outcome unknown; no retry sent. Restore external bypass, then disabled / no disabled")

    def execute(self, operation):
        self._require_ready()
        if operation == "arm-once":
            if self.regs.read_reg("status") & 1:
                raise RuntimeError("One drop quota is already armed")
            self._write_once(1)
            return {"command": "arm-once", "write_returned": True}
        if operation == "disarm":
            self._write_once(2)
            return {"command": "disarm", "write_returned": True}
        if operation != "show":
            raise ValueError("Expected arm-once, disarm or show")
        result = {name: self.regs.read_reg(name) for name in
                  ("app_id", "status", "rx_count", "tx_count", "drop_count", "error_count")}
        # Counts are live samples, not an atomic snapshot. Publish the sequence
        # only while disarmed, with an unchanged drop counter bracketing the read.
        before = self.regs.read_reg("drop_count")
        armed_before = self.regs.read_reg("status") & 1
        high = self.regs.read_reg("last_sequence_hi")
        low = self.regs.read_reg("last_sequence_lo")
        armed_after = self.regs.read_reg("status") & 1
        after = self.regs.read_reg("drop_count")
        stable = not (armed_before or armed_after) and before == after
        result["last_sequence"] = (high << 32) | low if stable else None
        result["sequence_stable"] = stable
        return result

    def stop(self):
        self.ready, self.loading = False, False
        if not self.owns_image:
            return
        try:
            if self.regs is not None and self.fpga.profile_state() == "applied":
                self._check_id()
                self._write_once(2)
        finally:
            self.fpga.unload_image()
            self.regs = None
            self.owns_image = False
