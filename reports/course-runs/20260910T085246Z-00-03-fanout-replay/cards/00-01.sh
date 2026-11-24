python3 - <<'PY'
import mmap
import os
import resource

# A. 读取系统页大小，并申请 128 页可读写的匿名内存。
page = os.sysconf("SC_PAGE_SIZE")
size = page * 128
# -1 与 MAP_ANONYMOUS：申请不关联文件的内存。
# MAP_PRIVATE 使用私有映射；PROT_READ/PROT_WRITE 允许程序读写。
buf = mmap.mmap(-1, size,
                flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE)
# B. 记下本进程累计的次缺页次数，作为比较起点。
# 计数覆盖整个进程，也包含 Python 自身发生的次缺页。
before = resource.getrusage(resource.RUSAGE_SELF).ru_minflt

# C. 从第 1 页开始，每次跨过一页，共访问 128 页。
for offset in range(0, size, page):
    # 每页的第一个字节写入数值 1；首次写入会让内核准备这一页。
    buf[offset] = 1

# D. 逐页写完后，再读取一次累计次数。
after = resource.getrusage(resource.RUSAGE_SELF).ru_minflt
# E. 输出页大小、写过的页数和计数增量，随后释放内存映射。
print("page_size=%d" % page)
print("touched_pages=%d" % (size // page))
print("minor_fault_delta=%d" % (after - before))
buf.close()
PY
