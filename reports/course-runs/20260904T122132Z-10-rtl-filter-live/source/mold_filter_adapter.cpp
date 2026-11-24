#include "Vmarket_filter.h"
#include "verilated.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <array>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

constexpr const char *MULTICAST_GROUP = "239.20.1.20";
constexpr const char *BIND_IP = "20.1.1.2";
constexpr const char *TRADER_IP = "20.1.1.2";
constexpr std::uint16_t MULTICAST_PORT = 42120;
constexpr std::uint16_t AUTO_PORT = 42121;
constexpr std::uint16_t NVDA_LOCATE = 8095;
constexpr std::uint64_t NVDA_STOCK = 0x4e56444120202020ULL;
constexpr std::size_t MOLD_HEADER_LEN = 20;
constexpr std::size_t ITCH_ADD_LEN = 36;
constexpr std::size_t SINGLE_ADD_PAYLOAD_LEN = MOLD_HEADER_LEN + 2 + ITCH_ADD_LEN;
constexpr auto POLICY_TTL = std::chrono::seconds(5);
constexpr const char *CONTROL_PATH = "/var/tmp/flle-market-filter.cmd";

std::atomic<bool> g_stop{false};

void on_signal(int) { g_stop = true; }

std::uint16_t read_be16(const std::uint8_t *bytes) {
    return static_cast<std::uint16_t>((bytes[0] << 8) | bytes[1]);
}

std::uint64_t read_be64(const std::uint8_t *bytes) {
    std::uint64_t value = 0;
    for (int index = 0; index < 8; ++index)
        value = (value << 8) | bytes[index];
    return value;
}

int open_multicast() {
    const int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) throw std::runtime_error("multicast socket failed");
    int one = 1;
    ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(MULTICAST_PORT);
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    if (::bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0)
        throw std::runtime_error("multicast bind failed");
    ip_mreq group{};
    ::inet_pton(AF_INET, MULTICAST_GROUP, &group.imr_multiaddr);
    ::inet_pton(AF_INET, BIND_IP, &group.imr_interface);
    if (::setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &group, sizeof(group)) < 0)
        throw std::runtime_error("IP_ADD_MEMBERSHIP failed");
    return fd;
}

int open_unicast() {
    const int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) throw std::runtime_error("unicast socket failed");
    return fd;
}

void send_copy(int fd, std::uint16_t port, const std::uint8_t *data, ssize_t length) {
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    ::inet_pton(AF_INET, TRADER_IP, &address.sin_addr);
    const auto sent = ::sendto(fd, data, static_cast<std::size_t>(length), 0,
                               reinterpret_cast<sockaddr *>(&address), sizeof(address));
    if (sent != length) throw std::runtime_error("unicast forward failed");
}

void clear_itch(Vmarket_filter &dut) {
    for (int word = 0; word < 9; ++word) dut.s_itch[word] = 0;
}

void drive_itch(Vmarket_filter &dut, const std::uint8_t *itch, std::uint64_t sequence) {
    clear_itch(dut);
    for (int byte_index = 0; byte_index < 36; ++byte_index) {
        const int bit_lo = 280 - 8 * byte_index;
        const int word = bit_lo / 32;
        const int shift = bit_lo % 32;
        dut.s_itch[word] |= static_cast<std::uint32_t>(itch[byte_index]) << shift;
    }
    dut.s_mold_seq = sequence;
}

void tick(Vmarket_filter &dut) {
    dut.clk = 0;
    dut.eval();
    dut.clk = 1;
    dut.eval();
}

void load_remaining(Vmarket_filter &dut, std::uint32_t remaining) {
    dut.cfg_load_drops = remaining;
    dut.cfg_load_valid = 1;
    tick(dut);
    dut.cfg_load_valid = 0;
    tick(dut);
}

bool clock_filter(Vmarket_filter &dut, const std::uint8_t *itch, std::uint64_t sequence) {
    dut.s_valid = 1;
    drive_itch(dut, itch, sequence);
    tick(dut);
    const bool drop = dut.drop_valid != 0;
    dut.s_valid = 0;
    clear_itch(dut);
    tick(dut);
    return drop;
}

void reset_filter(Vmarket_filter &dut) {
    dut.clk = 0;
    dut.rst_n = 0;
    dut.s_valid = 0;
    dut.cfg_load_valid = 0;
    dut.cfg_locate = NVDA_LOCATE;
    dut.cfg_stock = NVDA_STOCK;
    clear_itch(dut);
    tick(dut);
    tick(dut);
    dut.rst_n = 1;
    tick(dut);
}

