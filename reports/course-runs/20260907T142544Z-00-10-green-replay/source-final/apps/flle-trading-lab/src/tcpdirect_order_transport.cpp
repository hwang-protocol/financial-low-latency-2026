#include "order_transport.hpp"

#include <zf/zf.h>

#include <arpa/inet.h>
#include <ifaddrs.h>
#include <netinet/tcp.h>
#include <sched.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iterator>
#include <stdexcept>

namespace flle {
namespace {

class TcpDirectOrderTransport final : public OrderTransport {
 public:
  TcpDirectOrderTransport() {
    check(zf_init(), "zf_init");
    initialized_ = true;
  }

  ~TcpDirectOrderTransport() override { release_stack(); }

  bool connect(const std::string &local_ip, const std::string &remote_ip,
               std::uint16_t remote_port) override {
    close();
    if (!stack_) initialize_stack(local_ip);
    sockaddr_in local{};
    local.sin_family = AF_INET;
    local.sin_port = 0;
    sockaddr_in remote{};
    remote.sin_family = AF_INET;
    remote.sin_port = htons(remote_port);
    if (::inet_pton(AF_INET, local_ip.c_str(), &local.sin_addr) != 1 ||
        ::inet_pton(AF_INET, remote_ip.c_str(), &remote.sin_addr) != 1)
      return false;

    struct zft_handle *handle = nullptr;
    if (zft_alloc(stack_, attr_, &handle) < 0) return false;
    if (zft_addr_bind(handle, reinterpret_cast<sockaddr *>(&local),
                      sizeof(local), 0) < 0) {
      zft_handle_free(handle);
      return false;
    }
    if (zft_connect(handle, reinterpret_cast<sockaddr *>(&remote),
                    sizeof(remote), &zocket_) < 0) {
      zft_handle_free(handle);
      zocket_ = nullptr;
      return false;
    }

    const auto deadline = std::chrono::steady_clock::now() +
                          std::chrono::seconds(5);
    while (zft_state(zocket_) == TCP_SYN_SENT &&
           std::chrono::steady_clock::now() < deadline)
      zf_reactor_perform(stack_);
    if (zft_state(zocket_) != TCP_ESTABLISHED) {
      close();
      return false;
    }
    return true;
  }

  bool send_all(const void *data, std::size_t length) override {
    auto *cursor = static_cast<const std::uint8_t *>(data);
    std::size_t sent = 0;
    while (zocket_ && sent < length) {
      const auto result = zft_send_single(zocket_, cursor + sent,
                                          length - sent, 0);
      if (result > 0) {
        sent += static_cast<std::size_t>(result);
        continue;
      }
      if (result != -EAGAIN && result != -ENOMEM) return false;
      zf_reactor_perform(stack_);
    }
    return sent == length;
  }

  bool recv_all(void *data, std::size_t length) override {
    struct RxMessage {
      struct zft_msg msg;
      struct iovec iov[8];
    } message{};
    auto *cursor = static_cast<std::uint8_t *>(data);
    std::size_t received = 0;
    while (zocket_ && received < length) {
      message.msg.iovcnt = static_cast<int>(std::size(message.iov));
      zft_zc_recv(zocket_, &message.msg, 0);
      if (message.msg.iovcnt == 0) {
        if (zf_reactor_perform(stack_) < 0) return false;
        continue;
      }

      std::size_t available = 0;
      for (int index = 0; index < message.msg.iovcnt; ++index)
        available += message.iov[index].iov_len;
      if (available == 0) {
        zft_zc_recv_done(zocket_, &message.msg);
        return false;
      }

      const auto consume = std::min(available, length - received);
      std::size_t copied = 0;
      for (int index = 0; index < message.msg.iovcnt && copied < consume;
           ++index) {
        const auto bytes = std::min(message.iov[index].iov_len,
                                    consume - copied);
        std::memcpy(cursor + received + copied, message.iov[index].iov_base,
                    bytes);
        copied += bytes;
      }
      const int status = consume == available
                             ? zft_zc_recv_done(zocket_, &message.msg)
                             : zft_zc_recv_done_some(zocket_, &message.msg,
                                                     consume);
      received += consume;
      if (status <= 0 && received < length) return false;
    }
    return received == length;
  }

  void close() override {
    if (!zocket_) return;
    zft_free(zocket_);
    zocket_ = nullptr;
    for (int attempt = 0; attempt < 64; ++attempt)
      zf_reactor_perform(stack_);
  }

  int incoming_cpu() const override { return ::sched_getcpu(); }

 private:
  static void check(int result, const char *operation) {
    if (result < 0)
      throw std::runtime_error(std::string(operation) + " failed: " +
                               std::to_string(result));
  }

  static std::string interface_for_address(const std::string &address) {
    in_addr wanted{};
    if (::inet_pton(AF_INET, address.c_str(), &wanted) != 1)
      throw std::runtime_error("invalid local IPv4 address " + address);
    struct ifaddrs *interfaces = nullptr;
    if (::getifaddrs(&interfaces) != 0)
      throw std::runtime_error("getifaddrs failed");
    std::string match;
    for (auto *item = interfaces; item; item = item->ifa_next) {
      if (!item->ifa_addr || item->ifa_addr->sa_family != AF_INET) continue;
      const auto *candidate =
          reinterpret_cast<const sockaddr_in *>(item->ifa_addr);
      if (candidate->sin_addr.s_addr == wanted.s_addr) {
        match = item->ifa_name;
        break;
      }
    }
    ::freeifaddrs(interfaces);
    if (match.empty())
      throw std::runtime_error("no interface owns local IPv4 address " +
                               address);
    return match;
  }

  void initialize_stack(const std::string &local_ip) {
    const auto interface = interface_for_address(local_ip);
    check(zf_attr_alloc(&attr_), "zf_attr_alloc");
    try {
      check(zf_attr_set_str(attr_, "name", "flle-tcpdirect"),
            "zf_attr_set_str(name)");
      check(zf_attr_set_str(attr_, "interface", interface.c_str()),
            "zf_attr_set_str(interface)");
      // X2522 CTPIO is part of this experiment's contract.  Mode 3 makes a
      // missing hardware capability a startup error instead of a quiet DMA
      // fallback; sf-np keeps the adapter's no-poison store-and-forward mode.
      check(zf_attr_set_int(attr_, "ctpio", 3),
            "zf_attr_set_int(ctpio)");
      check(zf_attr_set_str(attr_, "ctpio_mode", "sf-np"),
            "zf_attr_set_str(ctpio_mode)");
      check(zf_stack_alloc(attr_, &stack_), "zf_stack_alloc");
    } catch (...) {
      zf_attr_free(attr_);
      attr_ = nullptr;
      throw;
    }
  }

  void release_stack() noexcept {
    close();
    if (stack_) {
      for (int attempt = 0;
           attempt < 4096 && !zf_stack_is_quiescent(stack_); ++attempt)
        zf_reactor_perform(stack_);
      zf_stack_free(stack_);
      stack_ = nullptr;
    }
    if (attr_) {
      zf_attr_free(attr_);
      attr_ = nullptr;
    }
    if (initialized_) {
      zf_deinit();
      initialized_ = false;
    }
  }

  bool initialized_{false};
  struct zf_attr *attr_{nullptr};
  struct zf_stack *stack_{nullptr};
  struct zft *zocket_{nullptr};
};

}  // namespace

std::unique_ptr<OrderTransport> make_order_transport() {
  return std::make_unique<TcpDirectOrderTransport>();
}

std::string_view order_transport_name() { return "TCPDIRECT_ZF"; }

}  // namespace flle
