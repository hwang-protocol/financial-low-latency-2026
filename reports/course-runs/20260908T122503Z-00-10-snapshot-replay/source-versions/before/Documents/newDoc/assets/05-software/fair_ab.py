import os
import time
def work():
    start = time.monotonic_ns()
    checksum = 0
    for sequence in range(100000):
        checksum += sequence
    return checksum, time.monotonic_ns() - start
original = os.sched_getaffinity(0)
first_checksum, first_ns = work()
candidate = min(original)
os.sched_setaffinity(0, {candidate})
second_checksum, second_ns = work()
os.sched_setaffinity(0, original)
print("input_count=100000 binary=python_work_v1")
print("original_affinity_ns=%d pinned_ns=%d cpu=%d" %
      (first_ns, second_ns, candidate))
print("checksums=%d,%d" % (first_checksum, second_checksum))
