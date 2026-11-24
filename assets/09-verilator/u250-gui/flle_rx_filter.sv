`timescale 1ns/1ps
// FLLE-authored receive-path adapter; not an AMD/OpenNIC source file.
// Simulation-stage interface: configuration and reset are synchronous to clk.
// One arm command gives ONE drop credit. Reset starts with zero credit.
// Profile: untagged Ethernet, IPv4 IHL=5, UDP, one 36-byte MoldUDP64 message.
// Other frames pass unchanged. Byte zero occupies tdata[7:0]. FCS is absent.
module flle_rx_filter #(
    parameter logic [31:0] SOURCE_IP = 32'h14010101,
    parameter logic [31:0] GROUP_IP = 32'he94a7d20,
    parameter logic [15:0] DEST_PORT = 16'd31032,
    parameter logic [15:0] STOCK_LOCATE = 16'd8095,
    parameter logic [63:0] STOCK = 64'h4e56444120202020,
    // Zero retains the original standalone test behavior. The board wrapper
    // enables a five-second limit at 250 MHz. Expiry wins over a new verdict.
    parameter logic [31:0] ARM_TIMEOUT_CYCLES = 0
) (
    input logic clk, rst_n,
    input logic cfg_valid, cfg_arm,
    output logic cfg_ready,
    input logic s_axis_tvalid,
    output logic s_axis_tready,
    input logic [511:0] s_axis_tdata,
    input logic [63:0] s_axis_tkeep,
    input logic s_axis_tlast,
    input logic [47:0] s_axis_tuser,
    output logic m_axis_tvalid,
    input logic m_axis_tready,
    output logic [511:0] m_axis_tdata,
    output logic [63:0] m_axis_tkeep,
    output logic m_axis_tlast,
    output logic [47:0] m_axis_tuser,
    output logic [31:0] passed_frames, dropped_frames, remaining_drops,
    output logic [63:0] last_drop_sequence
);
    typedef enum logic [2:0] {FIRST, SECOND, CHECKSUM, CHECK, WAIT_DECISION,
                              REPLAY0, REPLAY1, TAIL} state_t;
    state_t state;
    logic [511:0] data0, data1;
    logic [63:0] keep0, keep1;
    logic last0, last1;
    logic [47:0] user0, user1;
    wire [1023:0] prefix = {data1, data0};
    logic [287:0] itch;
    logic [63:0] sequence_number;
    logic profile_ok, core_valid, core_ready, core_pass, core_drop;
    logic [63:0] core_sequence;
    logic [3:0] checksum_step;
    // Balanced, registered reduction trees. Each stage adds only two words;
    // no packet-to-core enable path crosses the complete checksum arithmetic.
    wire [15:0] checksum_words [0:1][0:63];
    logic [16:0] checksum_fold1 [0:1], checksum_fold2 [0:1];
    logic [31:0] arm_timer;
    wire config_fire = cfg_valid && cfg_ready;
    wire expire_credit = (ARM_TIMEOUT_CYCLES != 0) &&
                         (arm_timer == 1) && (remaining_drops != 0);

    always_ff @(posedge clk) begin
        if (!rst_n) arm_timer <= 0;
        else if (config_fire)
            arm_timer <= cfg_arm ? ARM_TIMEOUT_CYCLES : 32'd0;
        else if (remaining_drops == 0) arm_timer <= 0;
        else if (arm_timer != 0) arm_timer <= arm_timer - 1;
    end

    function automatic [7:0] octet(input integer n);
        octet = prefix[n*8 +: 8];
    endfunction
    function automatic [15:0] word_be(input integer n);
        word_be = {octet(n), octet(n+1)};
    endfunction

    for (genvar w = 0; w < 64; w = w+1) begin : checksum_input
        if (w < 10) assign checksum_words[0][w] =
            {prefix[(14+2*w)*8 +: 8], prefix[(15+2*w)*8 +: 8]};
        else assign checksum_words[0][w] = 16'd0;
        // UDP pseudo-header: protocol + length, addresses, then all UDP bytes.
        if (w == 0) assign checksum_words[1][w] = 16'd83;
        else if (w < 5) assign checksum_words[1][w] =
            {prefix[(26+2*(w-1))*8 +: 8], prefix[(27+2*(w-1))*8 +: 8]};
        else if (w < 38) assign checksum_words[1][w] =
            {prefix[(34+2*(w-5))*8 +: 8], prefix[(35+2*(w-5))*8 +: 8]};
        else assign checksum_words[1][w] = 16'd0;
    end
    for (genvar c = 0; c < 2; c = c+1) begin : checksum_tree
        logic [16:0] sum1 [0:31];
        logic [17:0] sum2 [0:15];
        logic [18:0] sum3 [0:7];
        logic [19:0] sum4 [0:3];
        logic [20:0] sum5 [0:1];
        logic [21:0] sum6;
        // Carry folding also has register boundaries, then a registered verdict.
        // These data registers need no reset: CHECKSUM waits for all eight
        // arithmetic stages to fill from the current stable packet buffers.
        always_ff @(posedge clk) begin
            for (integer n = 0; n < 32; n = n+1)
                sum1[n] <= {1'b0, checksum_words[c][2*n]} +
                           {1'b0, checksum_words[c][2*n+1]};
            for (integer n = 0; n < 16; n = n+1)
                sum2[n] <= {1'b0, sum1[2*n]} + {1'b0, sum1[2*n+1]};
            for (integer n = 0; n < 8; n = n+1)
                sum3[n] <= {1'b0, sum2[2*n]} + {1'b0, sum2[2*n+1]};
            for (integer n = 0; n < 4; n = n+1)
                sum4[n] <= {1'b0, sum3[2*n]} + {1'b0, sum3[2*n+1]};
            for (integer n = 0; n < 2; n = n+1)
                sum5[n] <= {1'b0, sum4[2*n]} + {1'b0, sum4[2*n+1]};
            sum6 <= {1'b0, sum5[0]} + {1'b0, sum5[1]};
            checksum_fold1[c] <= {1'b0, sum6[15:0]} + {11'd0, sum6[21:16]};
            checksum_fold2[c] <= {1'b0, checksum_fold1[c][15:0]} +
                                {16'd0, checksum_fold1[c][16]};
        end
    end

    always_comb begin
        for (integer j = 0; j < 36; j = j+1)
            itch[287-j*8 -: 8] = octet(64+j);
        for (integer j = 0; j < 8; j = j+1)
            sequence_number[63-j*8 -: 8] = octet(52+j);
    end

    always_ff @(posedge clk) begin
        if (!rst_n) profile_ok <= 0;
        else if (state == CHECKSUM && checksum_step == 8)
            profile_ok <= !last0 && last1 && keep0 == 64'hffffffffffffffff &&
            keep1 == 64'h0000000fffffffff &&
            word_be(12) == 16'h0800 && octet(14) == 8'h45 &&
            word_be(16) == 16'd86 && (word_be(20) & 16'hbfff) == 0 &&
            octet(23) == 8'd17 &&
            {word_be(26), word_be(28)} == SOURCE_IP &&
            {word_be(30), word_be(32)} == GROUP_IP &&
            word_be(36) == DEST_PORT && word_be(38) == 16'd66 &&
            checksum_fold2[0] == 17'h0ffff &&
            (word_be(40) == 0 || checksum_fold2[1] == 17'h0ffff) &&
            word_be(60) == 16'd1 && word_be(62) == 16'd36;
    end

    assign cfg_ready = rst_n && state == FIRST;
    assign core_valid = rst_n && state == CHECK && profile_ok;
    market_filter core (
        .clk(clk), .rst_n(rst_n), .s_valid(core_valid), .s_ready(core_ready),
        .s_itch(itch), .s_mold_seq(sequence_number),
        .cfg_locate(STOCK_LOCATE), .cfg_stock(STOCK),
        .cfg_load_drops({31'd0, config_fire && cfg_arm}),
        .cfg_load_valid(config_fire || expire_credit),
        .m_valid(core_pass), .drop_valid(core_drop), .m_mold_seq(core_sequence),
        .remaining_drops(remaining_drops), .pass_count(), .drop_count()
    );

    always_comb begin
        s_axis_tready = 0;
        m_axis_tvalid = 0;
        m_axis_tdata = data0;
        m_axis_tkeep = keep0;
        m_axis_tlast = last0;
        m_axis_tuser = user0;
        if (rst_n) begin
            case (state)
                FIRST: s_axis_tready = !cfg_valid;
                SECOND: s_axis_tready = 1;
                REPLAY0: m_axis_tvalid = 1;
                REPLAY1: begin
                    m_axis_tvalid = 1;
                    m_axis_tdata = data1;
                    m_axis_tkeep = keep1;
                    m_axis_tlast = last1;
                    m_axis_tuser = user1;
                end
                TAIL: begin
                    s_axis_tready = m_axis_tready;
                    m_axis_tvalid = s_axis_tvalid;
                    m_axis_tdata = s_axis_tdata;
                    m_axis_tkeep = s_axis_tkeep;
                    m_axis_tlast = s_axis_tlast;
                    m_axis_tuser = s_axis_tuser;
                end
                default: begin end
            endcase
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state <= FIRST;
            checksum_step <= 0;
            data0 <= 0; data1 <= 0; keep0 <= 0; keep1 <= 0;
            user0 <= 0; user1 <= 0; last0 <= 0; last1 <= 0;
            passed_frames <= 0; dropped_frames <= 0; last_drop_sequence <= 0;
        end else begin
            if (m_axis_tvalid && m_axis_tready && m_axis_tlast)
                passed_frames <= passed_frames + 1;
            case (state)
                FIRST: if (s_axis_tvalid && s_axis_tready) begin
                    data0 <= s_axis_tdata; keep0 <= s_axis_tkeep;
                    user0 <= s_axis_tuser; last0 <= s_axis_tlast;
                    state <= s_axis_tlast ? REPLAY0 : SECOND;
                end
                SECOND: if (s_axis_tvalid && s_axis_tready) begin
                    data1 <= s_axis_tdata; keep1 <= s_axis_tkeep;
                    user1 <= s_axis_tuser; last1 <= s_axis_tlast;
                    checksum_step <= 0;
                    state <= CHECKSUM;
                end
                CHECKSUM: begin
                    if (checksum_step == 8) state <= CHECK;
                    else checksum_step <= checksum_step + 1'b1;
                end
                CHECK: begin
                    if (!profile_ok) state <= REPLAY0;
                    else if (core_ready) state <= WAIT_DECISION;
                end
                WAIT_DECISION: begin
                    if (core_drop) begin
                        dropped_frames <= dropped_frames + 1;
                        last_drop_sequence <= core_sequence;
                        state <= FIRST;
                    end else if (core_pass) state <= REPLAY0;
                end
                REPLAY0: if (m_axis_tready) state <= last0 ? FIRST : REPLAY1;
                REPLAY1: if (m_axis_tready) state <= last1 ? FIRST : TAIL;
                TAIL: if (s_axis_tvalid && s_axis_tready && s_axis_tlast)
                    state <= FIRST;
                default: state <= FIRST;
            endcase
        end
    end
endmodule
