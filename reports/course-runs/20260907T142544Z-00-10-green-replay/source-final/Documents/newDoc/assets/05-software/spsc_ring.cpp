#include <atomic>
#include <iostream>
#include <thread>
struct Ring {
  int slots[16]{}; std::atomic<int> head{0}, tail{0};
  bool push(int value) {
    int h=head.load(); int next=(h+1)%16;
    if (next==tail.load(std::memory_order_acquire)) return false;
    slots[h]=value; head.store(next,std::memory_order_release); return true;
  }
  bool pop(int& value) {
    int t=tail.load();
    if (t==head.load(std::memory_order_acquire)) return false;
    value=slots[t]; tail.store((t+1)%16,std::memory_order_release); return true;
  }
};
int main() {
  Ring ring; int output[10]{};
  std::thread producer([&]{for(int i=0;i<10;) if(ring.push(i)) ++i;});
  std::thread consumer([&]{for(int i=0;i<10;) if(ring.pop(output[i])) ++i;});
  producer.join(); consumer.join();
  std::cout << "received=";
  for(int i=0;i<10;++i) std::cout << (i ? "," : "") << output[i];
  std::cout << "\nfinal_head=" << ring.head.load()
            << " final_tail=" << ring.tail.load() << "\n";
}
