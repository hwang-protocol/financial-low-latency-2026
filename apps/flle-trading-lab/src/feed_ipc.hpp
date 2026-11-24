#pragma once

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <endian.h>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>

namespace flle {
// Local packet envelope. The original MoldUDP64 bytes are never rewritten.
// Byte 4: 0=unicast, 1=multicast. Bytes 8..15: receiver CLOCK_MONOTONIC ns.
inline constexpr std::size_t feed_header_size = 16;
inline sockaddr_un feed_address(const std::string &path) {
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  if (path.empty() || path.size() >= sizeof(address.sun_path))
    throw std::runtime_error("invalid local feed socket path");
  std::memcpy(address.sun_path, path.c_str(), path.size() + 1);
  return address;
}
inline void feed_header(std::uint8_t *out, unsigned path, std::uint64_t ns) {
  std::memset(out, 0, feed_header_size);
  std::memcpy(out, "FLF1", 4);
  out[4] = static_cast<std::uint8_t>(path);
  ns = htobe64(ns);
  std::memcpy(out + 8, &ns, sizeof(ns));
}
inline bool parse_feed_header(const std::uint8_t *data, std::size_t length,
                              unsigned &path, std::uint64_t &ns) {
  if (length < feed_header_size || std::memcmp(data, "FLF1", 4) || data[4] > 1)
    return false;
  path = data[4];
  std::memcpy(&ns, data + 8, sizeof(ns));
  ns = be64toh(ns);
  return true;
}
}  // namespace flle
