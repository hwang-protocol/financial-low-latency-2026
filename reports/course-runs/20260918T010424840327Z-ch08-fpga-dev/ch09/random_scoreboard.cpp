#include "Vmarket_pipeline.h"
#include "verilated.h"
#include "verilated_cov.h"

#include <cstdint>
#include <cstdlib>
#include <deque>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>

static vluint64_t main_time = 0;

double sc_time_stamp() {
    return static_cast<double>(main_time);
}

struct Message {
    std::uint16_t magic;
    std::uint32_t symbol;
    bool side;
    std::uint32_t price;
    std::uint32_t qty;
    std::uint32_t seq;
};

struct ExpectedOutput {
    Message message;
    std::uint64_t timestamp;
};

class XorShift32 {
  public:
    explicit XorShift32(std::uint32_t seed) : state_(seed == 0 ? 1u : seed) {}

    std::uint32_t next() {
        std::uint32_t value = state_;
        value ^= value << 13;
        value ^= value >> 17;
        value ^= value << 5;
        state_ = value;
        return value;
    }

  private:
    std::uint32_t state_;
};

class ScoreboardFailure : public std::runtime_error {
  public:
    explicit ScoreboardFailure(const std::string& what) : std::runtime_error(what) {}
};

class Simulation {
  public:
    explicit Simulation(std::uint32_t seed) : seed_(seed) {
        dut_.clk = 0;
        dut_.rst_n = 0;
        dut_.cfg_symbol = kAapl;
        dut_.s_valid = 0;
        dut_.m_ready = 0;
        clear_input();
        dut_.eval();
    }

    ~Simulation() {
        dut_.final();
    }

    void reset(unsigned cycles) {
        dut_.rst_n = 0;
        dut_.s_valid = 0;
        dut_.m_ready = 0;
        clear_input();
        for (unsigned index = 0; index < cycles; ++index) {
            raw_tick();
        }
        dut_.rst_n = 1;
        dut_.clk = 0;
        dut_.eval();
        active_cycle_ = 0;
    }

    bool step(const Message* message, bool output_ready) {
        dut_.clk = 0;
        dut_.m_ready = output_ready ? 1 : 0;
        if (message == nullptr) {
            dut_.s_valid = 0;
            clear_input();
        } else {
            dut_.s_valid = 1;
            drive_message(*message);
        }
        dut_.eval();
        main_time += 5;

        check_equal("preedge_fifo_level", expected_.size(), dut_.fifo_level);
        check_equal("preedge_m_valid", expected_.empty() ? 0u : 1u,
                    dut_.m_valid);
        if (!expected_.empty()) {
            check_output(expected_.front());
        }

        const bool input_fire = message != nullptr && dut_.s_ready;
        const bool output_fire = dut_.m_valid && dut_.m_ready;
        const bool input_stall = message != nullptr && !dut_.s_ready;
        const bool output_stall = dut_.m_valid && !dut_.m_ready;

        if (dut_.fifo_level == 4) {
            ++fifo_full_cycles_;
            saw_fifo_full_ = true;
        }
        if (input_stall) {
            ++input_stall_cycles_;
            ++current_input_stall_;
            if (current_input_stall_ > max_input_stall_) {
                max_input_stall_ = current_input_stall_;
            }
        } else {
            current_input_stall_ = 0;
        }
        if (output_stall) {
            ++output_stall_cycles_;
            ++current_output_stall_;
            if (current_output_stall_ > max_output_stall_) {
                max_output_stall_ = current_output_stall_;
            }
        } else {
            current_output_stall_ = 0;
        }
        if (input_fire && output_fire && message != nullptr &&
            message->magic == kMagic && message->symbol == kAapl) {
            ++simultaneous_push_pop_;
        }

        if (output_stall) {
            const ExpectedOutput current = sample_output();
            if (have_stalled_output_) {
                check_expected_output("stall_output_stable", stalled_output_, current);
            }
            stalled_output_ = current;
            have_stalled_output_ = true;
        } else {
            have_stalled_output_ = false;
        }

        if (output_fire) {
            if (expected_.empty()) {
                fail("output_without_reference", "queued", "empty");
            }
            check_output(expected_.front());
            expected_.pop_front();
            ++outputs_;
        }

        if (input_fire) {
            ++accepted_cases_;
            if (message->magic != kMagic) {
                ++bad_magic_;
            } else if (message->symbol != kAapl) {
                ++nonmatch_;
            } else {
                ++matched_valid_;
                expected_.push_back(ExpectedOutput{*message, active_cycle_});
            }
        }

        if (expected_.size() > max_fifo_level_) {
            max_fifo_level_ = expected_.size();
        }
        if (expected_.size() > 4) {
            fail("reference_fifo_bound", "at_most_4", decimal(expected_.size()));
        }

        dut_.clk = 1;
        dut_.eval();
        main_time += 5;
        ++active_cycle_;

        check_equal("postedge_fifo_level", expected_.size(), dut_.fifo_level);
        check_equal("cycle_count", active_cycle_, dut_.cycle_count);
        check_equal("accepted_count", accepted_cases_, dut_.accepted_count);
        check_equal("matched_count", matched_valid_, dut_.matched_count);
        check_equal("bad_magic_count", bad_magic_, dut_.bad_magic_count);
        check_equal("nonmatch_count", nonmatch_, dut_.nonmatch_count);
        check_equal("stall_count", input_stall_cycles_, dut_.stall_count);
        return input_fire;
    }

