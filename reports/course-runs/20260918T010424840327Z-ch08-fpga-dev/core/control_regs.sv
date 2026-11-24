// Word-indexed register interface, already synchronized into the packet clock.
// Connect wr_en/addr/data and readback through the selected FDK bus adapter.
module control_regs (
    input logic clk, rst, wr_en,
    input logic [3:0] wr_addr, rd_addr,
    input logic [31:0] wr_data,
    input logic armed,
    input logic [31:0] rx_count, tx_count, drop_count, error_count,
    input logic [63:0] last_sequence,
    output logic arm, disarm,
    output logic [31:0] rd_data
);
    always_ff @(posedge clk) begin
        if (rst) begin
            arm <= 0;
            disarm <= 0;
        end else begin
            arm    <= wr_en && wr_addr == 4'd1 && wr_data[0];
            disarm <= wr_en && wr_addr == 4'd1 && wr_data[1];
        end
    end
    always_comb begin
        case (rd_addr)
            0: rd_data = 32'h464c4c45; // ASCII FLLE, teaching application ID.
            1: rd_data = 32'd0;       // Write-one commands, not stored settings.
            2: rd_data = {31'd0, armed};
            3: rd_data = rx_count;
            4: rd_data = tx_count;
            5: rd_data = drop_count;
            6: rd_data = error_count;
            7: rd_data = last_sequence[63:32];
            8: rd_data = last_sequence[31:0];
            default: rd_data = 32'd0;
        endcase
    end
endmodule
