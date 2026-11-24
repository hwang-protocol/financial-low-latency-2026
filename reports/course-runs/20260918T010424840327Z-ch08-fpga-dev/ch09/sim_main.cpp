#include "Vmarket_pipeline.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

#include <cstdint>
#include <cstdlib>
#include <deque>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

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

struct StepResult {
    bool input_fire;
    bool output_fire;
};

struct OutputSnapshot {
    std::uint32_t symbol;
    bool side;
    std::uint32_t price;
    std::uint32_t qty;
    std::uint32_t seq;
    std::uint64_t timestamp;
};

static std::string value_string(std::uint64_t value) {
    std::ostringstream stream;
    stream << value;
    return stream.str();
}

class Simulation {
  public:
    explicit Simulation(const std::string& vcd_path) {
        Verilated::traceEverOn(true);
        dut_.trace(&trace_, 99);
        trace_.open(vcd_path.c_str());
        dut_.clk = 0;
        dut_.rst_n = 0;
        dut_.cfg_symbol = kAapl;
        dut_.s_valid = 0;
        dut_.m_ready = 0;
        clear_input();
    }

    ~Simulation() {
        dut_.final();
        trace_.close();
    }

    void reset(unsigned cycles) {
        dut_.rst_n = 0;
        dut_.s_valid = 0;
        dut_.m_ready = 0;
        clear_input();
        for (unsigned i = 0; i < cycles; ++i) {
            raw_tick();
        }
        dut_.rst_n = 1;
        active_cycle_ = 0;
        std::cout << "ASSERT_PASS name=reset_cycles expected=" << cycles
                  << " actual=" << cycles << '\n';
    }

    void set_symbol(std::uint32_t symbol) {
        dut_.cfg_symbol = symbol;
        std::cout << "CONFIG symbol=0x" << std::hex << std::setw(8)
                  << std::setfill('0') << symbol << std::dec << '\n';
    }

    StepResult step(const Message* message, bool output_ready) {
        dut_.clk = 0;
        dut_.m_ready = output_ready ? 1 : 0;
        if (message != nullptr) {
            dut_.s_valid = 1;
            drive_message(*message);
        } else {
            dut_.s_valid = 0;
            clear_input();
        }
        dut_.eval();
        trace_.dump(main_time);
        main_time += 5;

        assert_equal("preedge_m_valid", expected_.empty() ? 0 : 1,
                     static_cast<std::uint64_t>(dut_.m_valid));
        if (!expected_.empty()) {
            assert_output_matches(expected_.front(), false);
        }

        const bool input_fire = (message != nullptr) && dut_.s_ready;
        const bool output_fire = dut_.m_valid && dut_.m_ready;

        if (message != nullptr && !dut_.s_ready) {
            ++model_stall_count_;
            ++input_backpressure_observations_;
        }

        if (dut_.m_valid && !dut_.m_ready) {
            const OutputSnapshot current = output_snapshot();
            if (have_stalled_snapshot_) {
                assert_snapshot_equal(stalled_snapshot_, current);
                ++stalled_head_checks_;
            }
            stalled_snapshot_ = current;
            have_stalled_snapshot_ = true;
        } else {
            have_stalled_snapshot_ = false;
        }

        if (output_fire) {
            if (expected_.empty()) {
                fail("output_fire_without_expected", "queued output", "empty");
            }
            const ExpectedOutput expected_output = expected_.front();
            assert_output_matches(expected_output, true);
            output_sequences_.push_back(dut_.m_seq);
            output_timestamps_.push_back(dut_.m_timestamp);
            expected_.pop_front();
            ++output_count_;
        }

        if (input_fire) {
            ++model_accepted_count_;
            if (message->magic != kMagic) {
                ++model_bad_magic_count_;
            } else if (message->symbol != dut_.cfg_symbol) {
                ++model_nonmatch_count_;
            } else {
                ++model_matched_count_;
                expected_.push_back(ExpectedOutput{*message, active_cycle_});
                accepted_match_cycles_.push_back(active_cycle_);
            }
        }

        if (expected_.size() > max_fifo_level_) {
            max_fifo_level_ = expected_.size();
        }

        dut_.clk = 1;
        dut_.eval();
        trace_.dump(main_time);
        main_time += 5;
        ++active_cycle_;

        assert_equal("fifo_level", expected_.size(), dut_.fifo_level);
        assert_equal("cycle_count", active_cycle_, dut_.cycle_count);
        assert_equal("accepted_count", model_accepted_count_, dut_.accepted_count);
        assert_equal("matched_count", model_matched_count_, dut_.matched_count);
        assert_equal("bad_magic_count", model_bad_magic_count_, dut_.bad_magic_count);
        assert_equal("nonmatch_count", model_nonmatch_count_, dut_.nonmatch_count);
        assert_equal("stall_count", model_stall_count_, dut_.stall_count);

        return StepResult{input_fire, output_fire};
    }

