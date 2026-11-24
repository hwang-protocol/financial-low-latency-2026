import queue
import threading
work = queue.Queue()
received = []
def producer():
    for sequence in range(10):
        work.put(sequence)
def consumer():
    for unused in range(10):
        received.append(work.get())
p = threading.Thread(target=producer)
c = threading.Thread(target=consumer)
p.start(); c.start(); p.join(); c.join()
print("received=" + ",".join(str(value) for value in received))
