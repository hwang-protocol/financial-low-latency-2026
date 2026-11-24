// Portable teaching core. Single-buffer store-and-forward, not a line-rate design.
// The board adapter provides MAC/FCS handling, ingress buffering, CDC and registers.
// Earliest byte in a beat is s_data[7:0]; s_keep marks contiguous low byte lanes.
module frame_filter (
    input  logic        clk, rst,
    input  logic [63:0] s_data,
    input  logic [7:0]  s_keep,
    input  logic        s_valid, s_last, s_error,
    output logic        s_ready,
    output logic [63:0] m_data,
    output logic [7:0]  m_keep,
    output logic        m_valid, m_last,
    input  logic        m_ready,
    input  logic        arm, disarm,
    output logic        armed,
    output logic [31:0] rx_count, tx_count, drop_count, error_count,
    output logic [63:0] last_sequence
);
    localparam integer WORDS = 256; // 2048 bytes, excluding FCS.
    typedef enum logic [1:0] {RECEIVE, DECIDE, FORWARD} state_t;
    state_t state;
    logic [63:0] data_mem [0:WORDS-1];
    logic [7:0]  keep_mem [0:WORDS-1];
    logic [8:0] write_index, read_index, word_count;
    logic [15:0] byte_count;
    logic [799:0] prefix;
    logic bad_frame, match_nvda, drop_frame, decision_valid;
    logic [63:0] sequence_number;
    integer i, valid_bytes;
    logic keep_ok;

    always_comb begin
        valid_bytes = 0;
        for (integer k = 0; k < 8; k = k + 1)
            valid_bytes = valid_bytes + int'(s_keep[k]);
        keep_ok = s_last ? (s_keep != 0 && (s_keep & (s_keep + 1)) == 0)
                         : (s_keep == 8'hff);
    end

    assign s_ready = state == RECEIVE;
    assign m_valid = state == FORWARD;
    assign m_data  = data_mem[read_index[7:0]];
    assign m_keep  = keep_mem[read_index[7:0]];
    assign m_last  = m_valid && read_index == word_count - 1'b1;
    assign decision_valid = state == DECIDE && !bad_frame;

    nvda_match matcher(prefix, byte_count, match_nvda, sequence_number);
    drop_once policy(clk, rst, arm, disarm, decision_valid, match_nvda,
                     sequence_number, armed, drop_frame, drop_count, last_sequence);

    always_ff @(posedge clk) begin
        if (rst) begin
            state       <= RECEIVE;
            write_index <= 0;
            read_index  <= 0;
            word_count  <= 0;
            byte_count  <= 0;
            prefix      <= 0;
            bad_frame   <= 0;
            rx_count    <= 0;
            tx_count    <= 0;
            error_count <= 0;
        end else begin
            case (state)
                RECEIVE: if (s_valid && s_ready) begin
                    if (write_index < WORDS) begin
                        data_mem[write_index] <= s_data;
                        keep_mem[write_index] <= s_keep;
                        for (i = 0; i < 8; i = i + 1)
                            if (write_index*8+i < 100 && s_keep[i])
                                prefix[(write_index*8+i)*8 +: 8] <= s_data[i*8 +: 8];
                        write_index <= write_index + 1'b1;
                    end else begin
                        bad_frame <= 1'b1;
                    end
                    if (byte_count <= 2048)
                        byte_count <= byte_count + valid_bytes;
                    if (!keep_ok || s_error)
                        bad_frame <= 1'b1;
                    if (s_last) begin
                        word_count <= write_index + 1'b1;
                        rx_count <= rx_count + 1'b1;
                        state <= DECIDE;
                    end
                end
                DECIDE: begin
                    if (bad_frame || drop_frame) begin
                        if (bad_frame)
                            error_count <= error_count + 1'b1;
                        state <= RECEIVE;
                        write_index <= 0;
                        byte_count <= 0;
                        prefix <= 0;
                        bad_frame <= 0;
                    end else begin
                        read_index <= 0;
                        state <= FORWARD;
                    end
                end
                FORWARD: if (m_valid && m_ready) begin
                    if (m_last) begin
                        tx_count <= tx_count + 1'b1;
                        state <= RECEIVE;
                        write_index <= 0;
                        byte_count <= 0;
                        prefix <= 0;
                        bad_frame <= 0;
                    end else begin
                        read_index <= read_index + 1'b1;
                    end
                end
                default: state <= RECEIVE;
            endcase
        end
    end
endmodule
