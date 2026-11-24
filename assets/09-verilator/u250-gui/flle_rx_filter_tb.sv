`timescale 1ns/1ps
// FLLE-authored simulation stimulus and scoreboard, not synthesizable hardware.
module flle_rx_filter_tb #(parameter bit EXTRA_PIPELINE_TESTS = 0);
    logic clk = 0;
    always #2 clk = ~clk;
    logic rst_n = 0, cfg_valid = 0, cfg_arm = 0, cfg_ready;
    logic s_axis_tvalid = 0, s_axis_tready, s_axis_tlast = 0;
    logic [511:0] s_axis_tdata = 0;
    logic [63:0] s_axis_tkeep = 0;
    logic [47:0] s_axis_tuser = 0;
    logic m_axis_tvalid, m_axis_tready = 0, m_axis_tlast;
    logic [511:0] m_axis_tdata;
    logic [63:0] m_axis_tkeep;
    logic [47:0] m_axis_tuser;
    logic [31:0] passed_frames, dropped_frames, remaining_drops;
    logic [63:0] last_drop_sequence;
    flle_rx_filter dut (.*);

    byte unsigned frame [0:2047];
    logic [624:0] expected [0:2047];
    integer wr = 0, rd = 0, cycle = 0, cases = 0;
    integer expected_pass = 0, expected_drop = 0;
    logic stalled = 0, force_stall = 0;
    logic [624:0] held;
    integer payload_seed = 32'h12345678;

    // Independent whole-beat scoreboard: data, byte enables, EOP and metadata.
    always @(posedge clk) begin
        if (!rst_n) stalled = 0;
        else begin
            if (stalled && (!m_axis_tvalid ||
                {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser} !== held))
                $fatal(1, "Output changed under backpressure");
            if (m_axis_tvalid && m_axis_tready) begin
                if (rd >= wr) $fatal(1, "Unexpected output beat %0d", rd);
                if ({m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser} !== expected[rd])
                    $fatal(1, "Output mismatch at beat %0d", rd);
                rd = rd + 1;
            end
            stalled = m_axis_tvalid && !m_axis_tready;
            held = {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser};
        end
    end
    always @(negedge clk) begin
        cycle = cycle + 1;
        m_axis_tready = !force_stall && ((cycle % 7) >= 3);
    end

    task automatic checksums(input bit udp_enabled);
        integer sum, c;
        frame[24] = 0; frame[25] = 0;
        sum = 0;
        for (integer i = 14; i < 34; i = i+2)
            sum = sum + (int'(frame[i]) << 8) + int'(frame[i+1]);
        sum = (sum & 65535) + (sum >> 16);
        c = (~sum) & 65535;
        frame[24] = 8'(c >> 8); frame[25] = 8'(c);
        frame[40] = 0; frame[41] = 0;
        if (udp_enabled) begin
            sum = 17 + 66;
            for (integer i = 26; i < 100; i = i+2)
                sum = sum + (int'(frame[i]) << 8) + int'(frame[i+1]);
            sum = (sum & 65535) + (sum >> 16);
            sum = (sum & 65535) + (sum >> 16);
            c = (~sum) & 65535;
            if (c == 0) c = 65535;
            frame[40] = 8'(c >> 8); frame[41] = 8'(c);
        end
    endtask

    task automatic make_frame(input logic [63:0] seq);
        for (integer i = 0; i < 2048; i = i+1) frame[i] = 8'(i);
        frame[12] = 8'h08; frame[13] = 0;
        frame[14] = 8'h45; frame[16] = 0; frame[17] = 86;
        frame[20] = 0; frame[21] = 0; frame[22] = 64; frame[23] = 17;
        frame[26] = 20; frame[27] = 1; frame[28] = 1; frame[29] = 1;
        frame[30] = 233; frame[31] = 74; frame[32] = 125; frame[33] = 32;
        frame[36] = 8'h79; frame[37] = 8'h38;
        frame[38] = 0; frame[39] = 66;
        for (integer i = 0; i < 8; i = i+1) frame[52+i] = seq[63-8*i -: 8];
        frame[60] = 0; frame[61] = 1; frame[62] = 0; frame[63] = 36;
        frame[64] = "A"; frame[65] = 8'h1f; frame[66] = 8'h9f;
        frame[88] = "N"; frame[89] = "V"; frame[90] = "D"; frame[91] = "A";
        frame[92] = " "; frame[93] = " "; frame[94] = " "; frame[95] = " ";
        checksums(1);
    endtask

    task automatic configure(input bit arm);
        @(negedge clk);
        cfg_arm = arm; cfg_valid = 1;
        do @(posedge clk); while (!cfg_ready);
        @(negedge clk); cfg_valid = 0;
    endtask

    task automatic send_frame(input integer length, input bit drop_expected,
                              input bit broken_keep);
        logic [511:0] data;
        logic [63:0] keep;
        logic [47:0] user_bits;
        bit last;
        for (integer base = 0; base < length; base = base+64) begin
            data = 0; keep = 0; last = (base+64 >= length);
            for (integer j = 0; j < 64; j = j+1)
                if (base+j < length) begin
                    data[j*8 +: 8] = frame[base+j]; keep[j] = 1;
                end
            if (broken_keep && base == 0) keep[7] = 0;
            user_bits = {16'(base+7), 16'h1234, 16'(length)};
            if (!drop_expected) begin
                expected[wr] = {data,keep,last,user_bits}; wr = wr+1;
            end
            @(negedge clk);
            s_axis_tdata = data; s_axis_tkeep = keep;
            s_axis_tlast = last; s_axis_tuser = user_bits; s_axis_tvalid = 1;
            do @(posedge clk); while (!s_axis_tready);
            @(negedge clk); s_axis_tvalid = 0;
        end
        if (drop_expected) expected_drop = expected_drop+1;
        else expected_pass = expected_pass+1;
    endtask

    task automatic finish_case(input string name);
        // cfg_ready also proves the adapter returned to the frame boundary.
        wait (cfg_ready && rd == wr);
        @(negedge clk);
        if (passed_frames !== 32'(expected_pass) || dropped_frames !== 32'(expected_drop))
            $fatal(1, "%s counters got %0d/%0d expected %0d/%0d", name,
                   passed_frames, dropped_frames, expected_pass, expected_drop);
        cases = cases+1;
        $display("CASE_PASS %0d %s", cases, name);
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst_n = 1;
        make_frame(1); send_frame(100,0,0); finish_case("reset_has_no_drop_credit");
        configure(1);
        make_frame(2); send_frame(100,1,0); finish_case("armed_target_entire_frame_dropped");
        if (remaining_drops != 0 || last_drop_sequence != 2) $fatal(1,"drop audit");
        make_frame(3); send_frame(100,0,0); finish_case("next_target_passes");
        configure(1);
        for (integer variant = 0; variant < 14; variant = variant+1) begin
            make_frame(64'(100+variant));
            case (variant)
                0: frame[66] = 0;       // other locate
                1: frame[91] = "X";     // other symbol
                2: frame[64] = "F";     // other ITCH type
                3: frame[29] = 9;       // other source
                4: frame[33] = 33;      // other group
                5: frame[37] = 0;       // other port
                6: frame[20] = 8'h20;   // fragmented IP
                7: frame[14] = 8'h46;   // IP options
                8: frame[61] = 2;       // multiple messages
                9: frame[63] = 35;      // wrong message size
                10: frame[13] = 8'hdd;  // other ethertype
                11: frame[39] = 65;     // wrong UDP size
                12: frame[17] = 85;     // wrong IP size
                13: frame[23] = 6;      // non UDP
            endcase
            checksums(1);
            send_frame(100,0,0); finish_case($sformatf("non_target_variant_%0d",variant));
            if (remaining_drops != 1) $fatal(1,"non-target consumed credit");
        end
        make_frame(200); frame[24] = frame[24] ^ 8'h01;
        send_frame(100,0,0); finish_case("bad_ip_checksum_bypasses");
        make_frame(201); frame[41] = frame[41] ^ 8'h01;
        send_frame(100,0,0); finish_case("bad_udp_checksum_bypasses");
        make_frame(202); send_frame(100,0,1); finish_case("sparse_keep_bypasses");
        make_frame(203); send_frame(99,0,0); finish_case("truncated_frame_bypasses");
        make_frame(204); send_frame(1518,0,0); finish_case("long_frame_tail_and_backpressure");
        make_frame(205); send_frame(60,0,0); finish_case("one_beat_frame");
        make_frame(206); checksums(0);
        send_frame(100,1,0); finish_case("zero_udp_checksum_allowed_ipv4");
        if (last_drop_sequence != 206) $fatal(1,"sequence endian mismatch");
        configure(1); configure(0);
        make_frame(207); send_frame(100,0,0); finish_case("disarm_restores_pass");
        // Queue several packets without waiting for the adapter to become idle.
        make_frame(208); send_frame(100,0,0);
        make_frame(209); send_frame(100,0,0);
        make_frame(210); send_frame(1518,0,0); finish_case("consecutive_packets");
        // Configuration is held until the previous packet fully exits.
        force_stall = 1;
        make_frame(211); send_frame(100,0,0);
        @(negedge clk); cfg_valid = 1; cfg_arm = 1;
        repeat (5) begin
            @(negedge clk);
            if (cfg_ready) $fatal(1,"configuration accepted inside packet");
        end
        force_stall = 0;
        do @(posedge clk); while (!cfg_ready);
        @(negedge clk); cfg_valid = 0;
        finish_case("configuration_waits_for_packet_boundary");
        make_frame(212); send_frame(100,1,0); finish_case("deferred_arm_applies_next_packet");
        // Reset aborts buffered traffic, clears accounting and cancels credit.
        configure(1); force_stall = 1;
        make_frame(213); frame[64] = "F"; checksums(1);
        send_frame(100,0,0);
        repeat (4) @(negedge clk);
        rst_n = 0;
        repeat (3) @(negedge clk);
        wr = 0; rd = 0; expected_pass = 0; expected_drop = 0;
        rst_n = 1; force_stall = 0;
        make_frame(214); send_frame(100,0,0); finish_case("reset_aborts_buffered_packet_and_credit");
        if (EXTRA_PIPELINE_TESTS) begin
            // Independently generated nonzero UDP checksums with varied carry
            // patterns. Corruption must bypass without consuming the credit;
            // restoring the same packet must drop it exactly once.
            for (integer variant = 0; variant < 32; variant = variant+1) begin
                configure(1); make_frame(64'(500+variant));
                for (integer b = 42; b < 100; b = b+1)
                    if ((b < 52) || (b >= 67 && b < 88) || b >= 96)
                        frame[b] = variant == 0 ? 8'hff :
                                   variant == 1 ? 8'h00 : 8'($random(payload_seed));
                checksums(1);
                frame[99] = frame[99] ^ 8'h01;
                send_frame(100,0,0); finish_case("varied_checksum_corrupt_bypasses");
                if (remaining_drops != 1) $fatal(1,"corrupt packet consumed credit");
                frame[99] = frame[99] ^ 8'h01;
                send_frame(100,1,0); finish_case("varied_checksum_valid_drops");
                if (remaining_drops != 0 || last_drop_sequence != 64'(500+variant))
                    $fatal(1,"varied checksum sequence/credit mismatch");
            end
            // Interrupt each arithmetic/verdict cycle with reset. No stale
            // checksum or pending packet may leak into the following frame.
            for (integer delay_cycles = 0; delay_cycles < 9; delay_cycles = delay_cycles+1) begin
                configure(1); make_frame(64'(700+delay_cycles));
                force_stall = 1; send_frame(100,1,0);
                repeat(delay_cycles) @(negedge clk);
                rst_n = 0;
                repeat(3) @(negedge clk);
                wr = 0; rd = 0; expected_pass = 0; expected_drop = 0;
                rst_n = 1; force_stall = 0;
                make_frame(64'(800+delay_cycles)); send_frame(100,0,0);
                finish_case("reset_during_checksum_then_fresh_frame");
                if (remaining_drops != 0 || last_drop_sequence != 0)
                    $fatal(1,"pipeline reset left credit/audit");
            end
        end
        $display("U250_RX_ADAPTER_SIMULATION=PASS cases=%0d hardware=NOT_RUN", cases);
        $finish;
    end
    initial begin
        #200000;
        $fatal(1,"Simulation timeout");
    end
endmodule
