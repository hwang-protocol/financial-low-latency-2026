`timescale 1ns/1ps

module market_filter (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         s_valid,
    output logic         s_ready,
    input  logic [287:0] s_itch,
    input  logic [63:0]  s_mold_seq,
    input  logic [15:0]  cfg_locate,
    input  logic [63:0]  cfg_stock,
    input  logic [31:0]  cfg_load_drops,
    input  logic         cfg_load_valid,
    output logic         m_valid,
    output logic         drop_valid,
    output logic [63:0]  m_mold_seq,
    output logic [31:0]  remaining_drops,
    output logic [31:0]  pass_count,
    output logic [31:0]  drop_count
);
    logic [7:0]  in_type;
    logic [15:0] in_locate;
    logic [63:0] in_stock;
    logic        hit;

    assign in_type = s_itch[287:280];
    assign in_locate = s_itch[279:264];
    assign in_stock = s_itch[95:32];
    /* A configuration write owns the cycle; do not acknowledge packet input. */
    assign s_ready = !cfg_load_valid;
    assign hit = s_valid && s_ready && in_type == 8'h41 &&
                 in_locate == cfg_locate && in_stock == cfg_stock &&
                 remaining_drops != 32'd0;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            remaining_drops <= 32'd0;
            pass_count <= 32'd0;
            drop_count <= 32'd0;
            m_valid <= 1'b0;
            drop_valid <= 1'b0;
            m_mold_seq <= 64'd0;
        end else begin
            m_valid <= 1'b0;
            drop_valid <= 1'b0;
            if (cfg_load_valid)
                remaining_drops <= cfg_load_drops;
            else if (s_valid && s_ready) begin
                m_mold_seq <= s_mold_seq;
                if (hit) begin
                    remaining_drops <= remaining_drops - 32'd1;
                    drop_count <= drop_count + 32'd1;
                    drop_valid <= 1'b1;
                end else begin
                    pass_count <= pass_count + 32'd1;
                    m_valid <= 1'b1;
                end
            end
        end
    end
endmodule
