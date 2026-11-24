#include <iostream>
struct Tick { int sequence; };
static int dynamic_allocations = 0, dynamic_deallocations = 0;
static int pool_allocations = 0, pool_deallocations = 0;
__attribute__((noinline)) Tick* allocate_tick(int sequence) {
  ++dynamic_allocations; return new Tick{sequence};
}
__attribute__((noinline)) void release_tick(Tick* tick) {
  ++dynamic_deallocations; delete tick;
}
__attribute__((noinline)) Tick* allocate_pool(int count) {
  ++pool_allocations; return new Tick[count];
}
__attribute__((noinline)) void release_pool(Tick* pool) {
  ++pool_deallocations; delete[] pool;
}
int main() {
  int dynamic_sum = 0;
  for (int i = 0; i < 10; ++i) {
    Tick* tick = allocate_tick(i);
    dynamic_sum += tick->sequence;
    release_tick(tick);
  }
  Tick* slots = allocate_pool(10);
  int preallocated_sum = 0;
  for (int i = 0; i < 10; ++i) {
    slots[i].sequence = i; preallocated_sum += slots[i].sequence;
  }
  release_pool(slots);
  std::cout << "dynamic_allocation_calls=" << dynamic_allocations
            << " dynamic_deallocation_calls=" << dynamic_deallocations << "\n";
  std::cout << "pool_allocation_calls=" << pool_allocations
            << " pool_deallocation_calls=" << pool_deallocations << "\n";
  std::cout << "checksums=" << dynamic_sum << "," << preallocated_sum << "\n";
}
