`timescale 1ns/1ps

// Testbench only: add to Simulation Sources, not Design Sources.
module market_filter_sim_tb;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0;
    logic s_valid = 0;
    wire s_ready;
    logic [287:0] s_itch = 0;
    logic [63:0] s_mold_seq = 0;
    logic [15:0] cfg_locate = 16'd8095;
    logic [63:0] cfg_stock = 64'h4e56444120202020;
    logic [31:0] cfg_load_drops = 0;
    logic cfg_load_valid = 0;
    wire m_valid, drop_valid;
    wire [63:0] m_mold_seq;
    wire [31:0] remaining_drops, pass_count, drop_count;
    integer cases = 0;
    logic [287:0] target_msg;
    logic [287:0] other_msg;

    market_filter dut (.*);

    task automatic check_state(
        input string label_text,
        input logic [31:0] credit, passed, dropped,
        input logic pass_pulse, drop_pulse,
        input logic [63:0] sequence_value
    );
        if ({remaining_drops, pass_count, drop_count, m_valid, drop_valid, m_mold_seq}
            !== {credit, passed, dropped, pass_pulse, drop_pulse, sequence_value})
            $fatal(1, "FAIL %s credit=%0d pass=%0d drop=%0d m_valid=%b drop_valid=%b seq=%h",
                   label_text, remaining_drops, pass_count, drop_count,
                   m_valid, drop_valid, m_mold_seq);
        cases = cases + 1;
        $display("CASE_PASS %0d %s credit=%0d pass=%0d drop=%0d seq=%h",
                 cases, label_text, remaining_drops, pass_count, drop_count, m_mold_seq);
    endtask

    task automatic send_message(input logic [287:0] message,
                                input logic [63:0] sequence_value);
        @(negedge clk);
        s_itch = message;
        s_mold_seq = sequence_value;
        s_valid = 1;
        if (s_ready !== 1'b1) $fatal(1, "input is not ready");
        @(posedge clk); #1;
    endtask

    task automatic load_credit(input logic [31:0] value);
        @(negedge clk);
        s_valid = 0;
        cfg_load_drops = value;
        cfg_load_valid = 1;
        #1;
        if (s_ready !== 1'b0) $fatal(1, "configuration must block input");
        @(posedge clk); #1;
        if (remaining_drops !== value || m_valid !== 1'b0 || drop_valid !== 1'b0)
            $fatal(1, "configuration failed");
        @(negedge clk);
        cfg_load_valid = 0;
        $display("CONTROL credit_loaded=%0d", value);
    endtask

    initial begin
        target_msg = 0;
        target_msg[287:280] = 8'h41; // ITCH Add Order (A)
        target_msg[279:264] = 16'd8095;
        target_msg[95:32] = 64'h4e56444120202020; // NVDA + four spaces
        $display("STAGE 1 reset and pass a matching message without credit");
        repeat (2) @(posedge clk);
        #1;
        check_state("reset_clears_state", 0, 0, 0, 0, 0, 0);
        @(negedge clk); rst_n = 1;
        send_message(target_msg, 64'h1234567800000064);
        check_state("default_allow_full_sequence", 0, 1, 0, 1, 0, 64'h1234567800000064);

        $display("STAGE 2 issue one credit while a message waits");
        @(negedge clk);
        s_mold_seq = 200;
        cfg_load_drops = 1;
        cfg_load_valid = 1;
        #1;
        if (s_ready !== 1'b0) $fatal(1, "pending input acknowledged during configuration");
        @(posedge clk); #1;
        check_state("configuration_holds_input", 1, 1, 0, 0, 0, 64'h1234567800000064);
        @(negedge clk); cfg_load_valid = 0;
        @(posedge clk); #1;
        check_state("first_target_drops", 0, 1, 1, 0, 1, 200);
        send_message(target_msg, 201);
        check_state("next_target_passes", 0, 2, 1, 1, 0, 201);
        @(negedge clk); s_valid = 0;
        @(posedge clk); #1;
        check_state("idle_does_not_recount", 0, 2, 1, 0, 0, 201);

        $display("STAGE 3 nonmatching fields preserve credit");
        load_credit(1);
        other_msg = target_msg; other_msg[287:280] = 8'h46;
        send_message(other_msg, 300);
        check_state("other_type_passes", 1, 3, 1, 1, 0, 300);
        other_msg = target_msg; other_msg[279:264] = 16'd8094;
        send_message(other_msg, 301);
        check_state("other_locate_passes", 1, 4, 1, 1, 0, 301);
        other_msg = target_msg; other_msg[95:32] = 64'h4141504c20202020;
        send_message(other_msg, 302);
        check_state("other_stock_passes", 1, 5, 1, 1, 0, 302);
        other_msg = target_msg; other_msg[39:32] = 8'h21;
        send_message(other_msg, 303);
        check_state("stock_padding_is_checked", 1, 6, 1, 1, 0, 303);
        send_message(target_msg, 64'hfedcba9876543210);
        check_state("target_drops_full_sequence", 0, 6, 2, 0, 1, 64'hfedcba9876543210);

        $display("STAGE 4 disarm and reset");
        load_credit(1);
        load_credit(0);
        send_message(target_msg, 304);
        check_state("disarmed_target_passes", 0, 7, 2, 1, 0, 304);
        @(negedge clk);
        rst_n = 0;
        cfg_load_valid = 1;
        cfg_load_drops = 1;
        @(posedge clk); #1;
        check_state("reset_wins_over_input_and_config", 0, 0, 0, 0, 0, 0);
        @(negedge clk);
        rst_n = 1; cfg_load_valid = 0; s_valid = 0;
        send_message(target_msg, 306);
        check_state("first_target_after_reset_passes", 0, 1, 0, 1, 0, 306);
        @(negedge clk); s_valid = 0;
        $display("RTL_GUI_SIMULATION=PASS cases=%0d hardware=NOT_RUN", cases);
        $finish;
    end

    initial begin
        #10000;
        $fatal(1, "simulation timeout");
    end
endmodule