    void run_directed() {
        Message good1 = make_message(kMagic, kAapl, 1);
        Message bad = make_message(0x0000u, kAapl, 2);
        Message nonmatch = make_message(kMagic, kMsft, 3);
        require_accept(good1, false, "valid");
        require_accept(bad, false, "bad_magic");
        require_accept(nonmatch, false, "nonmatch");
        for (std::uint32_t seq = 4; seq <= 6; ++seq) {
            Message fill = make_message(kMagic, kAapl, seq);
            require_accept(fill, false, "fifo_fill");
        }

        Message held = make_message(kMagic, kAapl, 7);
        for (unsigned cycle = 0; cycle < 20; ++cycle) {
            if (step(&held, false)) {
                fail("directed_long_stall", "not_accepted", "accepted");
            }
        }
        require_accept(held, true, "simultaneous_push_pop");

        while (!expected_.empty()) {
            step(nullptr, true);
        }
    }

    void run_random(std::uint64_t cycles, XorShift32& random) {
        bool have_pending = false;
        Message pending{};
        for (std::uint64_t index = 0; index < cycles; ++index) {
            if (!have_pending && (random.next() % 100u) < 82u) {
                const std::uint32_t category = random.next() % 10u;
                const std::uint16_t magic = category < 6u || category >= 8u
                    ? kMagic
                    : static_cast<std::uint16_t>(random.next() ^ kMagic);
                const std::uint32_t symbol = category >= 8u ? kMsft : kAapl;
                pending = make_message(magic, symbol, next_sequence_++);
                pending.side = (random.next() & 1u) != 0;
                pending.price = 100000u + (random.next() % 900000u);
                pending.qty = 1u + (random.next() % 100000u);
                have_pending = true;
            }

            const bool forced_stall = (index % 257u) < 17u;
            const bool output_ready = !forced_stall && ((random.next() % 100u) < 67u);
            const bool accepted = step(have_pending ? &pending : nullptr,
                                       output_ready);
            if (accepted) {
                have_pending = false;
            }
        }

        std::uint64_t flush_guard = 0;
        while (have_pending) {
            if (step(&pending, true)) {
                have_pending = false;
            }
            if (++flush_guard > 16u) {
                fail("pending_flush_timeout", "at_most_16", decimal(flush_guard));
            }
        }
        while (!expected_.empty()) {
            step(nullptr, true);
            if (++flush_guard > cycles + 32u) {
                fail("fifo_drain_timeout", "bounded", decimal(flush_guard));
            }
        }
    }

