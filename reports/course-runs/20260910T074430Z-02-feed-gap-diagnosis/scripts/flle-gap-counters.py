import datetime
import hashlib
import json
import os
import pathlib
import struct
import time

pid = 21782
expected = 'ca172ec5300468d3cec02f769594d48ed7520beb9b820645674dd997084de404'
proc = pathlib.Path('/proc') / str(pid)
assert hashlib.sha256((proc / 'exe').read_bytes()).hexdigest() == expected
# For this exact ELF only: main stores pollfd[3] at rsp+0x90,
# received at rsp+0x30, delivered at rsp+0x10, slow_drops at rsp+0x28.
# Read only these counters while /proc reports poll(5,3,4); never attach,
# stop, signal, or write process memory. Verify the syscall before/after.
fd = os.open(proc / 'mem', os.O_RDONLY)
samples = []
try:
    for attempt in range(200):
        before = (proc / 'syscall').read_text().strip()
        fields = before.split()
        if len(fields) != 9 or fields[0] != '7' or int(fields[2], 0) != 3:
            time.sleep(0.01)
            continue
        address = int(fields[1], 0)
        pollfds = [struct.unpack('<ihh', os.pread(fd, 8, address + index * 8)) for index in range(3)]
        if [entry[0] for entry in pollfds] != [5, 3, 4]:
            raise RuntimeError('unexpected poll descriptors')
        values = {name: struct.unpack('<Q', os.pread(fd, 8, address + offset))[0]
                  for name, offset in [('received', -0x60), ('delivered', -0x80), ('slow_consumer_drops', -0x68)]}
        after = (proc / 'syscall').read_text().strip()
        if before != after:
            continue
        samples.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            syscall=before, pollfds=pollfds, **values))
        if len(samples) == 3:
            break
        time.sleep(0.1)
finally:
    os.close(fd)
assert len(samples) == 3
print(json.dumps(dict(pid=pid, binary_sha256=expected, method='read-only /proc/pid/mem; no ptrace or signals', samples=samples), indent=2))
