`timescale 1ns/1ps
// DECLARATIONS ONLY, for local structural lint. NO behavioral validation of IP.
// NEVER add this file to Vivado; real modules already exist in OpenNIC.
/* verilator lint_off UNDRIVEN */
/* verilator lint_off UNUSED */
module axi_lite_clock_converter (
    input wire s_axi_aclk, s_axi_aresetn, m_axi_aclk, m_axi_aresetn,
    input wire [31:0] s_axi_awaddr, s_axi_wdata, s_axi_araddr,
    input wire [2:0] s_axi_awprot, s_axi_arprot,
    input wire [3:0] s_axi_wstrb,
    input wire s_axi_awvalid, s_axi_wvalid, s_axi_bready, s_axi_arvalid, s_axi_rready,
    output wire s_axi_awready, s_axi_wready, s_axi_bvalid, s_axi_arready, s_axi_rvalid,
    output wire [31:0] s_axi_rdata,
    output wire [1:0] s_axi_bresp, s_axi_rresp,
    output wire [31:0] m_axi_awaddr, m_axi_wdata, m_axi_araddr,
    output wire [2:0] m_axi_awprot, m_axi_arprot,
    output wire [3:0] m_axi_wstrb,
    output wire m_axi_awvalid, m_axi_wvalid, m_axi_bready, m_axi_arvalid, m_axi_rready,
    input wire m_axi_awready, m_axi_wready, m_axi_bvalid, m_axi_arready, m_axi_rvalid,
    input wire [31:0] m_axi_rdata,
    input wire [1:0] m_axi_bresp, m_axi_rresp
);
endmodule
module generic_reset #(
    parameter integer NUM_INPUT_CLK=1, SAMPLE_CLK_INDEX=0, RESET_DURATION=100
) (
    input wire mod_rstn,
    output wire mod_rst_done,
    input wire [NUM_INPUT_CLK-1:0] clk,
    output wire [NUM_INPUT_CLK-1:0] rstn
);
endmodule
module axi_lite_slave #(parameter integer REG_ADDR_W=12, REG_PREFIX=0)(
    input wire aclk, aresetn,
    input wire s_axil_awvalid, s_axil_wvalid, s_axil_bready, s_axil_arvalid, s_axil_rready,
    input wire [31:0] s_axil_awaddr, s_axil_wdata, s_axil_araddr,
    output wire s_axil_awready, s_axil_wready, s_axil_bvalid, s_axil_arready, s_axil_rvalid,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_bresp, s_axil_rresp
);
endmodule
module axi_stream_pipeline (
    input wire aclk, aresetn,
    input wire s_axis_tvalid, s_axis_tlast,
    input wire [511:0] s_axis_tdata,
    input wire [63:0] s_axis_tkeep,
    input wire [47:0] s_axis_tuser,
    output wire s_axis_tready,
    output wire m_axis_tvalid, m_axis_tlast,
    output wire [511:0] m_axis_tdata,
    output wire [63:0] m_axis_tkeep,
    output wire [47:0] m_axis_tuser,
    input wire m_axis_tready
);
endmodule
