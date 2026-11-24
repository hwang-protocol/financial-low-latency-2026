#include "order_transport.hpp"

#include "common.hpp"

#include <netinet/tcp.h>

namespace flle {
namespace {

class PosixOrderTransport final : public OrderTransport {
 public:
  ~PosixOrderTransport() override { close(); }

  bool connect(const std::string &local_ip, const std::string &remote_ip,
               std::uint16_t remote_port) override {
    close();
    fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd_ < 0) return false;

    int one = 1;
    if (::setsockopt(fd_, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one)) < 0) {
      close();
      return false;
    }
    int observed = 0;
    socklen_t observed_length = sizeof(observed);
    if (::getsockopt(fd_, IPPROTO_TCP, TCP_NODELAY, &observed,
                     &observed_length) < 0 ||
        observed == 0) {
      close();
      return false;
    }
    if (!set_order_dscp(dscp_)) return false;
    sockaddr_in local{};
    local.sin_family = AF_INET;
    local.sin_port = 0;
    sockaddr_in remote{};
    remote.sin_family = AF_INET;
    remote.sin_port = htons(remote_port);
    if (::inet_pton(AF_INET, local_ip.c_str(), &local.sin_addr) != 1 ||
        ::inet_pton(AF_INET, remote_ip.c_str(), &remote.sin_addr) != 1 ||
        ::bind(fd_, reinterpret_cast<sockaddr *>(&local), sizeof(local)) < 0 ||
        ::connect(fd_, reinterpret_cast<sockaddr *>(&remote), sizeof(remote)) < 0) {
      close();
      return false;
    }
    return true;
  }

  bool send_all(const void *data, std::size_t length) override {
    return fd_ >= 0 && flle::send_all(fd_, data, length);
  }

  bool recv_all(void *data, std::size_t length) override {
    return fd_ >= 0 && flle::recv_all(fd_, data, length);
  }

  void close() override {
    if (fd_ >= 0) ::close(fd_);
    fd_ = -1;
  }

  int incoming_cpu() const override {
    int cpu = -1;
    socklen_t length = sizeof(cpu);
    return fd_ >= 0 &&
                   ::getsockopt(fd_, SOL_SOCKET, SO_INCOMING_CPU, &cpu, &length) == 0
               ? cpu
               : -1;
  }

  bool set_order_dscp(int dscp) override {
    if (dscp < 0 || dscp > 63) return false;
    if (fd_ >= 0) {
      int before = 0, observed = 0;
      socklen_t length = sizeof(before);
      if (::getsockopt(fd_, IPPROTO_IP, IP_TOS, &before, &length) < 0) {
        close();
        return false;
      }
      const int tos = (dscp << 2) | (before & 3);  // Preserve ECN bits.
      length = sizeof(observed);
      if (::setsockopt(fd_, IPPROTO_IP, IP_TOS, &tos, sizeof(tos)) < 0 ||
          ::getsockopt(fd_, IPPROTO_IP, IP_TOS, &observed, &length) < 0 ||
          (observed >> 2) != dscp) {
        close();  // Do not continue with an unverified socket marking.
        return false;
      }
    }
    dscp_ = dscp;  // Also applied when this transport reconnects.
    return true;
  }

  std::string order_dscp_state() const override {
    int tos = 0;
    sockaddr_in local{};
    socklen_t length = sizeof(tos), address_length = sizeof(local);
    if (fd_ >= 0 &&
        (::getsockopt(fd_, IPPROTO_IP, IP_TOS, &tos, &length) < 0 ||
         ::getsockname(fd_, reinterpret_cast<sockaddr *>(&local), &address_length) < 0 ||
         (tos >> 2) != dscp_))
      return "{\"error\":\"order IP_TOS readback failed\"}";
    return "{\"ok\":true,\"dscp\":" + std::to_string(dscp_) +
           ",\"tos\":" + (fd_ < 0 ? std::string("null") : std::to_string(tos)) +
           ",\"connected\":" + (fd_ < 0 ? "false" : "true") +
           ",\"local_port\":" + std::to_string(ntohs(local.sin_port)) +
           ",\"pid\":" + std::to_string(::getpid()) + "}";
  }

 private:
  int fd_{-1};
  int dscp_{0};
};

}  // namespace

std::unique_ptr<OrderTransport> make_order_transport() {
  return std::make_unique<PosixOrderTransport>();
}

std::string_view order_transport_name() { return "POSIX_SOCKET"; }

}  // namespace flle