void run_selftest() {
    Vmarket_filter dut;
    reset_filter(dut);
    std::array<std::uint8_t, ITCH_ADD_LEN> add{};
    add[0] = 'A';
    add[1] = static_cast<std::uint8_t>(NVDA_LOCATE >> 8);
    add[2] = static_cast<std::uint8_t>(NVDA_LOCATE);
    std::memcpy(add.data() + 24, "NVDA    ", 8);
    load_remaining(dut, 0);
    if (clock_filter(dut, add.data(), 100))
        throw std::runtime_error("allow verdict failed");
    load_remaining(dut, 1);
    if (!clock_filter(dut, add.data(), 101) || dut.remaining_drops != 0)
        throw std::runtime_error("one-shot drop verdict failed");
    if (clock_filter(dut, add.data(), 102))
        throw std::runtime_error("one-shot policy dropped twice");
    add[2] ^= 1;
    load_remaining(dut, 1);
    if (clock_filter(dut, add.data(), 103) || dut.remaining_drops != 1)
        throw std::runtime_error("non-target verdict failed");
    dut.final();
    std::cout << "rtl_selftest=PASS allow=1 target_drop=1 second_pass=1 non_target_pass=1"
              << std::endl;
}

void run_adapter(const std::string &mode, std::uint32_t remaining_drops) {
    Vmarket_filter dut;
    reset_filter(dut);
    load_remaining(dut, mode == "block" ? remaining_drops : 0);
    bool armed = mode == "block";
    auto deadline = std::chrono::steady_clock::now() + POLICY_TTL;

    const int multicast = open_multicast();
    const int unicast = open_unicast();
    std::uint8_t buffer[65536];
    std::uint64_t received = 0;
    std::uint64_t forwarded = 0;
    std::uint64_t dropped = 0;
    std::cout << "adapter_ready mode=" << mode
              << " remaining_drops=" << dut.remaining_drops << std::endl;
    while (!g_stop.load()) {
        {
            std::ifstream control(CONTROL_PATH);
            std::string command;
            if (control >> command) {
                ::unlink(CONTROL_PATH);
                if (command == "block") {
                    if (remaining_drops != 1)
                        throw std::runtime_error("classroom policy must be one-shot");
                    load_remaining(dut, 1);
                    armed = true;
                    deadline = std::chrono::steady_clock::now() + POLICY_TTL;
                    std::cout << "adapter_arm remaining_drops=" << dut.remaining_drops
                              << " ttl_ms=5000" << std::endl;
                } else if (command == "allow") {
                    load_remaining(dut, 0);
                    armed = false;
                    std::cout << "adapter_allow" << std::endl;
                } else {
                    throw std::runtime_error("unknown filter command");
                }
            }
        }
        if (armed && std::chrono::steady_clock::now() >= deadline) {
            load_remaining(dut, 0);
            armed = false;
            std::cout << "adapter_policy_expired" << std::endl;
        }
        pollfd descriptor{multicast, POLLIN, 0};
        const int ready = ::poll(&descriptor, 1, 100);
        if (ready < 0) {
            if (errno == EINTR) continue;
            throw std::runtime_error("multicast poll failed");
        }
        if (ready == 0 || !(descriptor.revents & POLLIN)) continue;
        const ssize_t length = ::recv(multicast, buffer, sizeof(buffer), 0);
        if (length < 0) {
            if (errno == EINTR) continue;
            throw std::runtime_error("multicast receive failed");
        }
        if (length < static_cast<ssize_t>(MOLD_HEADER_LEN)) continue;
        ++received;
        bool drop = false;
        std::uint64_t sequence = read_be64(buffer + 10);
        const std::uint16_t count = read_be16(buffer + 18);
        if (count == 1 && length == static_cast<ssize_t>(SINGLE_ADD_PAYLOAD_LEN)) {
            const std::uint16_t itch_len = read_be16(buffer + MOLD_HEADER_LEN);
            const std::uint8_t *itch = buffer + MOLD_HEADER_LEN + 2;
            if (itch_len == ITCH_ADD_LEN && itch[0] == 'A') {
                drop = clock_filter(dut, itch, sequence);
            }
        }
        if (drop) {
            armed = false;
            ++dropped;
            std::cout << "rtl_drop sequence=" << sequence
                      << " remaining=" << dut.remaining_drops
                      << " drop_count=" << dut.drop_count << std::endl;
            continue;
        }
        send_copy(unicast, AUTO_PORT, buffer, length);
        ++forwarded;
    }
    ::close(multicast);
    ::close(unicast);
    dut.final();
    std::cout << "adapter_stop received=" << received
              << " forwarded=" << forwarded
              << " dropped=" << dropped << std::endl;
}

}  // namespace

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    if (argc == 2 && std::string(argv[1]) == "--selftest") {
        run_selftest();
        return 0;
    }
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
    const char *mode = std::getenv("FLLE_FILTER_MODE");
    const char *remaining = std::getenv("FLLE_REMAINING_DROPS");
    run_adapter(mode ? mode : "allow", remaining ? static_cast<std::uint32_t>(std::stoul(remaining)) : 1);
    return 0;
}
