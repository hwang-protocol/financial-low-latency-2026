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
    state start {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control IngressImpl(inout Headers hdr, inout Metadata meta,
                    inout standard_metadata_t standard_metadata) {
    action forward(bit<9> port) {
        standard_metadata.egress_spec = port;
    }
    action drop() { mark_to_drop(standard_metadata); }
    table dst_exact {
        key = { hdr.ethernet.dst: exact; }
        actions = { forward; drop; }
        size = 16;
        default_action = drop();
    }
    apply { dst_exact.apply(); }
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
