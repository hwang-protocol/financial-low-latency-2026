#pragma once

#include <arpa/inet.h>
#include <stdexcept>
#include <string>

namespace flle {
// Lab endpoints, not a claim about the exchange's production A/B allocation.
inline constexpr const char *market_group_a = "233.74.125.32";
inline constexpr const char *market_group_b = "233.74.125.33";
inline constexpr const char *market_source = "20.1.1.1";
inline constexpr int market_port_a = 31032;
inline constexpr int market_port_b = 31033;
inline constexpr const char *market_schema = "udp-multicast-ab-v1";

inline bool valid_market_mode(const std::string &mode) {
  // MULTICAST remains an A-only alias for existing filter/control scripts.
  // UNICAST is retained for internal delivery and the deferred transport labs.
  return mode == "MULTICAST_A" || mode == "MULTICAST_B" || mode == "DUAL" ||
         mode == "MULTICAST" || mode == "UNICAST";
}
inline void validate_market_groups(const std::string &a, const std::string &b) {
  in_addr first{}, second{};
  if (::inet_pton(AF_INET, a.c_str(), &first) != 1 ||
      ::inet_pton(AF_INET, b.c_str(), &second) != 1 ||
      !IN_MULTICAST(ntohl(first.s_addr)) || !IN_MULTICAST(ntohl(second.s_addr)) ||
      first.s_addr == second.s_addr)
    throw std::runtime_error("A/B require two different IPv4 multicast groups");
}
}  // namespace flle
