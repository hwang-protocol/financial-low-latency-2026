`timescale 1ns/1ps
// A register-driven test harness for the unchanged Chapter 09 market_filter.
// This is NOT an Ethernet MAC, DMA engine, or complete NIC datapath.
module market_filter_axil (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXI, ASSOCIATED_RESET s_axi_aresetn" *)
    input logic s_axi_aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input logic s_axi_aresetn,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWADDR",
       X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 12, READ_WRITE_MODE READ_WRITE" *)
    input logic [11:0] s_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input logic [2:0] s_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input logic s_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output logic s_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input logic [31:0] s_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input logic [3:0] s_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input logic s_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output logic s_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output logic [1:0] s_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output logic s_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input logic s_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input logic [11:0] s_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input logic [2:0] s_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input logic s_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output logic s_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output logic [31:0] s_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output logic [1:0] s_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output logic s_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input logic s_axi_rready
);
    logic aw_pending, w_pending;
    logic [11:0] awaddr_q;
    logic [31:0] wdata_q;
    logic [3:0] wstrb_q;
    logic [287:0] message_q;
    logic [63:0] input_seq, result_seq, stock;
    logic [15:0] locate;
    logic busy, result_valid, result_drop;
    logic core_valid, core_ready, load_valid, pass_valid, drop_valid;
    logic [31:0] load_drops, remaining, pass_count, drop_count;
    logic [63:0] core_seq;
    logic [31:0] read_value;
    logic read_error;

    function automatic [31:0] merge_bytes(input [31:0] old_value, new_value,
                                          input [3:0] strb);
        for (int j = 0; j < 4; j++)
            merge_bytes[j*8 +: 8] = strb[j] ? new_value[j*8 +: 8] : old_value[j*8 +: 8];
    endfunction

    assign s_axi_awready = s_axi_aresetn && !aw_pending && !s_axi_bvalid;
    assign s_axi_wready  = s_axi_aresetn && !w_pending && !s_axi_bvalid;
    assign s_axi_arready = s_axi_aresetn && !s_axi_rvalid;

    market_filter core (
        .clk(s_axi_aclk), .rst_n(s_axi_aresetn),
        .s_valid(core_valid), .s_ready(core_ready),
        .s_itch(message_q), .s_mold_seq(input_seq),
        .cfg_locate(locate), .cfg_stock(stock),
        .cfg_load_drops(load_drops), .cfg_load_valid(load_valid),
        .m_valid(pass_valid), .drop_valid(drop_valid), .m_mold_seq(core_seq),
        .remaining_drops(remaining), .pass_count(pass_count), .drop_count(drop_count)
    );

    always_comb begin
        read_value = 0;
        read_error = 0;
        case (s_axi_araddr)
            12'h000: read_value = 32'h464c4c39; // FLL9: this register-test application
            12'h008: read_value = {29'd0, result_drop, result_valid, busy};
            12'h00c: read_value = remaining;
            12'h010: read_value = pass_count;
            12'h014: read_value = drop_count;
            12'h018: read_value = result_seq[31:0];
            12'h01c: read_value = result_seq[63:32];
            12'h020: read_value = {16'd0, locate};
            12'h024: read_value = stock[31:0];
            12'h028: read_value = stock[63:32];
            12'h030: read_value = input_seq[31:0];
            12'h034: read_value = input_seq[63:32];
            default: begin
                if (s_axi_araddr >= 12'h040 && s_axi_araddr <= 12'h060 && s_axi_araddr[1:0] == 0)
                    read_value = message_q[287 - int'((s_axi_araddr - 12'h040) >> 2)*32 -: 32];
                else read_error = 1;
            end
        endcase
    end

    always_ff @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            aw_pending <= 0; w_pending <= 0;
            awaddr_q <= 0; wdata_q <= 0; wstrb_q <= 0;
            s_axi_bvalid <= 0; s_axi_bresp <= 0;
            s_axi_rvalid <= 0; s_axi_rresp <= 0; s_axi_rdata <= 0;
            message_q <= 0; input_seq <= 0; result_seq <= 0;
            locate <= 16'd8095; stock <= 64'h4e56444120202020;
            busy <= 0; result_valid <= 0; result_drop <= 0;
            core_valid <= 0; load_valid <= 0; load_drops <= 0;
        end else begin
            load_valid <= 0;
            if (core_valid && core_ready) core_valid <= 0;
            if (pass_valid || drop_valid) begin
                busy <= 0;
                result_valid <= 1;
                result_drop <= drop_valid;
                result_seq <= core_seq;
            end
            if (s_axi_awvalid && s_axi_awready) begin
                awaddr_q <= s_axi_awaddr;
                aw_pending <= 1;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                wdata_q <= s_axi_wdata;
                wstrb_q <= s_axi_wstrb;
                w_pending <= 1;
            end
            if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 0;
            if (aw_pending && w_pending && !s_axi_bvalid) begin
                aw_pending <= 0; w_pending <= 0;
                s_axi_bvalid <= 1;
                s_axi_bresp <= 2'b00;
                if (busy || awaddr_q[1:0] != 0) s_axi_bresp <= 2'b10;
                else if (wstrb_q == 0) begin end // AXI null write has no side effects.
                else case (awaddr_q)
                    12'h004: begin
                        if (!wstrb_q[0]) begin end
                        else case (merge_bytes(0, wdata_q, wstrb_q))
                            32'd1: begin load_drops <= 1; load_valid <= 1; end
                            32'd2: begin core_valid <= 1; busy <= 1; result_valid <= 0; result_drop <= 0; end
                            32'd4: begin load_drops <= 0; load_valid <= 1; end
                            default: s_axi_bresp <= 2'b10;
                        endcase
                    end
                    12'h020: begin
                        if (wstrb_q[0]) locate[7:0] <= wdata_q[7:0];
                        if (wstrb_q[1]) locate[15:8] <= wdata_q[15:8];
                    end
                    12'h024: stock[31:0] <= merge_bytes(stock[31:0], wdata_q, wstrb_q);
                    12'h028: stock[63:32] <= merge_bytes(stock[63:32], wdata_q, wstrb_q);
                    12'h030: input_seq[31:0] <= merge_bytes(input_seq[31:0], wdata_q, wstrb_q);
                    12'h034: input_seq[63:32] <= merge_bytes(input_seq[63:32], wdata_q, wstrb_q);
                    default: begin
                        if (awaddr_q >= 12'h040 && awaddr_q <= 12'h060)
                            message_q[287 - int'((awaddr_q - 12'h040) >> 2)*32 -: 32] <=
                                merge_bytes(message_q[287 - int'((awaddr_q - 12'h040) >> 2)*32 -: 32], wdata_q, wstrb_q);
                        else s_axi_bresp <= 2'b10;
                    end
                endcase
            end
            if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 0;
            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rvalid <= 1;
                s_axi_rdata <= read_value;
                s_axi_rresp <= read_error ? 2'b10 : 2'b00;
            end
        end
    end
endmodule
