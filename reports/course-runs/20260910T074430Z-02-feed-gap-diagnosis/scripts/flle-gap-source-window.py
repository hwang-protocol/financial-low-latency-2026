import collections
import json
import mmap
import struct

path = '/var/tmp/flle-trading-lab-20260910T043800Z-02-trading-platform/AAPL_NVDA.itch'
target = 7641279
records = []
with open(path, 'rb') as source:
    with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        offset, sequence = 0, 0
        while offset < len(data):
            length = struct.unpack_from('!H', data, offset)[0]
            offset += 2
            if length >= 11:
                timestamp = int.from_bytes(data[offset + 5:offset + 11], 'big')
                if 34200000000000 <= timestamp < 57600000000000:
                    sequence += 1
                    if target - 3000 <= sequence <= target + 6000:
                        records.append({'sequence': sequence, 'timestamp_ns': timestamp,
                                        'type': chr(data[offset]), 'length': length})
            offset += length
            if sequence >= target + 6000:
                break
summary = {'source': path, 'target': next(row for row in records if row['sequence'] == target)}
times = [row['timestamp_ns'] for row in records]
for window_ns in [1000000, 10000000, 100000000]:
    start, maximum, bounds = 0, 0, None
    for end, timestamp in enumerate(times):
        while timestamp - times[start] >= window_ns:
            start += 1
        if end - start + 1 > maximum:
            maximum = end - start + 1
            bounds = [records[start]['sequence'], records[end]['sequence']]
    summary['max_messages_in_' + str(window_ns) + 'ns'] = {'count': maximum, 'sequence_bounds': bounds}
summary['neighbours'] = [row for row in records if abs(row['sequence'] - target) <= 3]
print(json.dumps({'summary': summary, 'records': records}, indent=2))
