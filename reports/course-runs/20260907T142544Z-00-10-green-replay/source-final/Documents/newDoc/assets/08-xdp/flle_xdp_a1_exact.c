#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>

#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

#define FLLE_SRC_IPV4 0x14010101U
#define FLLE_DST_IPV4 0x1401010bU
#define FLLE_ICMP_ID 26418U
#define FLLE_TARGET_COUNT 8U
#define FLLE_MAGIC_0 0x464c4c45U
#define FLLE_MAGIC_1 0x58445031U
#define FLLE_COOKIE_HI 0x673112bbU
#define FLLE_COOKIE_LO 0xe2f3d77dU

struct flle_payload {
    __be32 magic_0;
    __be32 magic_1;
    __be32 cookie_hi;
    __be32 cookie_lo;
    __be16 sequence_copy;
} __attribute__((packed));

struct flle_icmp_echo {
    __u8 type;
    __u8 code;
    __sum16 checksum;
    __be16 identifier;
    __be16 sequence;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, FLLE_TARGET_COUNT + 1);
    __type(key, __u32);
    __type(value, __u64);
} flle_drop_cnt SEC(".maps");

static __always_inline void increment_counter(__u32 key)
{
    __u64 *value = bpf_map_lookup_elem(&flle_drop_cnt, &key);

    if (value)
        __sync_fetch_and_add(value, 1);
}

SEC("xdp")
int flle_xdp_a1_exact(struct xdp_md *ctx)
{
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;
    struct ethhdr *eth = data;
    struct iphdr *iph;
    struct flle_icmp_echo *icmp;
    struct flle_payload *payload;
    __u32 sequence;

    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;
    if (iph->version != 4 || iph->ihl != 5 || iph->protocol != IPPROTO_ICMP)
        return XDP_PASS;
    if (iph->saddr != bpf_htonl(FLLE_SRC_IPV4) ||
        iph->daddr != bpf_htonl(FLLE_DST_IPV4))
        return XDP_PASS;

    icmp = (void *)iph + sizeof(*iph);
    if ((void *)(icmp + 1) > data_end)
        return XDP_PASS;
    if (icmp->type != 8 || icmp->code != 0)
        return XDP_PASS;
    if (icmp->identifier != bpf_htons(FLLE_ICMP_ID))
        return XDP_PASS;

    sequence = bpf_ntohs(icmp->sequence);
    if (sequence < 1 || sequence > FLLE_TARGET_COUNT)
        return XDP_PASS;

    payload = (void *)(icmp + 1);
    if ((void *)(payload + 1) > data_end)
        return XDP_PASS;
    if (payload->magic_0 != bpf_htonl(FLLE_MAGIC_0) ||
        payload->magic_1 != bpf_htonl(FLLE_MAGIC_1) ||
        payload->cookie_hi != bpf_htonl(FLLE_COOKIE_HI) ||
        payload->cookie_lo != bpf_htonl(FLLE_COOKIE_LO) ||
        payload->sequence_copy != bpf_htons(sequence))
        return XDP_PASS;

    increment_counter(0);
    increment_counter(sequence);
    return XDP_DROP;
}

char LICENSE[] SEC("license") = "GPL";