    void require_fire(const Message& message, bool output_ready,
                      const std::string& case_name) {
        const StepResult result = step(&message, output_ready);
        assert_equal(case_name + "_input_fire", 1, result.input_fire ? 1 : 0);
        ++packet_case_count_;
        std::cout << "CASE_PASS name=" << case_name << " seq=" << message.seq
                  << " accepted_at_cycle=" << (active_cycle_ - 1) << '\n';
    }

    void require_stall(const Message& message, const std::string& case_name) {
        const StepResult result = step(&message, false);
        assert_equal(case_name + "_input_fire", 0, result.input_fire ? 1 : 0);
        std::cout << "STALL_PASS name=" << case_name << " seq=" << message.seq
                  << " stalled_at_cycle=" << (active_cycle_ - 1) << '\n';
    }

    void drain() {
        while (!expected_.empty()) {
            step(nullptr, true);
        }
    }

    void finish_checks() {
        const std::vector<std::uint32_t> expected_sequences{
            1, 10, 11, 12, 13, 14, 15, 20};
        const std::vector<std::uint64_t> expected_timestamps{
            2, 4, 5, 6, 7, 13, 14, 20};

        assert_vector_equal("output_sequences", expected_sequences, output_sequences_);
        assert_vector_equal("output_timestamps", expected_timestamps, output_timestamps_);
        for (std::size_t i = 1; i < output_timestamps_.size(); ++i) {
            if (output_timestamps_[i] <= output_timestamps_[i - 1]) {
                fail("timestamp_monotonic", "strictly increasing",
                     value_string(output_timestamps_[i]));
            }
        }
        std::cout << "ASSERT_PASS name=timestamp_monotonic expected=strictly_increasing"
                  << " actual=strictly_increasing\n";

        assert_equal_report("packet_case_count", 13, packet_case_count_);
        assert_equal_report("accepted_count_final", 13, model_accepted_count_);
        assert_equal_report("matched_count_final", 8, model_matched_count_);
        assert_equal_report("bad_magic_count_final", 2, model_bad_magic_count_);
        assert_equal_report("nonmatch_count_final", 3, model_nonmatch_count_);
        assert_equal_report("stall_count_final", 3, model_stall_count_);
        assert_equal_report("output_count_final", 8, output_count_);
        assert_equal_report("max_fifo_level", 4, max_fifo_level_);
        assert_equal_report("input_backpressure_observations", 3,
                            input_backpressure_observations_);
        assert_equal_report("stalled_head_checks", 7, stalled_head_checks_);
        assert_equal_report("active_cycles", 22, active_cycle_);

        assert_equal_report("initial_burst_cycle_0", 4,
                            accepted_match_cycles_.at(1));
        assert_equal_report("initial_burst_cycle_1", 5,
                            accepted_match_cycles_.at(2));
        assert_equal_report("initial_burst_cycle_2", 6,
                            accepted_match_cycles_.at(3));
        assert_equal_report("initial_burst_cycle_3", 7,
                            accepted_match_cycles_.at(4));

        std::cout
            << "VERILATOR_MARKET_PIPELINE_PASS"
            << " cases=13 accepted=13 matched=8 bad_magic=2 nonmatch=3"
            << " outputs=8 stall_cycles=3 max_fifo=4"
            << " first_timestamp=2 last_timestamp=20 active_cycles=22\n";
    }

