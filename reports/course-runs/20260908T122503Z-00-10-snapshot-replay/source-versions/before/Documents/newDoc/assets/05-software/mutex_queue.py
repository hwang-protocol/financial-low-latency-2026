import threading
class MutexQueue:
    def __init__(self):
        self.items = []
        self.ready = threading.Condition()
        self.protected_operations = 0
    def push(self, value):
        with self.ready:
            self.items.append(value)
            self.protected_operations += 1
            self.ready.notify()
    def pop(self):
        with self.ready:
            while not self.items:
                self.ready.wait()
            self.protected_operations += 1
            return self.items.pop(0)
work = MutexQueue()
received = []
def producer():
    for sequence in range(10): work.push(sequence)
def consumer():
    for unused in range(10): received.append(work.pop())
p = threading.Thread(target=producer); c = threading.Thread(target=consumer)
c.start(); p.start(); p.join(); c.join()
print("received=%s protected_operations=%d" %
      (received, work.protected_operations))
