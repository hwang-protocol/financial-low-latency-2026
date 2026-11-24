#include "Vmarket_pipeline_reset.h"
#include "verilated.h"
#include "verilated_cov.h"
#include "verilated_vcd_c.h"

#include <array>
#include <cstdint>
#include <deque>
#include <fstream>
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

class ScoreboardFailure : public std::runtime_error {
  public:
    explicit ScoreboardFailure(const std::string& message)
        : std::runtime_error(message) {}
};

class Simulation {
  public:
    Simulation(const std::string& vcd_path, const std::string& coverage_path)
        : coverage_path_(coverage_path) {
        Verilated::traceEverOn(true);
        dut_.trace(&trace_, 99);
        trace_.open(vcd_path.c_str());
        dut_.clk = 0;
        dut_.rst_n = 0;
        dut_.cfg_symbol = kAapl;
        dut_.s_valid = 0;
        dut_.m_ready = 0;
        clear_input();
        dut_.eval();
        trace_.dump(main_time);
    }

    ~Simulation() {
        VerilatedCov::write(coverage_path_.c_str());
        dut_.final();
        trace_.flush();
        trace_.close();
    }

    void run(const std::string& mode, const std::string& result_path) {
        startup_reset(3);
        run_pre_reset_fill_and_stall();
        apply_midstream_reset(mode);
        run_post_reset_matrix();
        finish_checks();
        write_result(result_path);
        std::cout
            << "VERILATOR_MIDSTREAM_RESET_PASS"
            << " pre_fifo=4 pre_stall=2 reset_cycles=2"
            << " reset_discarded=4 pre_reset_leaks=0"
            << " post_outputs=1 first_post_timestamp=0"
            << " final_accepted=3 final_matched=1"
            << " final_bad_magic=1 final_nonmatch=1 final_cycle=3\n";
    }

  private:
    static constexpr std::uint16_t kMagic = 0x4d44;
    static constexpr std::uint32_t kAapl = 0x4141504c;
    static constexpr std::uint32_t kMsft = 0x4d534654;

    Vmarket_pipeline_reset dut_;
    VerilatedVcdC trace_;
    std::string coverage_path_;
    std::deque<ExpectedOutput> expected_;
    std::uint64_t active_cycle_ = 0;
    std::uint64_t accepted_ = 0;
    std::uint64_t matched_ = 0;
    std::uint64_t bad_magic_ = 0;
    std::uint64_t nonmatch_ = 0;
    std::uint64_t stall_ = 0;
    std::uint64_t outputs_ = 0;
    std::uint64_t pre_reset_fifo_level_ = 0;
    std::uint64_t pre_reset_stall_cycles_ = 0;
    std::uint64_t reset_asserted_cycles_ = 0;
    std::uint64_t during_reset_valid_ignored_ = 0;
    std::uint64_t reset_state_checks_ = 0;
    std::uint64_t reset_discarded_items_ = 0;
    std::uint64_t pre_reset_output_leaks_ = 0;
    std::vector<std::uint32_t> output_sequences_;
    std::vector<std::uint64_t> output_timestamps_;

    [[noreturn]] void fail(const std::string& name,
                           const std::string& expected,
                           const std::string& actual) const {
        std::cerr << "SCOREBOARD_FAIL name=" << name
                  << " active_cycle=" << active_cycle_
                  << " expected=" << expected
                  << " actual=" << actual << '\n';
        throw ScoreboardFailure(name);
    }

    static std::string decimal(std::uint64_t value) {
        std::ostringstream stream;
        stream << value;
        return stream.str();
    }

    template <typename Expected, typename Actual>
    void check_equal(const std::string& name,
                     Expected expected,
                     Actual actual) const {
        const auto expected_value = static_cast<std::uint64_t>(expected);
        const auto actual_value = static_cast<std::uint64_t>(actual);
        if (expected_value != actual_value) {
            fail(name, decimal(expected_value), decimal(actual_value));
        }
    }

    void check_string(const std::string& name,
                      const std::string& expected,
                      const std::string& actual) const {
        if (expected != actual) {
            fail(name, expected, actual);
        }
    }

