#include <core.p4>
#include <v1model.p4>

header Ethernet {
    bit<48> dst;
    bit<48> src;
    bit<16> etherType;
}
struct Headers { Ethernet ethernet; }
struct Metadata { }

parser ParserImpl(packet_in packet, out Headers hdr,
                  inout Metadata meta,
                  inout standard_metadata_t standard_metadata) {
    state start { packet.extract(hdr.ethernet); transition accept; }
}

control IngressImpl(inout Headers hdr, inout Metadata meta,
                    inout standard_metadata_t standard_metadata) {
    counter(3, CounterType.packets) frame_class;

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
    apply {
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
    apply { packet.emit(hdr.ethernet); }
}

V1Switch(ParserImpl(), VerifyChecksumImpl(), IngressImpl(), EgressImpl(),
         ComputeChecksumImpl(), DeparserImpl()) main;
