import socket
import sys
import time

# ~~~~~.2 用 onload 发 52 字节，收 ACK，再停 5 秒~~~~~
s = socket.socket()
s.connect(("20.1.1.1", int(sys.argv[1])))
s.sendall(bytes(52))
reply = s.recv(3)
time.sleep(5)
print("client_bytes=52")
print("client_reply=%s" % reply.decode())
