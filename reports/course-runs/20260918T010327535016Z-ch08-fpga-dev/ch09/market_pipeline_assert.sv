`timescale 1ns/1ps

/* verilator lint_off DECLFILENAME */
module market_pipeline (
    input  logic         clk,
    input  logic         rst_n,

    input  logic [31:0]  cfg_symbol,

    input  logic         s_valid,
    output logic         s_ready,
    input  logic [159:0] s_data,

    output logic         m_valid,
    input  logic         m_ready,
    output logic [31:0]  m_symbol,
    output logic         m_side,
    output logic [31:0]  m_price,
    output logic [31:0]  m_qty,
    output logic [31:0]  m_seq,
    output logic [63:0]  m_timestamp,

    output logic [63:0]  cycle_count,
    output logic [31:0]  accepted_count,
    output logic [31:0]  matched_count,
    output logic [31:0]  bad_magic_count,
    output logic [31:0]  nonmatch_count,
    output logic [31:0]  stall_count,
    output logic [2:0]   fifo_level
);

    localparam logic [15:0] EXPECTED_MAGIC = 16'h4d44;

    logic [31:0]  symbol_mem [0:3];
    logic         side_mem [0:3];
    logic [31:0]  price_mem [0:3];
    logic [31:0]  qty_mem [0:3];
    logic [31:0]  seq_mem [0:3];
    logic [63:0]  timestamp_mem [0:3];
    logic [1:0]   wr_ptr;
    logic [1:0]   rd_ptr;
    logic [2:0]   count;

    logic [15:0] in_magic;
    logic [31:0] in_symbol;
    logic        input_bad_magic;
    logic        input_symbol_match;
    logic        input_match;
    logic        fifo_full;
    logic        accept;
    logic        push;
    logic        pop;
    logic        _unused_reserved;
    logic        prior_stall;
    logic [31:0] prior_symbol;
    logic        prior_side;
    logic [31:0] prior_price;
    logic [31:0] prior_qty;
    logic [31:0] prior_seq;
    logic [63:0] prior_timestamp;

    assign in_magic           = s_data[159:144];
    assign in_symbol          = s_data[143:112];
    assign input_bad_magic    = (in_magic != EXPECTED_MAGIC);
    assign input_symbol_match = (in_symbol == cfg_symbol);
    assign input_match        = !input_bad_magic && input_symbol_match;

    assign fifo_full = (count == 3'd4);
    assign m_valid   = (count != 3'd0);
    assign pop       = m_valid && m_ready;

    // Invalid or non-matching messages are consumed even when the FIFO is
    // full. A matching message observes normal ready/valid backpressure.
    assign s_ready = !s_valid || !input_match || !fifo_full || pop;
    assign accept  = s_valid && s_ready;
    assign push    = accept && input_match;

    assign m_symbol    = symbol_mem[rd_ptr];
    assign m_side      = side_mem[rd_ptr];
    assign m_price     = price_mem[rd_ptr];
    assign m_qty       = qty_mem[rd_ptr];
    assign m_seq       = seq_mem[rd_ptr];
    assign m_timestamp = timestamp_mem[rd_ptr];
    assign fifo_level  = count;
    assign _unused_reserved = &{1'b0, s_data[110:96]};

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr          <= 2'd0;
            rd_ptr          <= 2'd0;
            count           <= 3'd0;
            cycle_count     <= 64'd0;
            accepted_count  <= 32'd0;
            matched_count   <= 32'd0;
            bad_magic_count <= 32'd0;
            nonmatch_count  <= 32'd0;
            stall_count     <= 32'd0;
            prior_stall     <= 1'b0;
            prior_symbol    <= 32'd0;
            prior_side      <= 1'b0;
            prior_price     <= 32'd0;
            prior_qty       <= 32'd0;
            prior_seq       <= 32'd0;
            prior_timestamp <= 64'd0;
        end else begin
            cycle_count <= cycle_count + 64'd1;

            prior_stall     <= m_valid && !m_ready;
            prior_symbol    <= m_symbol;
            prior_side      <= m_side;
            prior_price     <= m_price;
            prior_qty       <= m_qty;
            prior_seq       <= m_seq;
            prior_timestamp <= m_timestamp;

            if (s_valid && !s_ready) begin
                stall_count <= stall_count + 32'd1;
            end

            if (accept) begin
                accepted_count <= accepted_count + 32'd1;
                if (input_bad_magic) begin
                    bad_magic_count <= bad_magic_count + 32'd1;
                end else if (!input_symbol_match) begin
                    nonmatch_count <= nonmatch_count + 32'd1;
                end else begin
                    matched_count <= matched_count + 32'd1;
                end
            end

            if (push) begin
                symbol_mem[wr_ptr]    <= in_symbol;
                side_mem[wr_ptr]      <= s_data[111];
                price_mem[wr_ptr]     <= s_data[95:64];
                qty_mem[wr_ptr]       <= s_data[63:32];
                seq_mem[wr_ptr]       <= s_data[31:0];
                timestamp_mem[wr_ptr] <= cycle_count;
                wr_ptr                <= wr_ptr + 2'd1;
            end

            if (pop) begin
                rd_ptr <= rd_ptr + 2'd1;
            end

            case ({push, pop})
                2'b10: count <= count + 3'd1;
                2'b01: count <= count - 3'd1;
                default: count <= count;
            endcase

`ifdef FLLE_MUTANT_OVERFLOW
            // Deliberate negative-test mutant. It is never defined for the
            // authoritative clean build.
            if (s_valid && !s_ready && input_match && fifo_full) begin
                count <= 3'd5;
            end
