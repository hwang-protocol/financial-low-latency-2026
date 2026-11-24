#include <core.p4>
#include <v1model.p4>

header Ethernet { bit<48> dst; bit<48> src; bit<16> etherType; }
header IPv4 { bit<4> version; bit<4> ihl; bit<8> diffserv; bit<16> totalLen;
    bit<16> identification; bit<3> flags; bit<13> fragOffset; bit<8> ttl;
    bit<8> protocol; bit<16> checksum; bit<32> src; bit<32> dst; }
header UDP { bit<16> src; bit<16> dst; bit<16> length; bit<16> checksum; }
header Mold { bit<80> session; bit<64> sequence; bit<16> count; }
header MessageLength { bit<16> value; }
header ItchType { bit<8> value; }
header ItchStock { bit<184> before_stock; bit<64> stock; }
struct Headers { Ethernet ethernet; IPv4 ipv4; UDP udp; Mold mold;
    MessageLength message_length; ItchType itch_type; ItchStock itch_stock; }
struct Metadata { }

parser ParserImpl(packet_in packet, out Headers hdr, inout Metadata meta,
                  inout standard_metadata_t standard_metadata) {
    state start { packet.extract(hdr.ethernet); transition select(hdr.ethernet.etherType) { 0x0800: parse_ipv4; default: accept; } }
    state parse_ipv4 { packet.extract(hdr.ipv4); transition select(hdr.ipv4.ihl, hdr.ipv4.protocol) { (5,17): parse_udp; default: accept; } }
    state parse_udp { packet.extract(hdr.udp); transition select(hdr.udp.dst) { 42120: parse_mold; default: accept; } }
    state parse_mold { packet.extract(hdr.mold); transition select(hdr.mold.count) { 0: accept; 0xffff: accept; default: parse_message_length; } }
    state parse_message_length { packet.extract(hdr.message_length); transition parse_itch_type; }
    state parse_itch_type { packet.extract(hdr.itch_type); transition select(hdr.itch_type.value) { 0x41: parse_itch_stock; 0x46: parse_itch_stock; 0x50: parse_itch_stock; default: accept; } }
    state parse_itch_stock { packet.extract(hdr.itch_stock); transition accept; }
}

control IngressImpl(inout Headers hdr, inout Metadata meta,
                    inout standard_metadata_t standard_metadata) {
    counter(3, CounterType.packets) frame_class;
    counter(2, CounterType.packets) stock_packets;
    action drop() { mark_to_drop(standard_metadata); }
    action forward(bit<9> port) { frame_class.count(0); standard_metadata.egress_spec = port; }
    action peer(bit<9> port) { frame_class.count(1); standard_metadata.egress_spec = port; }
    table unicast_dst { key = { hdr.ethernet.dst: exact; } actions = { forward; drop; }
        size = 16; default_action = drop(); }
    apply {
        if (hdr.itch_stock.isValid()) {
            if (hdr.itch_stock.stock == 0x4141504c20202020) stock_packets.count(0);
            else if (hdr.itch_stock.stock == 0x4e56444120202020) stock_packets.count(1);
        }
        if ((hdr.ethernet.dst & 0xfffffffffff0) == 0x0180c2000000) {
            frame_class.count(2); drop();
        } else if (hdr.ethernet.dst[40:40] == 1) {
            if (standard_metadata.ingress_port == 1) peer(2);
            else if (standard_metadata.ingress_port == 2) peer(1);
            else drop();
        }
        else unicast_dst.apply();
    }
}
control VerifyChecksumImpl(inout Headers hdr, inout Metadata meta) { apply { } }
control EgressImpl(inout Headers hdr, inout Metadata meta,
                   inout standard_metadata_t standard_metadata) { apply { } }
control ComputeChecksumImpl(inout Headers hdr, inout Metadata meta) { apply { } }
control DeparserImpl(packet_out packet, in Headers hdr) { apply {
    packet.emit(hdr.ethernet); packet.emit(hdr.ipv4); packet.emit(hdr.udp);
    packet.emit(hdr.mold); packet.emit(hdr.message_length); packet.emit(hdr.itch_type);
    packet.emit(hdr.itch_stock); } }
V1Switch(ParserImpl(), VerifyChecksumImpl(), IngressImpl(), EgressImpl(),
         ComputeChecksumImpl(), DeparserImpl()) main;
