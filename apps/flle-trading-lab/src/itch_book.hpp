#pragma once

#include "nasdaq_protocol.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <istream>
#include <map>
#include <ostream>
#include <string>
#include <unordered_map>

namespace flle::nasdaq {

struct PriceLevel {
  std::uint64_t price_x10000{};
  std::uint64_t shares{};
};

struct TopOfBook {
  std::array<PriceLevel, kDepth> bids{};
  std::array<PriceLevel, kDepth> asks{};
  std::uint64_t last_x10000{};
  std::uint64_t volume{};

  bool ready() const { return bids[0].price_x10000 && asks[0].price_x10000; }
};

class ItchBook {
 public:
  bool apply(const std::uint8_t *message, std::size_t length) {
    if (!length) return false;
    switch (message[0]) {
      case 'A': case 'F': return add(message, length);
      case 'E': return execute(message, length, false);
      case 'C': return execute(message, length, true);
      case 'X': return cancel(message, length);
      case 'D': return erase(message, length);
      case 'U': return replace(message, length);
      case 'P': return trade(message, length);
      case 'Q': return cross(message, length);
      default: return false;
    }
  }

  TopOfBook top(const std::string &symbol) const {
    TopOfBook result;
    const auto found = symbols_.find(symbol);
    if (found == symbols_.end()) return result;
    const auto &book = found->second;
    std::size_t index = 0;
    for (auto it = book.bids.rbegin(); it != book.bids.rend() && index < kDepth;
         ++it, ++index)
      result.bids[index] = {it->first, it->second};
    index = 0;
    for (auto it = book.asks.begin(); it != book.asks.end() && index < kDepth;
         ++it, ++index)
      result.asks[index] = {it->first, it->second};
    result.last_x10000 = book.last_x10000;
    result.volume = book.volume;
    return result;
  }

  void clear() {
    orders_.clear();
    symbols_.clear();
  }

  std::size_t save_checkpoint(std::ostream &output) const {
    std::array<std::uint8_t, 16> header{};
    const std::array<std::uint8_t, 8> magic{{'F','L','L','E','B','0','1',0}};
    std::copy(magic.begin(), magic.end(), header.begin());
    put_u64(header.data() + 8, orders_.size());
    output.write(reinterpret_cast<const char *>(header.data()), header.size());
    for (const auto &[reference, order] : orders_) {
      std::array<std::uint8_t, 25> record{};
      put_u64(record.data(), reference);
      put_ascii(record.data() + 8, 8, order.symbol);
      record[16] = static_cast<std::uint8_t>(order.side);
      put_u32(record.data() + 17, static_cast<std::uint32_t>(order.shares));
      put_u32(record.data() + 21, static_cast<std::uint32_t>(order.price));
      output.write(reinterpret_cast<const char *>(record.data()), record.size());
    }
    if (!output) throw std::runtime_error("failed to write book checkpoint");
    return orders_.size();
  }

  std::size_t load_checkpoint(std::istream &input) {
    std::array<std::uint8_t, 16> header{};
    input.read(reinterpret_cast<char *>(header.data()), header.size());
    const std::array<std::uint8_t, 8> magic{{'F','L','L','E','B','0','1',0}};
    if (!input || !std::equal(magic.begin(), magic.end(), header.begin()))
      throw std::runtime_error("invalid book checkpoint header");
    const auto count = get_u64(header.data() + 8);
    clear();
    for (std::uint64_t index = 0; index < count; ++index) {
      std::array<std::uint8_t, 25> record{};
      input.read(reinterpret_cast<char *>(record.data()), record.size());
      if (!input) throw std::runtime_error("truncated book checkpoint");
      const auto reference = get_u64(record.data());
      Order order{get_ascii(record.data() + 8, 8), static_cast<char>(record[16]),
                  get_u32(record.data() + 17), get_u32(record.data() + 21)};
      if (!reference || (order.side != 'B' && order.side != 'S') ||
          order.symbol.empty() || !order.shares || !order.price)
        throw std::runtime_error("invalid book checkpoint record");
      orders_[reference] = order;
      aggregate(order, static_cast<std::int64_t>(order.shares));
    }
    return orders_.size();
  }

