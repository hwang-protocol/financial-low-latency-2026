#pragma once

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <immintrin.h>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>

namespace flle {

enum class OrderQueueMode { DequeCv, FixedCv, SpscSpin };

inline const char *order_queue_mode_name(OrderQueueMode mode) {
  switch (mode) {
    case OrderQueueMode::DequeCv: return "DEQUE_CV";
    case OrderQueueMode::FixedCv: return "FIXED_CV";
    case OrderQueueMode::SpscSpin: return "SPSC_SPIN";
  }
  return "UNKNOWN";
}

inline OrderQueueMode parse_order_queue_mode(const std::string &value) {
  if (value == "DEQUE_CV") return OrderQueueMode::DequeCv;
  if (value == "FIXED_CV") return OrderQueueMode::FixedCv;
  if (value == "SPSC_SPIN") return OrderQueueMode::SpscSpin;
  throw std::runtime_error("order queue must be DEQUE_CV, FIXED_CV or SPSC_SPIN");
}

template <typename T, std::size_t Slots>
class OrderQueue {
  static_assert(Slots >= 4, "order queue needs at least four slots");

 public:
  explicit OrderQueue(OrderQueueMode mode = OrderQueueMode::DequeCv) : mode_(mode) {}

  OrderQueueMode mode() const { return mode_.load(std::memory_order_acquire); }
  const char *mode_name() const { return order_queue_mode_name(mode()); }
  static constexpr std::size_t capacity() { return Slots - 1; }

  bool set_mode(OrderQueueMode next) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!deque_.empty() || fixed_size_ || spsc_depth()) return false;
    mode_.store(next, std::memory_order_release);
    condition_.notify_all();
    return true;
  }

  bool push(T value) {
    const auto selected = mode();
    if (selected == OrderQueueMode::DequeCv) {
      std::lock_guard<std::mutex> lock(mutex_);
      deque_.push_back(std::move(value));
      condition_.notify_one();
      return true;
    }
    if (selected == OrderQueueMode::FixedCv) {
      std::lock_guard<std::mutex> lock(mutex_);
      if (fixed_size_ == capacity()) return false;
      slots_[fixed_head_] = std::move(value);
      fixed_head_ = (fixed_head_ + 1) % Slots;
      ++fixed_size_;
      condition_.notify_one();
      return true;
    }
    const auto head = spsc_head_.load(std::memory_order_relaxed);
    const auto next = (head + 1) % Slots;
    if (next == spsc_tail_.load(std::memory_order_acquire)) return false;
    slots_[head] = std::move(value);
    spsc_head_.store(next, std::memory_order_release);
    return true;
  }

  bool front(T &value, const std::atomic<bool> &stop) {
    const auto selected = mode();
    if (selected == OrderQueueMode::SpscSpin) {
      const auto tail = spsc_tail_.load(std::memory_order_relaxed);
      if (tail == spsc_head_.load(std::memory_order_acquire)) {
        // This consumer owns a dedicated vCPU in the SPSC profile.  PAUSE
        // keeps it runnable without surrendering the vCPU to the scheduler;
        // yield() would turn this mode back into a scheduler-wakeup test.
        for (int count = 0; count < 64 && !stop.load(std::memory_order_relaxed);
             ++count)
          _mm_pause();
        return false;
      }
      value = slots_[tail];
      return true;
    }
    std::unique_lock<std::mutex> lock(mutex_);
    condition_.wait_for(lock, std::chrono::milliseconds(20), [&] {
      return stop.load() || mode() != selected ||
             (selected == OrderQueueMode::DequeCv ? !deque_.empty() : fixed_size_ != 0);
    });
    if (stop.load() || mode() != selected) return false;
    if (selected == OrderQueueMode::DequeCv) {
      if (deque_.empty()) return false;
      value = deque_.front();
      return true;
    }
    if (!fixed_size_) return false;
    value = slots_[fixed_tail_];
    return true;
  }

  void pop() {
    const auto selected = mode();
    if (selected == OrderQueueMode::SpscSpin) {
      const auto tail = spsc_tail_.load(std::memory_order_relaxed);
      spsc_tail_.store((tail + 1) % Slots, std::memory_order_release);
      return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    if (selected == OrderQueueMode::DequeCv) {
      if (!deque_.empty()) deque_.pop_front();
      return;
    }
    if (fixed_size_) {
      fixed_tail_ = (fixed_tail_ + 1) % Slots;
      --fixed_size_;
    }
  }

  std::size_t depth() const {
    const auto selected = mode();
    if (selected == OrderQueueMode::SpscSpin) return spsc_depth();
    std::lock_guard<std::mutex> lock(mutex_);
    return selected == OrderQueueMode::DequeCv ? deque_.size() : fixed_size_;
  }

  void wake() { condition_.notify_all(); }

 private:
  std::size_t spsc_depth() const {
    const auto head = spsc_head_.load(std::memory_order_acquire);
    const auto tail = spsc_tail_.load(std::memory_order_acquire);
    return head >= tail ? head - tail : Slots - tail + head;
  }

  std::atomic<OrderQueueMode> mode_;
  mutable std::mutex mutex_;
  std::condition_variable condition_;
  std::deque<T> deque_;
  // Allocate every queue slot once on the cold path.  FIXED_CV and SPSC never
  // allocate queue storage per order, and mode changes are allowed only empty.
  std::unique_ptr<T[]> slots_{new T[Slots]};
  std::size_t fixed_head_{};
  std::size_t fixed_tail_{};
  std::size_t fixed_size_{};
  alignas(64) std::atomic<std::size_t> spsc_head_{0};
  alignas(64) std::atomic<std::size_t> spsc_tail_{0};
};

}  // namespace flle
