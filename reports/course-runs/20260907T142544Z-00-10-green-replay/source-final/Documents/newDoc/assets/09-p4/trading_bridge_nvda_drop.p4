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
header ItchAdd {
    bit<16> locate;
    bit<16> tracking;
    bit<48> timestamp;
    bit<64> order_ref;
    bit<8> side;
    bit<32> shares;
    bit<64> stock;
    bit<32> price;
}
struct Headers {
    Ethernet ethernet; IPv4 ipv4; UDP udp; Mold mold;
    MessageLength message_length; ItchType itch_type; ItchAdd itch_add;
}
struct Metadata { bit<1> policy_hit; bit<1> policy_drop; }

parser ParserImpl(packet_in packet, out Headers hdr, inout Metadata meta,
                  inout standard_metadata_t standard_metadata) {
    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x0800: parse_ipv4;
            default: accept;
        }
    }
    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.ihl, hdr.ipv4.protocol) {
            (5, 17): parse_udp;
            default: accept;
        }
    }
    state parse_udp {
        packet.extract(hdr.udp);
        transition select(hdr.udp.dst) {
            42120: parse_mold;
            default: accept;
        }
    }
    state parse_mold {
        packet.extract(hdr.mold);
        transition select(hdr.mold.count) {
            0: accept;
            1: parse_message_length;
            default: accept;
        }
    }
    state parse_message_length {
        packet.extract(hdr.message_length);
        transition select(hdr.message_length.value) {
            36: parse_itch_type;
            default: accept;
        }
    }
    state parse_itch_type {
        packet.extract(hdr.itch_type);
        transition select(hdr.itch_type.value) {
            0x41: parse_itch_add;
            default: accept;
        }
    }
    state parse_itch_add { packet.extract(hdr.itch_add); transition accept; }
}

control IngressImpl(inout Headers hdr, inout Metadata meta,
                    inout standard_metadata_t standard_metadata) {
    counter(3, CounterType.packets) frame_class;
    counter(2, CounterType.packets) stock_packets;
    counter(1, CounterType.packets) policy_drop_packets;
    register<bit<32>>(1) remaining_drops;
    register<bit<64>>(1) dropped_sequence;

    action drop() { mark_to_drop(standard_metadata); }
    action forward(bit<9> port) {
        frame_class.count(0);
        standard_metadata.egress_spec = port;
    }
    action peer(bit<9> port) {
        frame_class.count(1);
        standard_metadata.egress_spec = port;
    }
    table unicast_dst {
        key = { hdr.ethernet.dst: exact; }
        actions = { forward; drop; }
        size = 16;
        default_action = drop();
    }

    action select_policy() { meta.policy_hit = 1; }
    table market_policy {
        key = {
            hdr.ipv4.src: exact;
            hdr.ipv4.dst: exact;
            hdr.itch_type.value: exact;
            hdr.itch_add.locate: exact;
            hdr.itch_add.stock: exact;
        }
        actions = { select_policy; NoAction; }
        size = 8;
        default_action = NoAction();
    }

    apply {
        meta.policy_hit = 0;
        meta.policy_drop = 0;
        if (hdr.itch_add.isValid()) {
            if (hdr.itch_add.stock == 0x4141504c20202020)
                stock_packets.count(0);
            else if (hdr.itch_add.stock == 0x4e56444120202020)
                stock_packets.count(1);
            if (hdr.ipv4.flags[0:0] == 0 && hdr.ipv4.fragOffset == 0) {
                market_policy.apply();
                if (meta.policy_hit == 1) {
                    bit<32> left;
                    /* The one-shot read/update is one transaction on targets
                     * that implement P4 atomic blocks. */
                    @atomic {
                        remaining_drops.read(left, 0);
                        if (left > 0) {
                            remaining_drops.write(0, left - 1);
                            dropped_sequence.write(0, hdr.mold.sequence);
                        }
                    }
                    if (left > 0) {
                        policy_drop_packets.count(0);
                        meta.policy_drop = 1;
                        drop();
                        return;
                    }
                }
            }
        }
        if ((hdr.ethernet.dst & 0xfffffffffff0) == 0x0180c2000000) {
            frame_class.count(2);
            drop();
        } else if (hdr.ethernet.dst[40:40] == 1) {
            if (standard_metadata.ingress_port == 1)
                peer(2);
            else if (standard_metadata.ingress_port == 2)
                peer(1);
            else
                drop();
        } else {
            unicast_dst.apply();
        }
    }
}

control VerifyChecksumImpl(inout Headers hdr, inout Metadata meta) { apply { } }
control EgressImpl(inout Headers hdr, inout Metadata meta,
                   inout standard_metadata_t standard_metadata) { apply { } }
control ComputeChecksumImpl(inout Headers hdr, inout Metadata meta) { apply { } }
control DeparserImpl(packet_out packet, in Headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.mold);
        packet.emit(hdr.message_length);
        packet.emit(hdr.itch_type);
        packet.emit(hdr.itch_add);
    }
}

V1Switch(ParserImpl(), VerifyChecksumImpl(), IngressImpl(), EgressImpl(),
         ComputeChecksumImpl(), DeparserImpl()) main;