    void validate_coverage_contract() {
        require("saw_valid", matched_valid_ > 0);
        require("saw_bad_magic", bad_magic_ > 0);
        require("saw_nonmatch", nonmatch_ > 0);
        require("saw_fifo_full", saw_fifo_full_);
        require("saw_input_stall", input_stall_cycles_ > 0);
        require("saw_output_stall", output_stall_cycles_ > 0);
        require("saw_long_input_stall", max_input_stall_ >= 16);
        require("saw_simultaneous_push_pop", simultaneous_push_pop_ > 0);
        require("max_fifo_exactly_four", max_fifo_level_ == 4);
        require("all_matched_emitted", outputs_ == matched_valid_);
        require("reference_empty", expected_.empty());
    }

    void emit_json(std::uint64_t requested_random_cycles,
                   const std::string& coverage_path) const {
        std::cout
            << "{\"status\":\"PASS\""
            << ",\"seed_hex\":\"0x" << std::hex << std::setw(8)
            << std::setfill('0') << seed_ << std::dec << "\""
            << ",\"seed_u32\":" << seed_
            << ",\"requested_random_cycles\":" << requested_random_cycles
            << ",\"active_cycles\":" << active_cycle_
            << ",\"accepted_cases\":" << accepted_cases_
            << ",\"matched_valid\":" << matched_valid_
            << ",\"bad_magic\":" << bad_magic_
            << ",\"nonmatch\":" << nonmatch_
            << ",\"semantic_drops\":" << (bad_magic_ + nonmatch_)
            << ",\"outputs\":" << outputs_
            << ",\"fifo_full_cycles\":" << fifo_full_cycles_
            << ",\"input_stall_cycles\":" << input_stall_cycles_
            << ",\"output_stall_cycles\":" << output_stall_cycles_
            << ",\"max_input_stall\":" << max_input_stall_
            << ",\"max_output_stall\":" << max_output_stall_
            << ",\"simultaneous_push_pop\":" << simultaneous_push_pop_
            << ",\"max_fifo_level\":" << max_fifo_level_
            << ",\"scoreboard_checks\":" << scoreboard_checks_
            << ",\"coverage_file\":\"" << coverage_path << "\"}\n";
    }

    static constexpr std::uint16_t kMagic = 0x4d44;
    static constexpr std::uint32_t kAapl = 0x4141504c;
    static constexpr std::uint32_t kMsft = 0x4d534654;

  private:
    Vmarket_pipeline dut_;
    std::deque<ExpectedOutput> expected_;
    std::uint32_t seed_;
    std::uint32_t next_sequence_ = 1000;
    std::uint64_t active_cycle_ = 0;
    std::uint64_t accepted_cases_ = 0;
    std::uint64_t matched_valid_ = 0;
    std::uint64_t bad_magic_ = 0;
    std::uint64_t nonmatch_ = 0;
    std::uint64_t outputs_ = 0;
    std::uint64_t fifo_full_cycles_ = 0;
    std::uint64_t input_stall_cycles_ = 0;
    std::uint64_t output_stall_cycles_ = 0;
    std::uint64_t current_input_stall_ = 0;
    std::uint64_t current_output_stall_ = 0;
    std::uint64_t max_input_stall_ = 0;
    std::uint64_t max_output_stall_ = 0;
    std::uint64_t simultaneous_push_pop_ = 0;
    std::uint64_t scoreboard_checks_ = 0;
    std::size_t max_fifo_level_ = 0;
    bool saw_fifo_full_ = false;
    bool have_stalled_output_ = false;
    ExpectedOutput stalled_output_{};

    static std::string decimal(std::uint64_t value) {
        std::ostringstream stream;
        stream << value;
        return stream.str();
    }

    [[noreturn]] void fail(const std::string& name,
                           const std::string& expected,
                           const std::string& actual) const {
        std::cerr << "SCOREBOARD_FAIL name=" << name
                  << " seed=0x" << std::hex << std::setw(8)
                  << std::setfill('0') << seed_ << std::dec
                  << " cycle=" << active_cycle_
                  << " expected=" << expected
                  << " actual=" << actual << '\n';
        throw ScoreboardFailure(name);
    }

    void require(const std::string& name, bool condition) const {
        if (!condition) {
            fail(name, "true", "false");
        }
    }

    template <typename Expected, typename Actual>
    void check_equal(const std::string& name, Expected expected, Actual actual) {
        ++scoreboard_checks_;
        const std::uint64_t expected_value = static_cast<std::uint64_t>(expected);
        const std::uint64_t actual_value = static_cast<std::uint64_t>(actual);
        if (expected_value != actual_value) {
            fail(name, decimal(expected_value), decimal(actual_value));
        }
    }

