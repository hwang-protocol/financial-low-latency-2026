import socket
import threading

# ~~~~~本机 loopback：一边听 52 字节，一边回 ACK~~~~~
def server(listener):
    connection, address = listener.accept()
    data = connection.recv(52)
    connection.sendall(b"ACK")
    print("server_bytes=%d" % len(data))

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(1)
thread = threading.Thread(target=server, args=(listener,))
thread.start()
client = socket.socket()
client.connect(listener.getsockname())
client.sendall(bytes(52))
print("client_reply=%s" % client.recv(3).decode())
thread.join()
