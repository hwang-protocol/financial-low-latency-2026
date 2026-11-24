#include "itch_book.hpp"
#include "order_queue.hpp"

#include <cassert>
#include <iostream>
#include <sstream>

namespace nasdaq = flle::nasdaq;

std::vector<std::uint8_t> add_order(std::uint64_t reference, char side,
                                    std::uint32_t shares, std::string symbol,
                                    std::uint32_t price) {
  std::vector<std::uint8_t> message(36);
  message[0] = 'A';
  flle::put_u16(message.data() + 1, 1);
  flle::put_u16(message.data() + 3, 2);
  nasdaq::put_u48(message.data() + 5, 34200000000000ULL);
  flle::put_u64(message.data() + 11, reference);
  message[19] = side;
  flle::put_u32(message.data() + 20, shares);
  flle::put_ascii(message.data() + 24, 8, symbol);
  flle::put_u32(message.data() + 32, price);
  return message;
}

int main() {
  std::atomic<std::uint64_t> next_user_ref{41};
  assert(flle::allocate_bounded_user_ref(next_user_ref, 43) == 41);
  assert(flle::allocate_bounded_user_ref(next_user_ref, 43) == 42);
  assert(!flle::allocate_bounded_user_ref(next_user_ref, 43));
  assert(next_user_ref.load() == 43);

  std::atomic<bool> stop{false};
  flle::OrderQueue<int, 8> queue;
  for (const auto mode : {flle::OrderQueueMode::DequeCv,
                          flle::OrderQueueMode::FixedCv,
                          flle::OrderQueueMode::SpscSpin}) {
    assert(queue.set_mode(mode));
    assert(queue.push(7));
    int value{};
    assert(queue.front(value, stop) && value == 7 && queue.depth() == 1);
    queue.pop();
    assert(queue.depth() == 0);
  }

  const auto add = add_order(1001, 'B', 500, "AAPL", 1982500);
  const auto ask = add_order(1002, 'S', 300, "AAPL", 1982600);
  assert(nasdaq::itch_timestamp(add.data(), add.size()) == 34200000000000ULL);
  assert(nasdaq::itch_symbol(add.data(), add.size()) == "AAPL");

  const auto mold = nasdaq::encode_mold("0612260001", 91, {add, ask});
  nasdaq::MoldPacket decoded_mold;
  std::string error;
  assert(nasdaq::decode_mold(mold.data(), mold.size(), decoded_mold, error));
  assert(decoded_mold.session == "0612260001");
  assert(decoded_mold.first_sequence == 91);
  assert(decoded_mold.messages.size() == 2);
  auto bad_mold = mold;
  bad_mold.push_back(0);
  assert(!nasdaq::decode_mold(bad_mold.data(), bad_mold.size(), decoded_mold, error));

  nasdaq::ItchBook book;
  assert(book.apply(add.data(), add.size()));
  assert(book.apply(ask.data(), ask.size()));
  auto top = book.top("AAPL");
  assert(top.ready());
  assert(top.bids[0].price_x10000 == 1982500 && top.bids[0].shares == 500);
  assert(top.asks[0].price_x10000 == 1982600 && top.asks[0].shares == 300);
  std::vector<std::uint8_t> execution(31);
  execution[0] = 'E';
  nasdaq::put_u48(execution.data() + 5, 34200001000000ULL);
  flle::put_u64(execution.data() + 11, 1001);
  flle::put_u32(execution.data() + 19, 125);
  flle::put_u64(execution.data() + 23, 777);
  assert(book.apply(execution.data(), execution.size()));
  top = book.top("AAPL");
  assert(top.bids[0].shares == 375 && top.last_x10000 == 1982500 && top.volume == 125);
  std::stringstream checkpoint(std::ios::in | std::ios::out | std::ios::binary);
  assert(book.save_checkpoint(checkpoint) == 2);
  checkpoint.seekg(0);
  nasdaq::ItchBook restored;
  assert(restored.load_checkpoint(checkpoint) == 2);
  const auto restored_top = restored.top("AAPL");
  assert(restored_top.bids[0].price_x10000 == 1982500 && restored_top.bids[0].shares == 375);
  assert(restored_top.asks[0].price_x10000 == 1982600 && restored_top.asks[0].shares == 300);

  nasdaq::EnterOrder enter{123456, nasdaq::Side::Buy, 25, "AAPL", 1982600,
                           '3', 'Y', 'A', 'N', 'N', "FLLE0000123456"};
  const auto encoded_enter = nasdaq::encode_enter(enter);
  assert(encoded_enter.size() == nasdaq::kOuchEnterBytes);
  assert(encoded_enter[0] == 'O' && flle::get_u32(encoded_enter.data() + 1) == 123456);
  nasdaq::EnterOrder decoded_enter;
  assert(nasdaq::decode_enter(encoded_enter.data(), encoded_enter.size(), decoded_enter, error));
  assert(decoded_enter.symbol == "AAPL" && decoded_enter.price_x10000 == 1982600);

  const auto accepted = nasdaq::encode_accepted(
      nasdaq::Accepted{34200002000000ULL, enter, 8888, 'L'});
  const auto executed = nasdaq::encode_executed(
      nasdaq::Executed{34200002010000ULL, enter.user_ref, enter.quantity,
                       1982600, 'A', 9999});
  const auto rejected = nasdaq::encode_rejected(
      nasdaq::Rejected{34200002020000ULL, enter.user_ref, "PX", enter.clordid});
  assert(accepted.size() == nasdaq::kOuchAcceptedBytes);
  assert(executed.size() == nasdaq::kOuchExecutedBytes);
  assert(rejected.size() == nasdaq::kOuchRejectedBytes);
  nasdaq::OuchResponse response;
  assert(nasdaq::decode_response(accepted.data(), accepted.size(), response, error));
  assert(response.type == 'A' && response.order_reference == 8888);
  assert(nasdaq::decode_response(executed.data(), executed.size(), response, error));
  assert(response.type == 'E' && response.price_x10000 == 1982600);
  assert(nasdaq::decode_response(rejected.data(), rejected.size(), response, error));
  assert(response.type == 'J' && response.reason == "PX");

  const auto login = nasdaq::soup_login_request("FLLE01", "PAPER");
  assert(login.size() == nasdaq::kSoupLoginRequestBytes);
  std::cout << "SELFTEST PASS protocol=ITCH5/MoldUDP64+OUCH5/SoupBinTCP"
            << " mold_messages=2 book=AAPL ouch=O/A/E/J\n";
  return 0;
}
