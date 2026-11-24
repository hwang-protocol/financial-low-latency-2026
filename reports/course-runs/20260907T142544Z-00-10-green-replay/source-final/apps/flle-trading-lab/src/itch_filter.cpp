#include "nasdaq_protocol.hpp"

#include <array>
#include <fstream>
#include <unordered_map>

namespace {

struct OrderState {
  std::uint8_t symbol{};
  std::uint32_t shares{};
};

std::uint8_t symbol_code(const std::uint8_t *message, std::size_t length,
                         std::size_t offset) {
  if (length < offset + 8) return 0;
  const auto symbol = flle::get_ascii(message + offset, 8);
  if (symbol == "AAPL") return 1;
  if (symbol == "NVDA") return 2;
  return 0;
}

bool keep(std::vector<std::uint8_t> &message,
          std::unordered_map<std::uint64_t, OrderState> &orders) {
  if (message.empty()) return false;
  const auto *m = message.data();
  const auto n = message.size();
  switch (m[0]) {
    case 'S': return true;
    case 'R': case 'H': case 'Y': case 'L': case 'N':
      return symbol_code(m, n, 11) != 0;
    case 'P': return symbol_code(m, n, 24) != 0;
    case 'Q': return symbol_code(m, n, 19) != 0;
    case 'I': return symbol_code(m, n, 28) != 0;
    case 'A': case 'F': {
      if (n < 36) return false;
      const auto symbol = symbol_code(m, n, 24);
      if (!symbol) return false;
      orders[flle::get_u64(m + 11)] = {symbol, flle::get_u32(m + 20)};
      return true;
    }
    case 'E': case 'C': case 'X': case 'D': {
      if (n < 19) return false;
      const auto reference = flle::get_u64(m + 11);
      const auto found = orders.find(reference);
      if (found == orders.end()) return false;
      if (m[0] == 'D') {
        orders.erase(found);
      } else if (n >= 23) {
        const auto removed = flle::get_u32(m + 19);
        if (removed >= found->second.shares) orders.erase(found);
        else found->second.shares -= removed;
      }
      return true;
    }
    case 'U': {
      if (n != 35) return false;
      const auto found = orders.find(flle::get_u64(m + 11));
      if (found == orders.end()) return false;
      const auto symbol = found->second.symbol;
      orders.erase(found);
      orders[flle::get_u64(m + 19)] = {symbol, flle::get_u32(m + 27)};
      return true;
    }
    default: return false;
  }
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: flle-itch-filter STATS_JSON\n";
    return 2;
  }
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);
  std::array<std::uint64_t, 256> input_counts{};
  std::array<std::uint64_t, 256> output_counts{};
  std::unordered_map<std::uint64_t, OrderState> orders;
  orders.reserve(2000000);
  std::uint64_t input_messages{};
  std::uint64_t output_messages{};
  std::uint64_t output_bytes{};
  std::uint64_t first_timestamp{};
  std::uint64_t last_timestamp{};
  while (true) {
    std::array<std::uint8_t, 2> prefix{};
    std::cin.read(reinterpret_cast<char *>(prefix.data()), prefix.size());
    if (std::cin.gcount() == 0) break;
    if (std::cin.gcount() != 2) {
      std::cerr << "truncated BinaryFILE prefix\n";
      return 1;
    }
    const auto length = flle::get_u16(prefix.data());
    if (!length) continue;
    std::vector<std::uint8_t> message(length);
    std::cin.read(reinterpret_cast<char *>(message.data()), length);
    if (std::cin.gcount() != length) {
      std::cerr << "truncated BinaryFILE message\n";
      return 1;
    }
    ++input_messages;
    ++input_counts[message[0]];
    if (!keep(message, orders)) continue;
    std::cout.write(reinterpret_cast<const char *>(prefix.data()), prefix.size());
    std::cout.write(reinterpret_cast<const char *>(message.data()), message.size());
    if (!std::cout) {
      std::cerr << "write failed\n";
      return 1;
    }
    ++output_messages;
    ++output_counts[message[0]];
    output_bytes += 2 + message.size();
    const auto timestamp = flle::nasdaq::itch_timestamp(message.data(), message.size());
    if (timestamp) {
      if (!first_timestamp) first_timestamp = *timestamp;
      last_timestamp = *timestamp;
    }
  }
  std::ofstream stats(argv[1]);
  if (!stats) {
    std::cerr << "cannot write stats\n";
    return 1;
  }
  stats << "{\n  \"input_messages_seen\":" << input_messages
        << ",\n  \"output_messages\":" << output_messages
        << ",\n  \"output_bytes\":" << output_bytes
        << ",\n  \"first_timestamp_ns\":" << first_timestamp
        << ",\n  \"last_timestamp_ns\":" << last_timestamp
        << ",\n  \"output_type_counts\":{";
  bool first = true;
  for (std::size_t index = 0; index < output_counts.size(); ++index) {
    if (!output_counts[index]) continue;
    if (!first) stats << ',';
    first = false;
    stats << "\n    \"" << static_cast<char>(index) << "\":" << output_counts[index];
  }
  stats << "\n  }\n}\n";
  return stats ? 0 : 1;
}
