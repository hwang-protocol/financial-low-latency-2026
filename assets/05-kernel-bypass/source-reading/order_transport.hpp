#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <string_view>

namespace flle {

// The trading session owns protocol semantics; an OrderTransport only owns
// the local TCP byte stream.  The POSIX and TCPDirect binaries provide
// different factories for this same interface.
class OrderTransport {
 public:
  virtual ~OrderTransport() = default;

  virtual bool connect(const std::string &local_ip,
                       const std::string &remote_ip,
                       std::uint16_t remote_port) = 0;
  virtual bool send_all(const void *data, std::size_t length) = 0;
  virtual bool recv_all(void *data, std::size_t length) = 0;
  virtual void close() = 0;
  virtual int incoming_cpu() const = 0;
  // Called only by the order thread, while no order is in flight.
  virtual bool set_order_dscp(int) { return false; }
  virtual std::string order_dscp_state() const {
    return "{\"error\":\"order DSCP is unsupported\"}";
  }
};

std::unique_ptr<OrderTransport> make_order_transport();
std::string_view order_transport_name();

}  // namespace flle
