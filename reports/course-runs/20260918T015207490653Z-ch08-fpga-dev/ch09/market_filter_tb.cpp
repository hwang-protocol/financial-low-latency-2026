// Offline checks for the current message-verdict RTL. No sockets or live feed.
#include "Vmarket_filter.h"
#include "verilated.h"

#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
using Message = std::array<std::uint8_t, 36>;
constexpr std::uint16_t kLocate = 8095;
constexpr std::uint64_t kStock = 0x4e56444120202020ULL;

void require(bool condition, const std::string &name) {
    if (!condition) throw std::runtime_error(name);
}

Message target() {
    Message message{};
    message[0] = 'A';
    message[1] = static_cast<std::uint8_t>(kLocate >> 8);
    message[2] = static_cast<std::uint8_t>(kLocate);
    const char stock[] = "NVDA    ";
    for (unsigned i = 0; i < 8; ++i) message[24 + i] = stock[i];
    return message;
}

class Test {
  public:
    Vmarket_filter dut;
    unsigned cases = 0;

    Test() {
        dut.clk = 0;
        dut.rst_n = 0;
        dut.s_valid = 0;
        dut.s_mold_seq = 0;
        dut.cfg_load_valid = 0;
        dut.cfg_load_drops = 0;
        dut.cfg_locate = kLocate;
        dut.cfg_stock = kStock;
        for (unsigned word = 0; word < 9; ++word) dut.s_itch[word] = 0;
        tick();
    }
    ~Test() { dut.final(); }

    void tick() {
        dut.clk = 0;
        dut.eval();
        dut.clk = 1;
        dut.eval();
    }

    void input(const Message &message, std::uint64_t sequence) {
        for (unsigned word = 0; word < 9; ++word) dut.s_itch[word] = 0;
        for (unsigned i = 0; i < message.size(); ++i) {
            const unsigned bit = (35 - i) * 8;
            dut.s_itch[bit / 32] |= std::uint32_t(message[i]) << (bit % 32);
        }
        dut.s_mold_seq = sequence;
        dut.s_valid = 1;
    }

    void state(unsigned remaining, unsigned passed, unsigned dropped,
               bool pass, bool drop, std::uint64_t sequence) {
        require(dut.remaining_drops == remaining, "remaining_drops");
        require(dut.pass_count == passed, "pass_count");
        require(dut.drop_count == dropped, "drop_count");
        require(bool(dut.m_valid) == pass, "m_valid");
        require(bool(dut.drop_valid) == drop, "drop_valid");
        require(dut.m_mold_seq == sequence, "m_mold_seq (all 64 bits)");
        require(!(dut.m_valid && dut.drop_valid), "verdicts must be exclusive");
    }

    void load(unsigned remaining) {
        dut.s_valid = 0;
        dut.cfg_load_valid = 1;
        dut.cfg_load_drops = remaining;
        dut.clk = 0;
        dut.eval();
        require(!dut.s_ready, "configuration must block input");
        tick();
        require(!dut.m_valid && !dut.drop_valid, "configuration produced verdict");
        dut.cfg_load_valid = 0;
        dut.eval();
        require(dut.s_ready, "input did not resume after configuration");
    }

    void passed(const char *name) {
        ++cases;
        std::cout << "CASE_PASS " << name << '\n';
    }
};
}  // namespace

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    try {
        Test test;
        auto &dut = test.dut;
        const Message nvda = target();
        test.state(0, 0, 0, false, false, 0);
        test.passed("reset_clears_state");
        dut.rst_n = 1;

        constexpr std::uint64_t first = 0x1234567800000064ULL;
        test.input(nvda, first);
        test.tick();
        test.state(0, 1, 0, true, false, first);
        test.passed("default_allow_and_full_sequence");

        // Keep an input pending during configuration. It must not be accepted.
        test.input(nvda, 200);
        dut.cfg_load_valid = 1;
        dut.cfg_load_drops = 1;
        dut.clk = 0;
        dut.eval();
        require(!dut.s_ready, "pending input acknowledged during configuration");
        test.tick();
        test.state(1, 1, 0, false, false, first);
        test.passed("configuration_preempts_pending_input");

        dut.cfg_load_valid = 0;
        test.tick();
        test.state(0, 1, 1, false, true, 200);
        test.passed("held_input_consumes_one_credit");
        test.input(nvda, 201);
        test.tick();
        test.state(0, 2, 1, true, false, 201);
        test.passed("next_cycle_target_passes");
        dut.s_valid = 0;
        test.tick();
        test.state(0, 2, 1, false, false, 201);
        test.passed("idle_clears_verdict_without_recounting");

        test.load(1);
        for (unsigned changed = 0; changed < 4; ++changed) {
            Message other = nvda;
            const unsigned byte[] = {0, 2, 27, 31};
            other[byte[changed]] ^= 1;
            test.input(other, 300 + changed);
            test.tick();
            test.state(1, 3 + changed, 1, true, false, 300 + changed);
            const char *name[] = {"type_mismatch_keeps_credit", "locate_mismatch_keeps_credit",
                                  "stock_mismatch_keeps_credit", "padding_mismatch_keeps_credit"};
            test.passed(name[changed]);
        }

        constexpr std::uint64_t last = 0xfedcba9876543210ULL;
        test.input(nvda, last);
        test.tick();
        test.state(0, 6, 2, false, true, last);
        test.passed("target_after_nonmatches_drops_full_sequence");

        test.load(1);
        test.load(0);
        test.input(nvda, 304);
        test.tick();
        test.state(0, 7, 2, true, false, 304);
        test.passed("explicit_zero_disarms");

        // Reset wins over both a configuration write and a pending message.
        dut.rst_n = 0;
        dut.cfg_load_valid = 1;
        dut.cfg_load_drops = 1;
        test.input(nvda, 305);
        test.tick();
        test.state(0, 0, 0, false, false, 0);
        test.passed("reset_wins_over_configuration_and_input");
        dut.rst_n = 1;
        dut.cfg_load_valid = 0;
        dut.s_valid = 0;
        test.tick();
        test.state(0, 0, 0, false, false, 0);
        test.input(nvda, 306);
        test.tick();
        test.state(0, 1, 0, true, false, 306);
        test.passed("first_target_after_reset_passes");

        std::cout << "RTL_OFFLINE_REGRESSION=PASS cases=" << test.cases
                  << " network=NOT_USED hardware=NOT_RUN\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "RTL_OFFLINE_REGRESSION=FAIL " << error.what() << '\n';
        return 1;
    }
}
