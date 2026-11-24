#include "Vmarket_pipeline.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <array>
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>

static vluint64_t main_time = 0;
double sc_time_stamp() { return static_cast<double>(main_time); }
struct Order { std::array<std::uint8_t, 36> itch{}; std::uint64_t sequence{}; };
struct Expected { std::uint64_t stock; std::uint8_t side; std::uint32_t shares;
                  std::uint32_t price; std::uint64_t sequence; };

static std::uint8_t digit(char v) {
    if (v >= '0' && v <= '9') return v - '0';
    if (v >= 'a' && v <= 'f') return v - 'a' + 10;
    throw std::runtime_error("bad hex digit");
}
static Order decode(const std::string& hex, std::uint64_t sequence) {
    if (hex.size() != 72) throw std::runtime_error("ITCH A must be 36 bytes");
    Order order; order.sequence = sequence;
    for (std::size_t i = 0; i < 36; ++i)
        order.itch[i] = (digit(hex[2*i]) << 4) | digit(hex[2*i+1]);
    return order;
}
static std::map<std::string, Order> load_golden(const std::string& path) {
    std::ifstream input(path); if (!input) throw std::runtime_error("golden file unavailable");
    std::map<std::string, Order> result; std::string line;
    while (std::getline(input, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream row(line); std::string stock, hex; std::uint64_t sequence;
        if (!(row >> stock >> sequence >> hex)) throw std::runtime_error("bad golden row");
        result.emplace(stock, decode(hex, sequence));
    }
    if (!result.count("AAPL") || !result.count("NVDA"))
        throw std::runtime_error("AAPL/NVDA golden missing");
    return result;
}
static std::uint64_t be64(const std::uint8_t* b) {
    std::uint64_t v = 0; for (int i = 0; i < 8; ++i) v = (v << 8) | b[i]; return v;
}
static std::uint32_t be32(const std::uint8_t* b) {
    return (std::uint32_t(b[0]) << 24) | (std::uint32_t(b[1]) << 16) |
           (std::uint32_t(b[2]) << 8) | b[3];
}

class Sim {
  public:
    explicit Sim(const char* vcd) {
        Verilated::traceEverOn(true); dut.trace(&trace, 99); trace.open(vcd);
        dut.clk=0; dut.rst_n=0; dut.s_valid=0; dut.m_ready=0;
        dut.cfg_stock=0x4141504c20202020ULL; clear(); tick(); tick(); dut.rst_n=1;
    }
    ~Sim() { dut.final(); trace.close(); }
    bool step(const Order* order, bool ready) {
        dut.clk=0; dut.m_ready=ready; dut.s_valid=order != nullptr;
        if (order) drive(*order); else clear();
        dut.eval(); trace.dump(main_time++);
        if (!queue.empty()) check(queue.front());
        bool input_fire=order && dut.s_ready, output_fire=dut.m_valid && dut.m_ready;
        if (output_fire) { check(queue.front()); queue.pop_front(); ++outputs; }
        if (input_fire) {
            ++accepted; const auto& b=order->itch;
            bool valid=b[0]=='A' && (b[19]=='B' || b[19]=='S') && be64(&b[24]);
            if (!valid) ++bad;
            else if (be64(&b[24]) != dut.cfg_stock) ++nonmatch;
            else { ++matched; queue.push_back({be64(&b[24]), b[19], be32(&b[20]),
                                               be32(&b[32]), order->sequence}); }
        }
        dut.clk=1; dut.eval(); trace.dump(main_time++);
        if (dut.fifo_level != queue.size()) throw std::runtime_error("fifo level mismatch");
        return input_fire;
    }
    void reset_boundary(Order order) {
        order.sequence = 15165560;
        if (!step(&order, false)) throw std::runtime_error("reset setup rejected");
        order.sequence++;
        if (!step(&order, false)) throw std::runtime_error("reset setup rejected");
        dut.rst_n=0; dut.s_valid=0; dut.m_ready=0; clear(); tick(); tick();
        if (dut.fifo_level || dut.m_valid || dut.accepted_count || dut.matched_count ||
            dut.bad_format_count || dut.nonmatch_count || dut.stall_count)
            throw std::runtime_error("reset boundary mismatch");
        queue.clear(); accepted=matched=bad=nonmatch=outputs=0;
        dut.rst_n=1; tick();
        std::cout << "RESET_BOUNDARY_PASS fifo_level=0 counters=0\n";
    }
    void finish() {
        while (!queue.empty()) step(nullptr, true);
        if (accepted!=13 || matched!=8 || bad!=2 || nonmatch!=3 || outputs!=8)
            throw std::runtime_error("reference counter mismatch");
        if (dut.accepted_count!=13 || dut.matched_count!=8 ||
            dut.bad_format_count!=2 || dut.nonmatch_count!=3 || dut.stall_count<3)
            throw std::runtime_error("RTL counter mismatch");
        std::cout << "VERILATOR_ITCH_PIPELINE_PASS cases=13 accepted=13 matched=8"
                  << " bad_format=2 nonmatch=3 outputs=8 stall_cycles="
                  << dut.stall_count << " full_mold_sequence=15165571\n";
    }
  private:
    Vmarket_pipeline dut; VerilatedVcdC trace; std::deque<Expected> queue;
    unsigned accepted=0, matched=0, bad=0, nonmatch=0, outputs=0;
    void tick(){ dut.clk=0;dut.eval();trace.dump(main_time++);dut.clk=1;dut.eval();trace.dump(main_time++); }
    void clear(){ for(int i=0;i<9;++i)dut.s_itch[i]=0; dut.s_mold_seq=0; }
    void drive(const Order& order){ clear(); for(unsigned i=0;i<36;++i){unsigned bit=(35-i)*8;
        dut.s_itch[bit/32] |= std::uint32_t(order.itch[i]) << (bit%32);} dut.s_mold_seq=order.sequence; }
    void check(const Expected& v){ if(!dut.m_valid || dut.m_stock!=v.stock ||
        dut.m_side!=v.side || dut.m_shares!=v.shares || dut.m_price!=v.price ||
        dut.m_mold_seq!=v.sequence) throw std::runtime_error("output mismatch"); }
};

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    try {
        Sim sim(argc>1 ? argv[1] : "itch-pipeline.vcd");
        auto vectors=load_golden(argc>2 ? argv[2] : "itch_add_order_golden.txt");
        Order aapl=vectors.at("AAPL"), nvda=vectors.at("NVDA");
        sim.reset_boundary(aapl);
        for(int i=0;i<4;++i){aapl.sequence=15165571+i;if(!sim.step(&aapl,false))throw std::runtime_error("fifo rejected before full");}
        for(int i=0;i<3;++i)if(sim.step(&aapl,false))throw std::runtime_error("fifo accepted while full");
        for(int i=0;i<4;++i){aapl.sequence=15165580+i;if(!sim.step(&aapl,true))throw std::runtime_error("simultaneous pop/push rejected");}
        for(int i=0;i<3;++i)if(!sim.step(&nvda,true))throw std::runtime_error("nonmatch input rejected");
        aapl.itch[0]='D';if(!sim.step(&aapl,true))throw std::runtime_error("bad type input rejected");
        aapl.itch[0]='A';aapl.itch[19]='X';if(!sim.step(&aapl,true))throw std::runtime_error("bad side input rejected");
        sim.finish();
    } catch(const std::exception& e){std::cerr<<"TEST_FAIL "<<e.what()<<'\n';return 1;}
    return 0;
}