    void dump_eval() {
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

    void check_golden_words() {
        static constexpr std::array<std::uint32_t, 5> expected_words{{
            0x0000002au,
            0x000003e8u,
            0x00bc614eu,
            0x504c8000u,
            0x4d444141u,
        }};
        for (std::size_t index = 0; index < expected_words.size(); ++index) {
            check_equal("golden_word_" + decimal(index),
                        expected_words[index], dut_.s_data[index]);
        }
        std::cout
            << "GOLDEN_WORD_GATE=PASS"
            << " hex=4d444141504c800000bc614e000003e80000002a\n";
    }

    void startup_reset(unsigned cycles) {
        for (unsigned index = 0; index < cycles; ++index) {
            dut_.clk = 0;
            dut_.rst_n = 0;
            dut_.s_valid = 0;
            dut_.m_ready = 0;
            clear_input();
            dump_eval();
            dut_.clk = 1;
            dump_eval();
            check_reset_state("startup_reset");
        }
        release_reset();
        clear_reference_epoch();
        std::cout << "STARTUP_RESET_GATE=PASS cycles=" << cycles << '\n';
    }

    void release_reset() {
        dut_.clk = 0;
        dut_.rst_n = 1;
        dut_.s_valid = 0;
        dut_.m_ready = 0;
        clear_input();
        dump_eval();
    }

    void clear_reference_epoch() {
        expected_.clear();
        active_cycle_ = 0;
        accepted_ = 0;
        matched_ = 0;
        bad_magic_ = 0;
        nonmatch_ = 0;
        stall_ = 0;
    }

    bool step(const Message* message, bool output_ready) {
        dut_.clk = 0;
        dut_.rst_n = 1;
        dut_.m_ready = output_ready ? 1 : 0;
        if (message == nullptr) {
            dut_.s_valid = 0;
            clear_input();
        } else {
            dut_.s_valid = 1;
            drive_message(*message);
        }
        dump_eval();

        check_equal("preedge_fifo_level", expected_.size(), dut_.fifo_level);
        check_equal("preedge_m_valid", expected_.empty() ? 0u : 1u,
                    dut_.m_valid);
        if (!expected_.empty()) {
            check_output(expected_.front());
        }

        const bool input_fire = message != nullptr && dut_.s_ready;
        const bool output_fire = dut_.m_valid && dut_.m_ready;
        if (message != nullptr && !dut_.s_ready) {
            ++stall_;
        }

        if (output_fire) {
            if (expected_.empty()) {
                fail("output_without_reference", "queued", "empty");
            }
            check_output(expected_.front());
            output_sequences_.push_back(dut_.m_seq);
            output_timestamps_.push_back(dut_.m_timestamp);
            expected_.pop_front();
            ++outputs_;
        }

        if (input_fire) {
            ++accepted_;
            if (message->magic != kMagic) {
                ++bad_magic_;
            } else if (message->symbol != kAapl) {
                ++nonmatch_;
            } else {
                ++matched_;
                expected_.push_back(ExpectedOutput{*message, active_cycle_});
            }
        }

        dut_.clk = 1;
        dump_eval();
        ++active_cycle_;
        check_active_state();
        return input_fire;
    }

    void check_active_state() {
        check_equal("postedge_fifo_level", expected_.size(), dut_.fifo_level);
        check_equal("cycle_count", active_cycle_, dut_.cycle_count);
        check_equal("accepted_count", accepted_, dut_.accepted_count);
        check_equal("matched_count", matched_, dut_.matched_count);
        check_equal("bad_magic_count", bad_magic_, dut_.bad_magic_count);
        check_equal("nonmatch_count", nonmatch_, dut_.nonmatch_count);
        check_equal("stall_count", stall_, dut_.stall_count);
    }

    void check_reset_state(const std::string& prefix) {
        check_equal(prefix + "_fifo_level", 0u, dut_.fifo_level);
        ++reset_state_checks_;
        check_equal(prefix + "_m_valid", 0u, dut_.m_valid);
        ++reset_state_checks_;
        check_equal(prefix + "_cycle_count", 0u, dut_.cycle_count);
        ++reset_state_checks_;
        check_equal(prefix + "_accepted_count", 0u, dut_.accepted_count);
        ++reset_state_checks_;
        check_equal(prefix + "_matched_count", 0u, dut_.matched_count);
        ++reset_state_checks_;
        check_equal(prefix + "_bad_magic_count", 0u, dut_.bad_magic_count);
        ++reset_state_checks_;
        check_equal(prefix + "_nonmatch_count", 0u, dut_.nonmatch_count);
        ++reset_state_checks_;
        check_equal(prefix + "_stall_count", 0u, dut_.stall_count);
        ++reset_state_checks_;
    }

    void check_output(const ExpectedOutput& expected) {
        check_equal("output_symbol", expected.message.symbol, dut_.m_symbol);
        check_equal("output_side", expected.message.side ? 1u : 0u,
                    dut_.m_side);
        check_equal("output_price", expected.message.price, dut_.m_price);
        check_equal("output_qty", expected.message.qty, dut_.m_qty);
        check_equal("output_seq", expected.message.seq, dut_.m_seq);
        check_equal("output_timestamp", expected.timestamp, dut_.m_timestamp);
    }

    static Message make_message(std::uint16_t magic,
                                std::uint32_t symbol,
                                std::uint32_t seq) {
        return Message{magic, symbol, (seq & 1u) != 0,
                       100000u + seq * 17u, 1u + seq * 3u, seq};
    }

    void require_accept(const Message& message,
                        bool output_ready,
                        const std::string& name) {
        if (!step(&message, output_ready)) {
            fail(name, "accepted", "stalled");
        }
    }

    void require_stall(const Message& message, const std::string& name) {
        if (step(&message, false)) {
            fail(name, "stalled", "accepted");
        }
    }

    void run_pre_reset_fill_and_stall() {
        const Message golden{kMagic, kAapl, true, 12345678u, 1000u, 42u};
        dut_.clk = 0;
        dut_.rst_n = 1;
        dut_.s_valid = 1;
        dut_.m_ready = 0;
        drive_message(golden);
        dut_.eval();
        check_golden_words();

        require_accept(golden, false, "golden_accept");
        for (std::uint32_t seq = 43; seq <= 45; ++seq) {
            require_accept(make_message(kMagic, kAapl, seq), false,
                           "fifo_fill");
        }
        const Message pending = make_message(kMagic, kAapl, 46);
        require_stall(pending, "full_fifo_stall_1");
        require_stall(pending, "full_fifo_stall_2");

        check_equal("pre_reset_fifo_exact", 4u, dut_.fifo_level);
        check_equal("pre_reset_accepted_exact", 4u, dut_.accepted_count);
        check_equal("pre_reset_matched_exact", 4u, dut_.matched_count);
        check_equal("pre_reset_stall_exact", 2u, dut_.stall_count);
        check_equal("pre_reset_outputs_exact", 0u, outputs_);
        pre_reset_fifo_level_ = dut_.fifo_level;
        pre_reset_stall_cycles_ = dut_.stall_count;
        reset_discarded_items_ = expected_.size();
        std::cout
            << "PRE_RESET_STATE_GATE=PASS fifo_level=4 stall_cycles=2"
            << " queued=4 outputs=0\n";
    }

    void apply_midstream_reset(const std::string& mode) {
        if (mode == "omit-reset") {
            check_string("reset_assertion_required", "rst_n_low", "rst_n_high");
        }
        if (mode != "clean") {
            fail("mode", "clean_or_omit-reset", mode);
        }

        const Message pending = make_message(kMagic, kAapl, 46);
        const std::uint64_t outputs_before = outputs_;
        for (unsigned index = 0; index < 2; ++index) {
            dut_.clk = 0;
            dut_.rst_n = 0;
            dut_.s_valid = 1;
            dut_.m_ready = 1;
            drive_message(pending);
            dump_eval();
            dut_.clk = 1;
            dump_eval();
            ++reset_asserted_cycles_;
            ++during_reset_valid_ignored_;
            check_reset_state("reset");
            if (index == 0) {
                clear_reference_epoch();
            }
        }
        check_equal("reset_output_count_unchanged", outputs_before, outputs_);
        pre_reset_output_leaks_ = outputs_ - outputs_before;
        release_reset();
        clear_reference_epoch();
        output_sequences_.clear();
        output_timestamps_.clear();
        outputs_ = 0;
        std::cout
            << "MIDSTREAM_RESET_GATE=PASS reset_cycles=2"
            << " discarded=4 ignored_valid_cycles=2 leaks=0\n";
    }

    void run_post_reset_matrix() {
        const Message good = make_message(kMagic, kAapl, 900);
        const Message bad = make_message(0x4d45u, kAapl, 901);
        const Message nonmatch = make_message(kMagic, kMsft, 902);

        require_accept(good, false, "post_reset_good");
        require_accept(bad, true, "post_reset_bad_magic");
        require_accept(nonmatch, true, "post_reset_nonmatch");

        check_equal("post_reset_reference_empty", 0u, expected_.size());
        check_equal("post_reset_outputs", 1u, outputs_);
        check_equal("post_reset_sequence_count", 1u, output_sequences_.size());
        check_equal("post_reset_sequence", 900u, output_sequences_.at(0));
        check_equal("post_reset_timestamp_count", 1u, output_timestamps_.size());
        check_equal("post_reset_first_timestamp", 0u, output_timestamps_.at(0));
        std::cout
            << "POST_RESET_MATRIX_GATE=PASS outputs=1 sequence=900 timestamp=0"
            << " bad_magic=1 nonmatch=1\n";
    }

    void finish_checks() {
        check_equal("pre_reset_fifo_level_final", 4u, pre_reset_fifo_level_);
        check_equal("pre_reset_stall_cycles_final", 2u,
                    pre_reset_stall_cycles_);
        check_equal("reset_asserted_cycles_final", 2u,
                    reset_asserted_cycles_);
        check_equal("during_reset_valid_ignored_final", 2u,
                    during_reset_valid_ignored_);
        check_equal("reset_discarded_items_final", 4u,
                    reset_discarded_items_);
        check_equal("pre_reset_output_leaks_final", 0u,
                    pre_reset_output_leaks_);
        check_equal("final_accepted", 3u, accepted_);
        check_equal("final_matched", 1u, matched_);
        check_equal("final_bad_magic", 1u, bad_magic_);
        check_equal("final_nonmatch", 1u, nonmatch_);
        check_equal("final_stall", 0u, stall_);
        check_equal("final_cycle", 3u, active_cycle_);
        check_equal("dut_final_cycle", 3u, dut_.cycle_count);
        if (reset_state_checks_ < 16u) {
            fail("reset_state_checks", "at_least_16",
                 decimal(reset_state_checks_));
        }
    }

    void write_result(const std::string& result_path) const {
        std::ofstream output(result_path, std::ios::binary);
        if (!output) {
            throw std::runtime_error("cannot open result path");
        }
        output
            << "{\n"
            << "  \"status\": \"PASS\",\n"
            << "  \"probe_id\": \"v1-midstream-reset\",\n"
            << "  \"scenario\": \"fifo_full_output_stalled_midstream_reset\",\n"
            << "  \"golden_hex\": \"4d444141504c800000bc614e000003e80000002a\",\n"
            << "  \"pre_reset_fifo_level\": " << pre_reset_fifo_level_ << ",\n"
            << "  \"pre_reset_stall_cycles\": " << pre_reset_stall_cycles_ << ",\n"
            << "  \"reset_asserted_cycles\": " << reset_asserted_cycles_ << ",\n"
            << "  \"during_reset_valid_ignored\": " << during_reset_valid_ignored_ << ",\n"
            << "  \"reset_discarded_items\": " << reset_discarded_items_ << ",\n"
            << "  \"pre_reset_output_leaks\": " << pre_reset_output_leaks_ << ",\n"
            << "  \"post_reset_output_sequences\": [900],\n"
            << "  \"post_reset_timestamps\": [0],\n"
            << "  \"final_counters\": {\n"
            << "    \"accepted\": " << accepted_ << ",\n"
            << "    \"matched\": " << matched_ << ",\n"
            << "    \"bad_magic\": " << bad_magic_ << ",\n"
            << "    \"nonmatch\": " << nonmatch_ << ",\n"
            << "    \"stall\": " << stall_ << ",\n"
            << "    \"cycle\": " << active_cycle_ << "\n"
            << "  },\n"
            << "  \"claim_limit\": \"software_cycle_model_only\"\n"
            << "}\n";
        output.close();
        if (!output) {
            throw std::runtime_error("write failure for result path");
        }
    }
};

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc != 5) {
        std::cerr
            << "usage: Vmarket_pipeline_reset MODE RESULT_JSON VCD COVERAGE\n";
        return 64;
    }

    try {
        Simulation simulation(argv[3], argv[4]);
        simulation.run(argv[1], argv[2]);
        return 0;
    } catch (const ScoreboardFailure&) {
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "HARNESS_FAIL what=" << error.what() << '\n';
        return 3;
    }
}
