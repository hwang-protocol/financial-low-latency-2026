// arm/disarm must be one-cycle pulses synchronized to clk by the board adapter.
module drop_once (
    input  logic        clk, rst,
    input  logic        arm, disarm,
    input  logic        decision_valid, match_nvda,
    input  logic [63:0] sequence_number,
    output logic        armed, drop_frame,
    output logic [31:0] drop_count,
    output logic [63:0] last_sequence
);
    // A control command on the decision edge takes priority over consumption.
    assign drop_frame = decision_valid && match_nvda && armed && !disarm && !arm;

    always_ff @(posedge clk) begin
        if (rst) begin
            armed        <= 1'b0;
            drop_count   <= 32'd0;
            last_sequence <= 64'd0;
        end else begin
            if (disarm)
                armed <= 1'b0;
            else if (arm)
                armed <= 1'b1;
            else if (drop_frame)
                armed <= 1'b0;

            if (drop_frame) begin
                drop_count    <= drop_count + 1'b1;
                last_sequence <= sequence_number;
            end
        end
    end
endmodule