    void check_expected_output(const std::string& prefix,
                               const ExpectedOutput& expected,
                               const ExpectedOutput& actual) {
        // Sequence is the canonical ordering key, so report a reorder with the
        // most precise marker before checking the remaining payload fields.
        check_equal(prefix + "_seq", expected.message.seq,
                    actual.message.seq);
        check_equal(prefix + "_symbol", expected.message.symbol,
                    actual.message.symbol);
        check_equal(prefix + "_side", expected.message.side,
                    actual.message.side);
        check_equal(prefix + "_price", expected.message.price,
                    actual.message.price);
        check_equal(prefix + "_qty", expected.message.qty,
                    actual.message.qty);
        check_equal(prefix + "_timestamp", expected.timestamp,
                    actual.timestamp);
    }

    void check_output(const ExpectedOutput& expected) {
        check_expected_output("output", expected, sample_output());
    }

    ExpectedOutput sample_output() const {
        Message message{
            kMagic,
            dut_.m_symbol,
            dut_.m_side != 0,
            dut_.m_price,
            dut_.m_qty,
            dut_.m_seq};
        return ExpectedOutput{message, dut_.m_timestamp};
    }

    Message make_message(std::uint16_t magic, std::uint32_t symbol,
                         std::uint32_t seq) const {
        return Message{magic, symbol, (seq & 1u) != 0,
                       100000u + seq * 17u, 1u + seq * 3u, seq};
    }

    void require_accept(const Message& message, bool output_ready,
                        const std::string& name) {
        if (!step(&message, output_ready)) {
            fail(name, "accepted", "stalled");
        }
    }

    void raw_tick() {
        dut_.clk = 0;
        dut_.eval();
        main_time += 5;
        dut_.clk = 1;
        dut_.eval();
        main_time += 5;
    }

    void clear_input() {
        for (int word = 0; word < 5; ++word) {
            dut_.s_data[word] = 0;
        }
    }

    void drive_message(const Message& message) {
        dut_.s_data[0] = message.seq;
        dut_.s_data[1] = message.qty;
        dut_.s_data[2] = message.price;
        dut_.s_data[3] = ((message.symbol & 0xffffu) << 16)
                       | (message.side ? 0x00008000u : 0u);
        dut_.s_data[4] = (static_cast<std::uint32_t>(message.magic) << 16)
                       | ((message.symbol >> 16) & 0xffffu);
    }
};

static std::uint64_t parse_u64(const char* text, const char* name) {
    char* end = nullptr;
    const unsigned long long value = std::strtoull(text, &end, 0);
    if (text[0] == '\0' || end == nullptr || *end != '\0') {
        std::cerr << "ARGUMENT_FAIL name=" << name << " value=" << text << '\n';
        std::exit(64);
    }
    return static_cast<std::uint64_t>(value);
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc != 4) {
        std::cerr << "usage: " << argv[0]
                  << " SEED RANDOM_CYCLES COVERAGE_PATH\n";
        return 64;
    }

    const std::uint64_t parsed_seed = parse_u64(argv[1], "seed");
    const std::uint64_t random_cycles = parse_u64(argv[2], "random_cycles");
    if (parsed_seed > std::numeric_limits<std::uint32_t>::max() ||
        random_cycles < 4096u) {
        std::cerr << "ARGUMENT_FAIL seed_must_fit_u32_and_cycles_must_be_at_least_4096\n";
        return 64;
    }

    try {
        const std::uint32_t seed = static_cast<std::uint32_t>(parsed_seed);
        XorShift32 random(seed);
        Simulation simulation(seed);
        simulation.reset(4);
        simulation.run_directed();
        simulation.run_random(random_cycles, random);
        simulation.validate_coverage_contract();
        VerilatedCov::write(argv[3]);
        simulation.emit_json(random_cycles, argv[3]);
    } catch (const ScoreboardFailure&) {
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "HARNESS_FAIL what=" << error.what() << '\n';
        return 3;
    }
    return 0;
}