    static constexpr std::uint16_t kMagic = 0x4d44;
    static constexpr std::uint32_t kAapl = 0x4141504c;
    static constexpr std::uint32_t kMsft = 0x4d534654;

  private:
    Vmarket_pipeline dut_;
    VerilatedVcdC trace_;
    std::deque<ExpectedOutput> expected_;
    std::uint64_t active_cycle_ = 0;
    std::uint64_t model_accepted_count_ = 0;
    std::uint64_t model_matched_count_ = 0;
    std::uint64_t model_bad_magic_count_ = 0;
    std::uint64_t model_nonmatch_count_ = 0;
    std::uint64_t model_stall_count_ = 0;
    std::uint64_t output_count_ = 0;
    std::uint64_t packet_case_count_ = 0;
    std::uint64_t input_backpressure_observations_ = 0;
    std::uint64_t stalled_head_checks_ = 0;
    std::size_t max_fifo_level_ = 0;
    bool have_stalled_snapshot_ = false;
    OutputSnapshot stalled_snapshot_{};
    std::vector<std::uint32_t> output_sequences_;
    std::vector<std::uint64_t> output_timestamps_;
    std::vector<std::uint64_t> accepted_match_cycles_;

    void raw_tick() {
        dut_.clk = 0;
        dut_.eval();
        trace_.dump(main_time);
        main_time += 5;
        dut_.clk = 1;
        dut_.eval();
        trace_.dump(main_time);
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

    OutputSnapshot output_snapshot() const {
        return OutputSnapshot{
            dut_.m_symbol,
            dut_.m_side != 0,
            dut_.m_price,
            dut_.m_qty,
            dut_.m_seq,
            dut_.m_timestamp};
    }

    void assert_output_matches(const ExpectedOutput& expected_output, bool emit) {
        const OutputSnapshot actual = output_snapshot();
        const Message& expected_message = expected_output.message;
        assert_equal("output_symbol", expected_message.symbol, actual.symbol);
        assert_equal("output_side", expected_message.side ? 1 : 0,
                     actual.side ? 1 : 0);
        assert_equal("output_price", expected_message.price, actual.price);
        assert_equal("output_qty", expected_message.qty, actual.qty);
        assert_equal("output_seq", expected_message.seq, actual.seq);
        assert_equal("output_timestamp", expected_output.timestamp, actual.timestamp);
        if (emit) {
            std::cout << "ASSERT_OUTPUT_PASS index=" << output_count_
                      << " expected_seq=" << expected_message.seq
                      << " actual_seq=" << actual.seq
                      << " expected_symbol=" << expected_message.symbol
                      << " actual_symbol=" << actual.symbol
                      << " expected_side=" << (expected_message.side ? 1 : 0)
                      << " actual_side=" << (actual.side ? 1 : 0)
                      << " expected_price=" << expected_message.price
                      << " actual_price=" << actual.price
                      << " expected_qty=" << expected_message.qty
                      << " actual_qty=" << actual.qty
                      << " expected_timestamp=" << expected_output.timestamp
                      << " actual_timestamp=" << actual.timestamp << '\n';
        }
    }

    void assert_snapshot_equal(const OutputSnapshot& expected,
                               const OutputSnapshot& actual) {
        assert_equal("stalled_symbol_stable", expected.symbol, actual.symbol);
        assert_equal("stalled_side_stable", expected.side ? 1 : 0,
                     actual.side ? 1 : 0);
        assert_equal("stalled_price_stable", expected.price, actual.price);
        assert_equal("stalled_qty_stable", expected.qty, actual.qty);
        assert_equal("stalled_seq_stable", expected.seq, actual.seq);
        assert_equal("stalled_timestamp_stable", expected.timestamp, actual.timestamp);
    }

    template <typename Expected, typename Actual>
    void assert_equal(const std::string& name, Expected expected, Actual actual) const {
        const std::uint64_t expected_value = static_cast<std::uint64_t>(expected);
        const std::uint64_t actual_value = static_cast<std::uint64_t>(actual);
        if (expected_value != actual_value) {
            fail(name, value_string(expected_value), value_string(actual_value));
        }
    }

    template <typename Expected, typename Actual>
    void assert_equal_report(const std::string& name,
                             Expected expected,
                             Actual actual) const {
        assert_equal(name, expected, actual);
        std::cout << "ASSERT_PASS name=" << name
                  << " expected=" << static_cast<std::uint64_t>(expected)
                  << " actual=" << static_cast<std::uint64_t>(actual) << '\n';
    }

    template <typename T>
    void assert_vector_equal(const std::string& name,
                             const std::vector<T>& expected,
                             const std::vector<T>& actual) const {
        if (expected.size() != actual.size()) {
            fail(name + "_size", value_string(expected.size()),
                 value_string(actual.size()));
        }
        for (std::size_t i = 0; i < expected.size(); ++i) {
            if (expected[i] != actual[i]) {
                fail(name + "_index_" + value_string(i),
                     value_string(expected[i]), value_string(actual[i]));
            }
        }
        std::cout << "ASSERT_PASS name=" << name
                  << " expected_count=" << expected.size()
                  << " actual_count=" << actual.size() << '\n';
    }

    [[noreturn]] void fail(const std::string& name,
                           const std::string& expected,
                           const std::string& actual) const {
        std::ostringstream stream;
        stream << "ASSERT_FAIL name=" << name
               << " expected=" << expected
               << " actual=" << actual
               << " active_cycle=" << active_cycle_;
        throw std::runtime_error(stream.str());
    }
};

static Message message(std::uint16_t magic, std::uint32_t symbol, bool side,
                       std::uint32_t price, std::uint32_t qty,
                       std::uint32_t seq) {
    return Message{magic, symbol, side, price, qty, seq};
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    const std::string vcd_path = argc > 1 ? argv[1] : "market_pipeline.vcd";

    try {
        Simulation sim(vcd_path);
        sim.reset(3);
        sim.set_symbol(Simulation::kAapl);

        sim.require_fire(message(0xbeef, Simulation::kAapl, false, 1, 1, 9001),
                         true, "bad_magic_initial");
        sim.require_fire(message(Simulation::kMagic, Simulation::kMsft, true,
                                 2, 2, 9002),
                         true, "nonmatch_initial");
        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, false,
                                 100100, 10, 1),
                         true, "match_initial");
        sim.drain();

        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, false,
                                 101000, 100, 10),
                         false, "burst_match_10");
        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, true,
                                 101001, 101, 11),
                         false, "burst_match_11");
        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, false,
                                 101002, 102, 12),
                         false, "burst_match_12");
        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, true,
                                 101003, 103, 13),
                         false, "burst_match_13");

        sim.require_fire(message(0x0000, Simulation::kMsft, false,
                                 3, 3, 9003),
                         false, "bad_magic_while_full");
        sim.require_fire(message(Simulation::kMagic, Simulation::kMsft, false,
                                 4, 4, 9004),
                         false, "nonmatch_while_full");

        const Message seq14 = message(Simulation::kMagic, Simulation::kAapl,
                                      false, 101004, 104, 14);
        sim.require_stall(seq14, "fifo_full_stall_1");
        sim.require_stall(seq14, "fifo_full_stall_2");
        sim.require_stall(seq14, "fifo_full_stall_3");
        sim.require_fire(seq14, true, "fifo_release_match_14");
        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, true,
                                 101005, 105, 15),
                         true, "post_release_match_15");
        sim.drain();

        sim.set_symbol(Simulation::kMsft);
        sim.require_fire(message(Simulation::kMagic, Simulation::kAapl, false,
                                 5, 5, 9005),
                         true, "reconfigured_nonmatch");
        sim.require_fire(message(Simulation::kMagic, Simulation::kMsft, true,
                                 202000, 200, 20),
                         true, "reconfigured_match");
        sim.drain();

        sim.finish_checks();
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
