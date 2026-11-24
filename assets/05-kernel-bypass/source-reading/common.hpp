#pragma once

#include <arpa/inet.h>
#include <endian.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sched.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace flle {

constexpr std::size_t kDepth = 5;

inline void pin_current_thread(int cpu) {
  if (cpu < 0) return;
  cpu_set_t affinity;
  CPU_ZERO(&affinity);
  CPU_SET(cpu, &affinity);
  if (::sched_setaffinity(0, sizeof(affinity), &affinity) != 0)
    throw std::runtime_error("sched_setaffinity CPU " +
                             std::to_string(cpu) + ": " +
                             std::string(std::strerror(errno)));
}

inline int affinity_count(int tid) {
  if (tid <= 0) return 0;
  cpu_set_t affinity;
  CPU_ZERO(&affinity);
  return ::sched_getaffinity(tid, sizeof(affinity), &affinity) == 0
             ? CPU_COUNT(&affinity)
             : 0;
}

inline std::uint64_t monotonic_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch()).count();
}

inline std::uint64_t realtime_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::system_clock::now().time_since_epoch()).count();
}

inline std::optional<std::uint32_t> allocate_bounded_user_ref(
    std::atomic<std::uint64_t> &next, std::uint64_t end_exclusive) {
  auto current = next.load(std::memory_order_relaxed);
  while (current < end_exclusive) {
    if (next.compare_exchange_weak(current, current + 1,
                                   std::memory_order_relaxed,
                                   std::memory_order_relaxed))
      return static_cast<std::uint32_t>(current);
  }
  return std::nullopt;
}

inline void put_u16(std::uint8_t *out, std::uint16_t value) {
  value = htons(value);
  std::memcpy(out, &value, sizeof(value));
}

inline void put_u32(std::uint8_t *out, std::uint32_t value) {
  value = htonl(value);
  std::memcpy(out, &value, sizeof(value));
}

inline void put_u64(std::uint8_t *out, std::uint64_t value) {
  value = htobe64(value);
  std::memcpy(out, &value, sizeof(value));
}

inline std::uint16_t get_u16(const std::uint8_t *in) {
  std::uint16_t value{};
  std::memcpy(&value, in, sizeof(value));
  return ntohs(value);
}

inline std::uint32_t get_u32(const std::uint8_t *in) {
  std::uint32_t value{};
  std::memcpy(&value, in, sizeof(value));
  return ntohl(value);
}

inline std::uint64_t get_u64(const std::uint8_t *in) {
  std::uint64_t value{};
  std::memcpy(&value, in, sizeof(value));
  return be64toh(value);
}

inline void put_ascii(std::uint8_t *out, std::size_t width,
                      std::string_view value) {
  std::memset(out, ' ', width);
  std::memcpy(out, value.data(), std::min(width, value.size()));
}

inline std::string get_ascii(const std::uint8_t *in, std::size_t width) {
  std::string value(reinterpret_cast<const char *>(in), width);
  while (!value.empty() && value.back() == ' ') value.pop_back();
  return value;
}

inline bool send_all(int fd, const void *data, std::size_t length) {
  const auto *cursor = static_cast<const std::uint8_t *>(data);
  while (length) {
    const auto sent = ::send(fd, cursor, length, MSG_NOSIGNAL);
    if (sent < 0 && errno == EINTR) continue;
    if (sent <= 0) return false;
    cursor += sent;
    length -= static_cast<std::size_t>(sent);
  }
  return true;
}

inline bool recv_all(int fd, void *data, std::size_t length) {
  auto *cursor = static_cast<std::uint8_t *>(data);
  while (length) {
    const auto received = ::recv(fd, cursor, length, 0);
    if (received < 0 && errno == EINTR) continue;
    if (received <= 0) return false;
    cursor += received;
    length -= static_cast<std::size_t>(received);
  }
  return true;
}

inline int tcp_listener(const std::string &ip, std::uint16_t port) {
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) throw std::runtime_error("socket: " + std::string(std::strerror(errno)));
  int one = 1;
  ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_port = htons(port);
  if (::inet_pton(AF_INET, ip.c_str(), &address.sin_addr) != 1 ||
      ::bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0 ||
      ::listen(fd, 32) < 0) {
    const std::string error = std::strerror(errno);
    ::close(fd);
    throw std::runtime_error("listen " + ip + ':' + std::to_string(port) + ": " + error);
  }
  return fd;
}

class EventEmitter {
 public:
  EventEmitter(std::string source, std::string host, std::uint16_t port)
      : source_(std::move(source)) {
    if (host == "off" || host == "none" || !port) return;
    fd_ = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (fd_ < 0) throw std::runtime_error("telemetry socket failed");
    target_.sin_family = AF_INET;
    target_.sin_port = htons(port);
    if (::inet_pton(AF_INET, host.c_str(), &target_.sin_addr) != 1) {
      ::close(fd_);
      fd_ = -1;
      throw std::runtime_error("invalid telemetry host");
    }
  }

  ~EventEmitter() { if (fd_ >= 0) ::close(fd_); }
  bool enabled() const noexcept { return fd_ >= 0; }

  void emit(std::string_view kind, std::string_view fields_json = "{}") noexcept {
    if (!enabled()) return;
    try {
      const auto sequence = ++sequence_;
      std::ostringstream event;
      event << "{\"schema\":\"flle.trading-event.v1\",\"event_id\":\""
            << source_ << ':' << sequence << "\",\"source\":\"" << source_
            << "\",\"kind\":\"" << kind << "\",\"event_ns\":" << realtime_ns()
            << ",\"sequence\":" << sequence
            << ",\"environment\":\"HISTORICAL_MARKET_PAPER_EXECUTION\",\"fields\":"
            << fields_json << '}';
      const auto payload = event.str();
      ::sendto(fd_, payload.data(), payload.size(), MSG_DONTWAIT,
               reinterpret_cast<const sockaddr *>(&target_), sizeof(target_));
    } catch (...) {
      // Best-effort management telemetry must never stop or block the C++ path.
    }
  }

 private:
  std::string source_;
  int fd_{-1};
  sockaddr_in target_{};
  std::atomic<std::uint64_t> sequence_{0};
};

inline std::vector<std::string> split(std::string_view input, char separator) {
  std::vector<std::string> parts;
  std::size_t begin = 0;
  while (begin <= input.size()) {
    const auto end = input.find(separator, begin);
    parts.emplace_back(input.substr(
        begin, end == std::string_view::npos ? input.size() - begin : end - begin));
    if (end == std::string_view::npos) break;
    begin = end + 1;
  }
  return parts;
}

}  // namespace flle
