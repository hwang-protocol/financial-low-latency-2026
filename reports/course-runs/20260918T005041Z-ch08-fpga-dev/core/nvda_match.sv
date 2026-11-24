// Teaching profile: untagged Ethernet / IPv4 IHL=5 / UDP / one ITCH message.
// Byte 0 is the first destination-MAC byte, stored in prefix[7:0]. No FCS.
module nvda_match (
    input  logic [799:0] prefix,
    input  logic [15:0]  frame_bytes,
    output logic         match_nvda,
    output logic [63:0]  sequence_number
);
    function automatic [7:0] octet(input logic [799:0] bytes, input integer n);
        octet = bytes[n*8 +: 8];
    endfunction

    logic transport_ok, message_ok;
    assign transport_ok =
        frame_bytes == 16'd100 &&
        {octet(prefix, 12), octet(prefix, 13)} == 16'h0800 &&
        octet(prefix, 14) == 8'h45 && octet(prefix, 23) == 8'd17 &&
        ({octet(prefix, 20), octet(prefix, 21)} & 16'h3fff) == 16'd0 &&
        {octet(prefix, 16), octet(prefix, 17)} == 16'd86 &&
        {octet(prefix, 26), octet(prefix, 27), octet(prefix, 28), octet(prefix, 29)} == 32'h14010101 &&
        {octet(prefix, 30), octet(prefix, 31), octet(prefix, 32), octet(prefix, 33)} == 32'he94a7d20 &&
        {octet(prefix, 36), octet(prefix, 37)} == 16'd31032 &&
        {octet(prefix, 38), octet(prefix, 39)} == 16'd66;

    assign message_ok =
        {octet(prefix, 60), octet(prefix, 61)} == 16'd1 &&
        {octet(prefix, 62), octet(prefix, 63)} == 16'd36 &&
        octet(prefix, 64) == 8'h41 &&
        {octet(prefix, 65), octet(prefix, 66)} == 16'd8095 &&
        {octet(prefix, 88), octet(prefix, 89), octet(prefix, 90), octet(prefix, 91),
         octet(prefix, 92), octet(prefix, 93), octet(prefix, 94), octet(prefix, 95)} == 64'h4e56444120202020;

    assign match_nvda = transport_ok && message_ok;
    assign sequence_number = {
        octet(prefix, 52), octet(prefix, 53), octet(prefix, 54), octet(prefix, 55),
        octet(prefix, 56), octet(prefix, 57), octet(prefix, 58), octet(prefix, 59)
    };
endmodule
