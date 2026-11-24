#include "Vtoolchain_smoke.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>

static void tick(Vtoolchain_smoke& dut) {
    dut.clk = 0;
    dut.eval();
    dut.clk = 1;
    dut.eval();
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Vtoolchain_smoke dut;
    dut.rst_n = 0;
    dut.in_valid = 0;
    dut.in_data = 0;
    tick(dut);

    dut.rst_n = 1;
    dut.in_valid = 1;
    dut.in_data = 0x1234;
    tick(dut);

    dut.final();
    std::cout << "input=0x1234 out_valid="
              << static_cast<int>(dut.out_valid)
              << " output=0x" << std::hex << dut.out_data << '\n';
    return 0;
}
