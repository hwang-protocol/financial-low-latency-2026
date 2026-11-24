`timescale 1ns/1ps

module market_pipeline (
    input logic clk, input logic rst_n, input logic [63:0] cfg_stock,
    input logic s_valid, output logic s_ready,
    input logic [287:0] s_itch, input logic [63:0] s_mold_seq,
    output logic m_valid, input logic m_ready,
    output logic [63:0] m_stock, output logic [7:0] m_side,
    output logic [31:0] m_shares, output logic [31:0] m_price,
    output logic [63:0] m_mold_seq, output logic [63:0] m_timestamp,
    output logic [63:0] cycle_count, output logic [31:0] accepted_count,
    output logic [31:0] matched_count, output logic [31:0] bad_format_count,
    output logic [31:0] nonmatch_count, output logic [31:0] stall_count,
    output logic [2:0] fifo_level
);
    logic [63:0] stock_mem [0:3], seq_mem [0:3], timestamp_mem [0:3];
    logic [7:0] side_mem [0:3];
    logic [31:0] shares_mem [0:3], price_mem [0:3];
    logic [1:0] wr_ptr, rd_ptr;
    logic [2:0] count;
    logic [7:0] in_type, in_side;
    logic [31:0] in_shares, in_price;
    logic [63:0] in_stock;
    logic input_bad_format, input_match, fifo_full, accept, push, pop;

    assign in_type = s_itch[287:280];
    assign in_side = s_itch[135:128];
    assign in_shares = s_itch[127:96];
    assign in_stock = s_itch[95:32];
    assign in_price = s_itch[31:0];
    assign input_bad_format = in_type != 8'h41 ||
        (in_side != 8'h42 && in_side != 8'h53) || in_stock == 64'd0;
    assign input_match = !input_bad_format && in_stock == cfg_stock;
`ifdef FLLE_MUTANT_FIFO
    assign fifo_full = count == 3'd5;
`else
    assign fifo_full = count == 3'd4;
`endif
    assign m_valid = count != 0;
    assign pop = m_valid && m_ready;
    assign s_ready = !s_valid || !input_match || !fifo_full || pop;
    assign accept = s_valid && s_ready;
    assign push = accept && input_match;
    assign m_stock = stock_mem[rd_ptr];
    assign m_side = side_mem[rd_ptr];
    assign m_shares = shares_mem[rd_ptr];
    assign m_price = price_mem[rd_ptr];
    assign m_mold_seq = seq_mem[rd_ptr];
    assign m_timestamp = timestamp_mem[rd_ptr];
    assign fifo_level = count;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= 0; rd_ptr <= 0; count <= 0; cycle_count <= 0;
            accepted_count <= 0; matched_count <= 0; bad_format_count <= 0;
            nonmatch_count <= 0; stall_count <= 0;
        end else begin
            cycle_count <= cycle_count + 1;
            if (s_valid && !s_ready) stall_count <= stall_count + 1;
            if (accept) begin
                accepted_count <= accepted_count + 1;
                if (input_bad_format) bad_format_count <= bad_format_count + 1;
                else if (!input_match) nonmatch_count <= nonmatch_count + 1;
                else matched_count <= matched_count + 1;
            end
            if (push) begin
                stock_mem[wr_ptr] <= in_stock; side_mem[wr_ptr] <= in_side;
                shares_mem[wr_ptr] <= in_shares; price_mem[wr_ptr] <= in_price;
                seq_mem[wr_ptr] <= s_mold_seq;
                timestamp_mem[wr_ptr] <= cycle_count; wr_ptr <= wr_ptr + 1;
            end
            if (pop) rd_ptr <= rd_ptr + 1;
            case ({push, pop})
                2'b10: count <= count + 1;
                2'b01: count <= count - 1;
                default: count <= count;
            endcase
            assert (count <= 3'd4)
                else $error("RTL_ASSERT_FAIL name=fifo_bound count=%0d", count);
        end
    end
endmodule
