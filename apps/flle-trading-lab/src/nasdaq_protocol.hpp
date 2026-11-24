#pragma once

#include "common.hpp"

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace flle::nasdaq {

constexpr std::size_t kMoldHeaderBytes = 20;
constexpr std::size_t kSoupLoginRequestBytes = 46;
constexpr std::size_t kSoupLoginAcceptedBytes = 30;
constexpr std::size_t kOuchEnterBytes = 47;
constexpr std::size_t kOuchAcceptedBytes = 64;
constexpr std::size_t kOuchExecutedBytes = 36;
constexpr std::size_t kOuchRejectedBytes = 31;

inline std::uint64_t get_u48(const std::uint8_t *in) {
  return (static_cast<std::uint64_t>(in[0]) << 40U) |
         (static_cast<std::uint64_t>(in[1]) << 32U) |
         (static_cast<std::uint64_t>(in[2]) << 24U) |
         (static_cast<std::uint64_t>(in[3]) << 16U) |
         (static_cast<std::uint64_t>(in[4]) << 8U) |
         static_cast<std::uint64_t>(in[5]);
}

inline void put_u48(std::uint8_t *out, std::uint64_t value) {
  for (int index = 5; index >= 0; --index) {
    out[index] = static_cast<std::uint8_t>(value & 0xffU);
    value >>= 8U;
  }
}

inline std::optional<std::uint64_t> itch_timestamp(const std::uint8_t *message,
                                                   std::size_t length) {
  if (length < 11) return std::nullopt;
  return get_u48(message + 5);
}

inline std::string itch_symbol(const std::uint8_t *message, std::size_t length) {
  if (!length) return {};
  std::size_t offset = 0;
  switch (message[0]) {
    case 'R': case 'H': case 'Y': case 'L': case 'N': offset = 11; break;
    case 'A': case 'F': case 'P': offset = 24; break;
    case 'Q': offset = 19; break;
    case 'I': offset = 28; break;
    default: return {};
  }
  return length >= offset + 8 ? get_ascii(message + offset, 8) : std::string{};
}

struct MoldPacket {
  std::string session;
  std::uint64_t first_sequence{};
  std::vector<std::vector<std::uint8_t>> messages;
};

inline std::vector<std::uint8_t> encode_mold(
    std::string_view session, std::uint64_t first_sequence,
    const std::vector<std::vector<std::uint8_t>> &messages) {
  if (session.size() > 10 || messages.size() > 0xfffeU)
    throw std::runtime_error("invalid MoldUDP64 packet");
  std::size_t total = kMoldHeaderBytes;
  for (const auto &message : messages) {
    if (message.empty() || message.size() > 0xffffU)
      throw std::runtime_error("invalid MoldUDP64 message length");
    total += 2 + message.size();
  }
  std::vector<std::uint8_t> packet(total);
  put_ascii(packet.data(), 10, session);
  put_u64(packet.data() + 10, first_sequence);
  put_u16(packet.data() + 18, static_cast<std::uint16_t>(messages.size()));
  std::size_t cursor = kMoldHeaderBytes;
  for (const auto &message : messages) {
    put_u16(packet.data() + cursor, static_cast<std::uint16_t>(message.size()));
    cursor += 2;
    std::memcpy(packet.data() + cursor, message.data(), message.size());
    cursor += message.size();
  }
  return packet;
}

inline bool decode_mold(const std::uint8_t *packet, std::size_t length,
                        MoldPacket &out, std::string &error) {
  if (length < kMoldHeaderBytes) { error = "MOLD_SHORT_HEADER"; return false; }
  out.session = get_ascii(packet, 10);
  out.first_sequence = get_u64(packet + 10);
  const auto count = get_u16(packet + 18);
  if (out.session.empty() || count == 0xffffU) {
    error = "MOLD_UNSUPPORTED_CONTROL";
    return false;
  }
  out.messages.clear();
  out.messages.reserve(count);
  std::size_t cursor = kMoldHeaderBytes;
  for (std::uint16_t index = 0; index < count; ++index) {
    if (cursor + 2 > length) { error = "MOLD_TRUNCATED_LENGTH"; return false; }
    const auto message_length = get_u16(packet + cursor);
    cursor += 2;
    if (!message_length || cursor + message_length > length) {
      error = "MOLD_TRUNCATED_MESSAGE";
      return false;
    }
    out.messages.emplace_back(packet + cursor, packet + cursor + message_length);
    cursor += message_length;
  }
  if (cursor != length) { error = "MOLD_TRAILING_BYTES"; return false; }
  return true;
}

inline bool send_soup(int fd, char packet_type, const std::uint8_t *payload,
                      std::size_t payload_length) {
  if (payload_length + 1 > 0xffffU) return false;
  std::vector<std::uint8_t> packet(payload_length + 3);
  put_u16(packet.data(), static_cast<std::uint16_t>(payload_length + 1));
  packet[2] = static_cast<std::uint8_t>(packet_type);
  if (payload_length) std::memcpy(packet.data() + 3, payload, payload_length);
  return send_all(fd, packet.data(), packet.size());
}

inline bool send_soup(int fd, char packet_type,
                      const std::vector<std::uint8_t> &payload) {
  return send_soup(fd, packet_type, payload.data(), payload.size());
}

inline bool recv_soup(int fd, char &packet_type, std::vector<std::uint8_t> &payload) {
  std::array<std::uint8_t, 2> prefix{};
  if (!recv_all(fd, prefix.data(), prefix.size())) return false;
  const auto packet_length = get_u16(prefix.data());
  if (packet_length < 1) return false;
  std::vector<std::uint8_t> body(packet_length);
  if (!recv_all(fd, body.data(), body.size())) return false;
  packet_type = static_cast<char>(body[0]);
  payload.assign(body.begin() + 1, body.end());
  return true;
}

template <typename Stream>
inline bool send_soup(Stream &stream, char packet_type,
                      const std::uint8_t *payload,
                      std::size_t payload_length) {
  if (payload_length + 1 > 0xffffU) return false;
  std::vector<std::uint8_t> packet(payload_length + 3);
  put_u16(packet.data(), static_cast<std::uint16_t>(payload_length + 1));
  packet[2] = static_cast<std::uint8_t>(packet_type);
  if (payload_length) std::memcpy(packet.data() + 3, payload, payload_length);
  return stream.send_all(packet.data(), packet.size());
}

template <typename Stream>
inline bool send_soup(Stream &stream, char packet_type,
                      const std::vector<std::uint8_t> &payload) {
  return send_soup(stream, packet_type, payload.data(), payload.size());
}

template <typename Stream>
inline bool recv_soup(Stream &stream, char &packet_type,
                      std::vector<std::uint8_t> &payload) {
  std::array<std::uint8_t, 2> prefix{};
  if (!stream.recv_all(prefix.data(), prefix.size())) return false;
  const auto packet_length = get_u16(prefix.data());
  if (packet_length < 1) return false;
  std::vector<std::uint8_t> body(packet_length);
  if (!stream.recv_all(body.data(), body.size())) return false;
  packet_type = static_cast<char>(body[0]);
  payload.assign(body.begin() + 1, body.end());
  return true;
}

inline std::array<std::uint8_t, kSoupLoginRequestBytes> soup_login_request(
    std::string_view username, std::string_view password) {
  std::array<std::uint8_t, kSoupLoginRequestBytes> out{};
  put_ascii(out.data(), 6, username);
  put_ascii(out.data() + 6, 10, password);
  put_ascii(out.data() + 16, 10, "");
  put_ascii(out.data() + 26, 20, "");
  return out;
}

inline std::array<std::uint8_t, kSoupLoginAcceptedBytes> soup_login_accepted(
    std::string_view session, std::uint64_t next_sequence) {
  std::array<std::uint8_t, kSoupLoginAcceptedBytes> out{};
  put_ascii(out.data(), 10, session);
  std::ostringstream sequence;
  sequence << std::setfill('0') << std::setw(20) << next_sequence;
  put_ascii(out.data() + 10, 20, sequence.str());
  return out;
}

enum class Side : char { Buy = 'B', Sell = 'S' };

inline std::string side_name(Side side) {
  return side == Side::Buy ? "BUY" : "SELL";
}

struct EnterOrder {
  std::uint32_t user_ref{};
  Side side{Side::Buy};
  std::uint32_t quantity{};
  std::string symbol;
  std::uint64_t price_x10000{};
  char tif{'3'};
  char display{'Y'};
  char capacity{'A'};
  char iso{'N'};
  char cross{'N'};
  std::string clordid;
};

inline std::array<std::uint8_t, kOuchEnterBytes> encode_enter(const EnterOrder &order) {
  std::array<std::uint8_t, kOuchEnterBytes> out{};
  out[0] = 'O';
  put_u32(out.data() + 1, order.user_ref);
  out[5] = static_cast<std::uint8_t>(order.side);
  put_u32(out.data() + 6, order.quantity);
  put_ascii(out.data() + 10, 8, order.symbol);
  put_u64(out.data() + 18, order.price_x10000);
  out[26] = order.tif;
  out[27] = order.display;
  out[28] = order.capacity;
  out[29] = order.iso;
  out[30] = order.cross;
  put_ascii(out.data() + 31, 14, order.clordid);
  put_u16(out.data() + 45, 0);
  return out;
}

inline bool decode_enter(const std::uint8_t *in, std::size_t length,
                         EnterOrder &order, std::string &error) {
  if (length != kOuchEnterBytes || in[0] != 'O') {
    error = "OUCH_BAD_ENTER_LENGTH_OR_TYPE";
    return false;
  }
  order.user_ref = get_u32(in + 1);
  order.side = static_cast<Side>(in[5]);
  order.quantity = get_u32(in + 6);
  order.symbol = get_ascii(in + 10, 8);
  order.price_x10000 = get_u64(in + 18);
  order.tif = static_cast<char>(in[26]);
  order.display = static_cast<char>(in[27]);
  order.capacity = static_cast<char>(in[28]);
  order.iso = static_cast<char>(in[29]);
  order.cross = static_cast<char>(in[30]);
  order.clordid = get_ascii(in + 31, 14);
  if (!order.user_ref || (order.side != Side::Buy && order.side != Side::Sell) ||
      !order.quantity || order.symbol.empty() || !order.price_x10000 ||
      order.tif != '3' || get_u16(in + 45) != 0) {
    error = "OUCH_BAD_ENTER_FIELD";
    return false;
  }
  return true;
}

struct Accepted {
  std::uint64_t timestamp_ns{};
  EnterOrder order;
  std::uint64_t order_reference{};
  char order_state{'L'};
};

inline std::array<std::uint8_t, kOuchAcceptedBytes> encode_accepted(
    const Accepted &accepted) {
  std::array<std::uint8_t, kOuchAcceptedBytes> out{};
  out[0] = 'A';
  put_u64(out.data() + 1, accepted.timestamp_ns);
  put_u32(out.data() + 9, accepted.order.user_ref);
  out[13] = static_cast<std::uint8_t>(accepted.order.side);
  put_u32(out.data() + 14, accepted.order.quantity);
  put_ascii(out.data() + 18, 8, accepted.order.symbol);
  put_u64(out.data() + 26, accepted.order.price_x10000);
  out[34] = accepted.order.tif;
  out[35] = accepted.order.display;
  put_u64(out.data() + 36, accepted.order_reference);
  out[44] = accepted.order.capacity;
  out[45] = accepted.order.iso;
  out[46] = accepted.order.cross;
  out[47] = accepted.order_state;
  put_ascii(out.data() + 48, 14, accepted.order.clordid);
  put_u16(out.data() + 62, 0);
  return out;
}

struct Executed {
  std::uint64_t timestamp_ns{};
  std::uint32_t user_ref{};
  std::uint32_t quantity{};
  std::uint64_t price_x10000{};
  char liquidity{'A'};
  std::uint64_t match_number{};
};

inline std::array<std::uint8_t, kOuchExecutedBytes> encode_executed(
    const Executed &executed) {
  std::array<std::uint8_t, kOuchExecutedBytes> out{};
  out[0] = 'E';
  put_u64(out.data() + 1, executed.timestamp_ns);
  put_u32(out.data() + 9, executed.user_ref);
  put_u32(out.data() + 13, executed.quantity);
  put_u64(out.data() + 17, executed.price_x10000);
  out[25] = executed.liquidity;
  put_u64(out.data() + 26, executed.match_number);
  put_u16(out.data() + 34, 0);
  return out;
}

struct Rejected {
  std::uint64_t timestamp_ns{};
  std::uint32_t user_ref{};
  std::string reason;
  std::string clordid;
};

inline std::array<std::uint8_t, kOuchRejectedBytes> encode_rejected(
    const Rejected &rejected) {
  std::array<std::uint8_t, kOuchRejectedBytes> out{};
  out[0] = 'J';
  put_u64(out.data() + 1, rejected.timestamp_ns);
  put_u32(out.data() + 9, rejected.user_ref);
  put_ascii(out.data() + 13, 2, rejected.reason);
  put_ascii(out.data() + 15, 14, rejected.clordid);
  put_u16(out.data() + 29, 0);
  return out;
}

struct OuchResponse {
  char type{};
  std::uint64_t timestamp_ns{};
  std::uint32_t user_ref{};
  std::uint32_t quantity{};
  std::uint64_t price_x10000{};
  std::uint64_t order_reference{};
  std::uint64_t match_number{};
  std::string reason;
  std::string symbol;
  Side side{Side::Buy};
};

inline bool decode_response(const std::uint8_t *in, std::size_t length,
                            OuchResponse &out, std::string &error) {
  if (!length) { error = "OUCH_EMPTY_RESPONSE"; return false; }
  out = OuchResponse{};
  out.type = static_cast<char>(in[0]);
  if (out.type == 'A' && length == kOuchAcceptedBytes) {
    out.timestamp_ns = get_u64(in + 1);
    out.user_ref = get_u32(in + 9);
    out.side = static_cast<Side>(in[13]);
    out.quantity = get_u32(in + 14);
    out.symbol = get_ascii(in + 18, 8);
    out.price_x10000 = get_u64(in + 26);
    out.order_reference = get_u64(in + 36);
    return true;
  }
  if (out.type == 'E' && length == kOuchExecutedBytes) {
    out.timestamp_ns = get_u64(in + 1);
    out.user_ref = get_u32(in + 9);
    out.quantity = get_u32(in + 13);
    out.price_x10000 = get_u64(in + 17);
    out.match_number = get_u64(in + 26);
    return true;
  }
  if (out.type == 'J' && length == kOuchRejectedBytes) {
    out.timestamp_ns = get_u64(in + 1);
    out.user_ref = get_u32(in + 9);
    out.reason = get_ascii(in + 13, 2);
    return true;
  }
  error = "OUCH_UNSUPPORTED_RESPONSE";
  return false;
}

}  // namespace flle::nasdaq
