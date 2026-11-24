"""Transient requests carried by the documented EOSSDK agent RPC interface.

No request is written to running-config or replayed after a daemon restart.
"""
import json
import time
import uuid


class FilterRpc:
    def __init__(self, controller, clock=time.monotonic):
        self.controller, self.clock = controller, clock
        self.session = uuid.uuid4().hex
        self.completed = {}

    def handle(self, command):
        try:
            request = json.loads(command)
            now = self.clock()
            if request["session"] != self.session:
                raise RuntimeError("Application restarted; discard this request")
            if request["deadline"] <= now or request["deadline"] > now + 10:
                raise RuntimeError("Request expired or has an invalid deadline")
            self.completed = {key: item for key, item in self.completed.items() if item[0] > now}
            request_id = request["id"]
            if request_id in self.completed:
                return self.completed[request_id][1]  # Return previous reply; do not write again.
            if len(self.completed) >= 256:
                raise RuntimeError("Too many pending request records")
            try:
                reply = {"ok": True, "result": self.controller.execute(request["operation"])}
            except Exception as error:
                reply = {"ok": False, "error": str(error)}
            encoded = json.dumps(reply)
            self.completed[request_id] = (request["deadline"], encoded)
            return encoded
        except Exception as error:
            return json.dumps({"ok": False, "error": str(error)})
