#include <iostream>
struct Tick { int sequence; };
static int allocation_calls = 0;
static int deallocation_calls = 0;
__attribute__((noinline)) Tick* allocate_tick(int sequence) {
  ++allocation_calls;
  return new Tick{sequence};
}
__attribute__((noinline)) void release_tick(Tick* tick) {
  ++deallocation_calls;
  delete tick;
}
int main() {
  int checksum = 0;
  for (int sequence = 0; sequence < 10; ++sequence) {
    Tick* tick = allocate_tick(sequence);
    checksum += tick->sequence;
    release_tick(tick);
  }
  std::cout << "messages=10 allocation_calls=" << allocation_calls
            << " deallocation_calls=" << deallocation_calls
            << " checksum=" << checksum << "\n";
}
