python3 - <<'PY'
import mmap
import os
import resource

page = os.sysconf("SC_PAGE_SIZE")
size = page * 128
buf = mmap.mmap(-1, size,
                flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE)
before = resource.getrusage(resource.RUSAGE_SELF).ru_minflt

for offset in range(0, size, page):
    buf[offset] = 1

after = resource.getrusage(resource.RUSAGE_SELF).ru_minflt
print("page_size=%d" % page)
print("touched_pages=%d" % (size // page))
print("minor_fault_delta=%d" % (after - before))
buf.close()
PY
