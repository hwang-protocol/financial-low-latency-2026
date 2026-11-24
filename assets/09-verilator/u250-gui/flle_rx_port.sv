`timescale 1ns/1ps
// FLLE integration wrapper. The existing OpenNIC AMD clock-converter IP owns
// every control/status crossing; registers and packet logic run at axis_aclk.
module flle_rx_port #(
    parameter logic [31:0] ARM_TIMEOUT_CYCLES = 32'd1250000000
) (
    input wire axil_aclk, axil_aresetn, axis_aclk, axis_aresetn,
    input wire s_axil_awvalid, s_axil_wvalid, s_axil_bready,
    input wire [31:0] s_axil_awaddr, s_axil_wdata,
    output wire s_axil_awready, s_axil_wready, s_axil_bvalid,
    output wire [1:0] s_axil_bresp,
    input wire s_axil_arvalid, s_axil_rready,
    input wire [31:0] s_axil_araddr,
    output wire s_axil_arready, s_axil_rvalid,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
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
    wire c_awvalid, c_awready, c_wvalid, c_wready, c_bvalid, c_bready;
    wire c_arvalid, c_arready, c_rvalid, c_rready;
    wire [31:0] c_awaddr, c_wdata, c_araddr, c_rdata;
    wire [3:0] c_wstrb;
    wire [1:0] c_bresp, c_rresp;
    wire cfg_valid, cfg_arm, cfg_ready;
    wire [31:0] passed_frames, dropped_frames, remaining_drops;
    wire [63:0] last_drop_sequence;

    // The upstream OpenNIC user bus has no WSTRB: full 32-bit accesses only.
    // Its fixed source config uses AXI4LITE, DATA_WIDTH=32, ACLK_ASYNC=1.
    axi_lite_clock_converter control_cdc_inst (
        .s_axi_aclk(axil_aclk), .s_axi_aresetn(axil_aresetn),
        .m_axi_aclk(axis_aclk), .m_axi_aresetn(axis_aresetn),
        .s_axi_awaddr(s_axil_awaddr), .s_axi_awprot(3'b000),
        .s_axi_awvalid(s_axil_awvalid), .s_axi_awready(s_axil_awready),
        .s_axi_wdata(s_axil_wdata), .s_axi_wstrb(4'hf),
        .s_axi_wvalid(s_axil_wvalid), .s_axi_wready(s_axil_wready),
        .s_axi_bvalid(s_axil_bvalid), .s_axi_bready(s_axil_bready),
        .s_axi_bresp(s_axil_bresp),
        .s_axi_araddr(s_axil_araddr), .s_axi_arprot(3'b000),
        .s_axi_arvalid(s_axil_arvalid), .s_axi_arready(s_axil_arready),
        .s_axi_rdata(s_axil_rdata), .s_axi_rresp(s_axil_rresp),
        .s_axi_rvalid(s_axil_rvalid), .s_axi_rready(s_axil_rready),
        .m_axi_awaddr(c_awaddr), .m_axi_awprot(),
        .m_axi_awvalid(c_awvalid), .m_axi_awready(c_awready),
        .m_axi_wdata(c_wdata), .m_axi_wstrb(c_wstrb),
        .m_axi_wvalid(c_wvalid), .m_axi_wready(c_wready),
        .m_axi_bvalid(c_bvalid), .m_axi_bready(c_bready), .m_axi_bresp(c_bresp),
        .m_axi_araddr(c_araddr), .m_axi_arprot(),
        .m_axi_arvalid(c_arvalid), .m_axi_arready(c_arready),
        .m_axi_rdata(c_rdata), .m_axi_rresp(c_rresp),
        .m_axi_rvalid(c_rvalid), .m_axi_rready(c_rready)
    );

    flle_rx_regs #(.ARM_TIMEOUT_CYCLES(ARM_TIMEOUT_CYCLES)) control_inst (
        .clk(axis_aclk), .rst_n(axis_aresetn),
        .s_awaddr(c_awaddr), .s_awvalid(c_awvalid), .s_awready(c_awready),
        .s_wdata(c_wdata), .s_wstrb(c_wstrb), .s_wvalid(c_wvalid), .s_wready(c_wready),
        .s_bvalid(c_bvalid), .s_bready(c_bready), .s_bresp(c_bresp),
        .s_araddr(c_araddr), .s_arvalid(c_arvalid), .s_arready(c_arready),
        .s_rdata(c_rdata), .s_rresp(c_rresp), .s_rvalid(c_rvalid), .s_rready(c_rready),
        .cfg_valid(cfg_valid), .cfg_arm(cfg_arm), .cfg_ready(cfg_ready),
        .passed_frames(passed_frames), .dropped_frames(dropped_frames),
        .remaining_drops(remaining_drops), .last_drop_sequence(last_drop_sequence)
    );

    flle_rx_filter #(.ARM_TIMEOUT_CYCLES(ARM_TIMEOUT_CYCLES)) filter_inst (
        .clk(axis_aclk), .rst_n(axis_aresetn),
        .cfg_valid(cfg_valid), .cfg_arm(cfg_arm), .cfg_ready(cfg_ready),
        .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
        .s_axis_tdata(s_axis_tdata), .s_axis_tkeep(s_axis_tkeep),
        .s_axis_tlast(s_axis_tlast), .s_axis_tuser(s_axis_tuser),
        .m_axis_tvalid(m_axis_tvalid), .m_axis_tready(m_axis_tready),
        .m_axis_tdata(m_axis_tdata), .m_axis_tkeep(m_axis_tkeep),
        .m_axis_tlast(m_axis_tlast), .m_axis_tuser(m_axis_tuser),
        .passed_frames(passed_frames), .dropped_frames(dropped_frames),
        .remaining_drops(remaining_drops), .last_drop_sequence(last_drop_sequence)
    );
endmodule

// Single-clock AXI-Lite register bank: independently buffer AW and W, keep
// B/R stable under backpressure, and acknowledge commands only when applied.
// Offsets are LOCAL to the per-port ingress window, not PCIe BAR addresses.
module flle_rx_regs #(
    parameter logic [31:0] ARM_TIMEOUT_CYCLES = 32'd1250000000
) (
    input logic clk, rst_n,
    input logic [31:0] s_awaddr, s_wdata, s_araddr,
    input logic [3:0] s_wstrb,
    input logic s_awvalid, s_wvalid, s_bready, s_arvalid, s_rready,
    output logic s_awready, s_wready, s_bvalid, s_arready, s_rvalid,
    output logic [1:0] s_bresp, s_rresp,
    output logic [31:0] s_rdata,
    output logic cfg_valid, cfg_arm,
    input logic cfg_ready,
    input logic [31:0] passed_frames, dropped_frames, remaining_drops,
    input logic [63:0] last_drop_sequence
);
    logic aw_pending, w_pending, command_pending;
    logic [31:0] aw_saved, w_saved;
    logic [3:0] strb_saved;
    logic [63:0] sequence_snapshot;
    assign s_awready = rst_n && !aw_pending && !command_pending && !s_bvalid;
    assign s_wready = rst_n && !w_pending && !command_pending && !s_bvalid;
    assign s_arready = rst_n && !s_rvalid;
    assign cfg_valid = rst_n && command_pending;
    assign cfg_arm = w_saved[0];

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            aw_pending <= 0; w_pending <= 0; command_pending <= 0;
            aw_saved <= 0; w_saved <= 0; strb_saved <= 0;
            s_bvalid <= 0; s_bresp <= 0;
            s_rvalid <= 0; s_rdata <= 0; s_rresp <= 0;
            sequence_snapshot <= 0;
        end else begin
            if (s_bvalid && s_bready) s_bvalid <= 0;
            if (s_rvalid && s_rready) s_rvalid <= 0;
            if (s_awvalid && s_awready) begin
                aw_saved <= s_awaddr;
                aw_pending <= 1;
            end
            if (s_wvalid && s_wready) begin
                w_saved <= s_wdata; strb_saved <= s_wstrb;
                w_pending <= 1;
            end
            if (aw_pending && w_pending && !command_pending && !s_bvalid) begin
                aw_pending <= 0; w_pending <= 0;
                // Only command offset 0x08 accepts writes: 0=disarm, 1=arm.
                // No implicit address wrap/aliases or partial command writes.
                if (aw_saved == 32'h08 && strb_saved == 4'hf && w_saved <= 1)
                    command_pending <= 1;
                else begin
                    s_bvalid <= 1; s_bresp <= 2'b10; // SLVERR
                end
            end
            if (cfg_valid && cfg_ready) begin
                command_pending <= 0;
                s_bvalid <= 1; s_bresp <= 2'b00;
            end
            if (s_arvalid && s_arready) begin
                s_rvalid <= 1; s_rresp <= 0;
                case (s_araddr)
                    32'h00: s_rdata <= 32'h464c4c45; // FLLE
                    32'h04: s_rdata <= 32'h00010000; // register ABI 1.0
                    32'h08: s_rdata <= 0; // command, not persistent enable
                    32'h0c: s_rdata <= {29'd0, cfg_ready, command_pending,
                                       (remaining_drops != 0)};
                    32'h10: s_rdata <= remaining_drops;
                    32'h14: s_rdata <= passed_frames;
                    32'h18: s_rdata <= dropped_frames;
                    32'h1c: begin
                        s_rdata <= last_drop_sequence[31:0];
                        sequence_snapshot <= last_drop_sequence;
                    end
                    32'h20: s_rdata <= sequence_snapshot[63:32];
                    32'h24: s_rdata <= ARM_TIMEOUT_CYCLES;
                    32'h28: s_rdata <= 32'h14010101; // fixed source IPv4
                    32'h2c: s_rdata <= 32'he94a7d20; // fixed group IPv4
                    32'h30: s_rdata <= 32'd31032;
                    32'h34: s_rdata <= 32'd8095;
                    32'h38: s_rdata <= 32'h4e564441; // NVDA
                    32'h3c: s_rdata <= 32'h20202020;
                    default: begin s_rdata <= 0; s_rresp <= 2'b10; end
                endcase
            end
        end
    end
endmodule