 private:
  struct Order {
    std::string symbol;
    char side{};
    std::uint64_t shares{};
    std::uint64_t price{};
  };
  struct SymbolBook {
    std::map<std::uint64_t, std::uint64_t> bids;
    std::map<std::uint64_t, std::uint64_t> asks;
    std::uint64_t last_x10000{};
    std::uint64_t volume{};
  };

  std::unordered_map<std::uint64_t, Order> orders_;
  std::unordered_map<std::string, SymbolBook> symbols_;

  void aggregate(const Order &order, std::int64_t delta) {
    auto &levels = order.side == 'B' ? symbols_[order.symbol].bids
                                    : symbols_[order.symbol].asks;
    auto &quantity = levels[order.price];
    if (delta >= 0) quantity += static_cast<std::uint64_t>(delta);
    else quantity -= std::min(quantity, static_cast<std::uint64_t>(-delta));
    if (!quantity) levels.erase(order.price);
  }

  bool add(const std::uint8_t *m, std::size_t n) {
    if ((m[0] == 'A' && n != 36) || (m[0] == 'F' && n != 40)) return false;
    Order order{get_ascii(m + 24, 8), static_cast<char>(m[19]),
                get_u32(m + 20), get_u32(m + 32)};
    if ((order.side != 'B' && order.side != 'S') || order.symbol.empty() ||
        !order.shares || !order.price) return false;
    const auto reference = get_u64(m + 11);
    orders_[reference] = order;
    aggregate(order, static_cast<std::int64_t>(order.shares));
    return true;
  }

  bool reduce(std::uint64_t reference, std::uint64_t shares, bool update_trade,
              std::uint64_t execution_price = 0) {
    const auto found = orders_.find(reference);
    if (found == orders_.end()) return false;
    auto &order = found->second;
    const auto removed = std::min(shares, order.shares);
    aggregate(order, -static_cast<std::int64_t>(removed));
    order.shares -= removed;
    if (update_trade) {
      auto &book = symbols_[order.symbol];
      book.last_x10000 = execution_price ? execution_price : order.price;
      book.volume += removed;
    }
    if (!order.shares) orders_.erase(found);
    return true;
  }

  bool execute(const std::uint8_t *m, std::size_t n, bool priced) {
    if ((!priced && n != 31) || (priced && n != 36)) return false;
    return reduce(get_u64(m + 11), get_u32(m + 19), true,
                  priced ? get_u32(m + 32) : 0);
  }

  bool cancel(const std::uint8_t *m, std::size_t n) {
    return n == 23 && reduce(get_u64(m + 11), get_u32(m + 19), false);
  }

  bool erase(const std::uint8_t *m, std::size_t n) {
    if (n != 19) return false;
    const auto found = orders_.find(get_u64(m + 11));
    if (found == orders_.end()) return false;
    aggregate(found->second, -static_cast<std::int64_t>(found->second.shares));
    orders_.erase(found);
    return true;
  }

  bool replace(const std::uint8_t *m, std::size_t n) {
    if (n != 35) return false;
    const auto found = orders_.find(get_u64(m + 11));
    if (found == orders_.end()) return false;
    auto order = found->second;
    aggregate(order, -static_cast<std::int64_t>(order.shares));
    orders_.erase(found);
    order.shares = get_u32(m + 27);
    order.price = get_u32(m + 31);
    orders_[get_u64(m + 19)] = order;
    aggregate(order, static_cast<std::int64_t>(order.shares));
    return true;
  }

  bool trade(const std::uint8_t *m, std::size_t n) {
    if (n != 44) return false;
    auto &book = symbols_[get_ascii(m + 24, 8)];
    book.last_x10000 = get_u32(m + 32);
    book.volume += get_u32(m + 20);
    return true;
  }

  bool cross(const std::uint8_t *m, std::size_t n) {
    if (n != 40) return false;
    auto &book = symbols_[get_ascii(m + 19, 8)];
    book.last_x10000 = get_u32(m + 27);
    book.volume += get_u64(m + 11);
    return true;
  }
};

inline std::string levels_json(const std::array<PriceLevel, kDepth> &levels) {
  std::ostringstream out;
  out << '[';
  for (std::size_t index = 0; index < levels.size(); ++index) {
    if (index) out << ',';
    out << '[' << levels[index].price_x10000 << ',' << levels[index].shares << ']';
  }
  return out.str() + ']';
}

}  // namespace flle::nasdaq
