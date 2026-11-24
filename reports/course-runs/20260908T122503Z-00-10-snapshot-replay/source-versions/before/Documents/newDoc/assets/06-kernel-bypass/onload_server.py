import socket
import sys
import time

# ~~~~~.1 用 onload 听 52 字节，回 ACK，再停 5 秒给 stackdump~~~~~
s = socket.socket()
s.bind(("20.1.1.1", int(sys.argv[1])))
s.listen()
c, address = s.accept()
data = c.recv(52)
c.sendall(b"ACK")
time.sleep(5)
print("server_bytes=%d" % len(data))
