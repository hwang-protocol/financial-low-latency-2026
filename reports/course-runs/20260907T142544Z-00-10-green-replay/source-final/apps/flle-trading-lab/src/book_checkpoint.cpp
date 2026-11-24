#include "itch_book.hpp"

#include <fstream>

namespace nasdaq = flle::nasdaq;

bool read_record(std::ifstream &input, std::vector<std::uint8_t> &message) {
  std::array<std::uint8_t, 2> prefix{};
  input.read(reinterpret_cast<char *>(prefix.data()), prefix.size());
  if (input.gcount() == 0) return false;
  if (input.gcount() != 2) throw std::runtime_error("truncated BinaryFILE prefix");
  const auto length = flle::get_u16(prefix.data());
  if (!length) return read_record(input, message);
  message.resize(length);
  input.read(reinterpret_cast<char *>(message.data()), length);
  if (input.gcount() != length) throw std::runtime_error("truncated BinaryFILE message");
  return true;
}

int main(int argc, char **argv) {
  try {
    if (argc != 4) {
      std::cerr << "usage: flle-book-checkpoint INPUT OUTPUT START_NS\n";
      return 2;
    }
    const auto start_ns = std::stoull(argv[3]);
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) throw std::runtime_error("cannot open replay input");
    nasdaq::ItchBook book;
    std::vector<std::uint8_t> message;
    std::uint64_t messages{};
    while (read_record(input, message)) {
      const auto timestamp = nasdaq::itch_timestamp(message.data(), message.size());
      if (timestamp && *timestamp >= start_ns) break;
      book.apply(message.data(), message.size());
      ++messages;
    }
    std::ofstream output(argv[2], std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot open checkpoint output");
    const auto orders = book.save_checkpoint(output);
    output.close();
    std::cout << "checkpoint=PASS start_ns=" << start_ns
              << " source_messages=" << messages << " active_orders=" << orders << '\n';
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "flle-book-checkpoint: " << error.what() << '\n';
    return 1;
  }
}
