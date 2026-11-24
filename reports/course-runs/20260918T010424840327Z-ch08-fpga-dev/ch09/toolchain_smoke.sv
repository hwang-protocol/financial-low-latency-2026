module toolchain_smoke (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        in_valid,
    input  logic [15:0] in_data,
    output logic        out_valid,
    output logic [15:0] out_data
);
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_data  <= '0;
        end else begin
            out_valid <= in_valid;
            out_data  <= in_data + 16'h0001;
        end
    end
endmodule