`endif

`ifdef FLLE_MUTANT_REORDER
            // Deliberate negative-test mutant for the external scoreboard.
            if (m_valid && !m_ready) begin
                rd_ptr <= rd_ptr + 2'd1;
            end
`endif
        end
    end

    // The combinational check makes the deliberate overflow mutant fail in
    // the same evaluation step, before the C++ scoreboard masks the RTL error.
    always_comb begin : immediate_invariants
        if (rst_n) begin
            assert (count <= 3'd4)
                else $fatal(1, "RTL_ASSERT_FAIL name=fifo_bound count=%0d", count);
        end
    end

    // Version 4.038 accepts only one-cycle assertion expressions. State from
    // the preceding cycle is therefore carried explicitly for the stall rule.
    always_ff @(posedge clk) begin : immediate_clocked_invariants
        if (rst_n) begin
            assert (count <= 3'd4)
                else $fatal(1, "RTL_ASSERT_FAIL name=fifo_bound_clocked count=%0d", count);
            assert (!push || !fifo_full || pop)
                else $fatal(1, "RTL_ASSERT_FAIL name=push_without_capacity");
            assert (!pop || count != 3'd0)
                else $fatal(1, "RTL_ASSERT_FAIL name=pop_without_data");
            assert (m_valid == (fifo_level != 3'd0))
                else $fatal(1, "RTL_ASSERT_FAIL name=valid_level_mismatch");
            if (prior_stall) begin
                assert (m_valid && m_symbol == prior_symbol &&
                        m_side == prior_side && m_price == prior_price &&
                        m_qty == prior_qty && m_seq == prior_seq &&
                        m_timestamp == prior_timestamp)
                    else $fatal(1, "RTL_ASSERT_FAIL name=stall_output_stable");
            end
        end
    end

    a_fifo_bound: assert property (
        @(posedge clk) disable iff (!rst_n) fifo_level <= 3'd4
    )
        else $fatal(1, "RTL_ASSERT_FAIL name=fifo_bound_sampled level=%0d", fifo_level);
    a_push_has_capacity: assert property (
        @(posedge clk) disable iff (!rst_n) !push || !fifo_full || pop
    )
        else $fatal(1, "RTL_ASSERT_FAIL name=push_without_capacity");
    a_pop_has_data: assert property (
        @(posedge clk) disable iff (!rst_n) !pop || count != 3'd0
    )
        else $fatal(1, "RTL_ASSERT_FAIL name=pop_without_data");
    a_valid_matches_level: assert property (
        @(posedge clk) disable iff (!rst_n) m_valid == (fifo_level != 3'd0)
    )
        else $fatal(1, "RTL_ASSERT_FAIL name=valid_level_mismatch");

    c_fifo_full:       cover property (@(posedge clk) disable iff (!rst_n) fifo_full);
    c_input_stall:     cover property (@(posedge clk) disable iff (!rst_n) s_valid && !s_ready);
    c_output_stall:    cover property (@(posedge clk) disable iff (!rst_n) m_valid && !m_ready);
    c_push_pop:        cover property (@(posedge clk) disable iff (!rst_n) push && pop);
    c_bad_magic:       cover property (@(posedge clk) disable iff (!rst_n) accept && input_bad_magic);
    c_nonmatch:        cover property (@(posedge clk) disable iff (!rst_n) accept && !input_bad_magic && !input_symbol_match);

endmodule
/* verilator lint_on DECLFILENAME */
