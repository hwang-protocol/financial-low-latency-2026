#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>
#include <linux/udp.h>

#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

#define FEED_SOURCE 0xac1f0a2bU  /* AWS: 172.31.10.43 (course 20.1.1.1) */
#define FEED_GROUP  0xac1f0c9cU  /* AWS unicast dst 172.31.12.156 (course group 233.74.125.32) */
#define FEED_PORT   42121  /* AWS unicast port (course 31032) */
#define IPV4_FRAGMENT_MASK 0x3fff
#define ITCH_ADD_LEN 36
#define NVDA_LOCATE 8095

enum counter_key {
    COURSE_UDP = 0,
    MOLD_HEARTBEAT,
    AAPL_STOCK,
    NVDA_STOCK,
    OTHER_ITCH,
    SHORT_INPUT,
    POLICY_DROP,
    COUNTER_MAX
};

enum policy_mode {
    POLICY_ALLOW = 0,
    POLICY_BLOCK = 1
};

struct mold_header {
    __u8 session[10];
    __be64 sequence;
    __be16 count;
} __attribute__((packed));

struct policy_config {
    __u32 mode;
    __u32 target_stock_locate;
    __u64 remaining_drops;
    __u64 deadline_ns;
};

struct drop_audit {
    __u64 first_drop_sequence;
    __u32 first_drop_locate;
    __u32 drops;
};

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, COUNTER_MAX);
    __type(key, __u32);
    __type(value, __u64);
} counters SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct policy_config);
} policy SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct drop_audit);
} drop_audit SEC(".maps");

static __always_inline void count(__u32 key)
{
    __u64 *value = bpf_map_lookup_elem(&counters, &key);
    if (value)
        *value += 1;
}

static __always_inline int is_symbol(const __u8 *s, const char *name)
{
    return s[0] == name[0] && s[1] == name[1] &&
           s[2] == name[2] && s[3] == name[3] &&
           s[4] == ' ' && s[5] == ' ' && s[6] == ' ' && s[7] == ' ';
}

SEC("xdp")
int flle_xdp_mold_itch(struct xdp_md *ctx)
{
    void *data = (void *)(long)ctx->data;
    void *end = (void *)(long)ctx->data_end;
    struct ethhdr *eth = data;
    struct iphdr *ip;
    struct udphdr *udp;
    struct mold_header *mold;
    struct policy_config *cfg;
    struct drop_audit *audit;
    __u8 *lengthp, *itch, *stock;
    __u16 message_length, message_count, locate;
    __u32 zero = 0;
    __u64 now_ns, sequence, old_remaining;

    if ((void *)(eth + 1) > end || eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;
    ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > end || ip->version != 4 || ip->ihl != 5)
        return XDP_PASS;
    if (ip->protocol != IPPROTO_UDP ||
        (ip->frag_off & bpf_htons(IPV4_FRAGMENT_MASK)) != 0 ||
        ip->saddr != bpf_htonl(FEED_SOURCE) ||
        ip->daddr != bpf_htonl(FEED_GROUP))
        return XDP_PASS;
    udp = (void *)(ip + 1);
    if ((void *)(udp + 1) > end || udp->dest != bpf_htons(FEED_PORT))
        return XDP_PASS;

    count(COURSE_UDP);
    mold = (void *)(udp + 1);
    if ((void *)(mold + 1) > end) {
        count(SHORT_INPUT);
        return XDP_PASS;
    }
    message_count = bpf_ntohs(mold->count);
    if (message_count == 0) {
        count(MOLD_HEARTBEAT);
        return XDP_PASS;
    }
    if (message_count != 1) {
        count(OTHER_ITCH);
        return XDP_PASS;
    }

    lengthp = (void *)(mold + 1);
    if ((void *)(lengthp + 2) > end) {
        count(SHORT_INPUT);
        return XDP_PASS;
    }
    message_length = ((__u16)lengthp[0] << 8) | lengthp[1];
    itch = lengthp + 2;
    if (message_length != ITCH_ADD_LEN) {
        count(OTHER_ITCH);
        return XDP_PASS;
    }
    if ((void *)(itch + ITCH_ADD_LEN) > end) {
        count(SHORT_INPUT);
        return XDP_PASS;
    }
    if (itch[0] != 'A') {
        count(OTHER_ITCH);
        return XDP_PASS;
    }
    if ((void *)(itch + 3) > end) {
        count(SHORT_INPUT);
        return XDP_PASS;
    }

    locate = ((__u16)itch[1] << 8) | itch[2];
    stock = itch + 24;
    if ((void *)(stock + 8) > end) {
        count(SHORT_INPUT);
        return XDP_PASS;
    }
    if (is_symbol(stock, "AAPL")) {
        count(AAPL_STOCK);
        return XDP_PASS;
    }
    if (!is_symbol(stock, "NVDA") || locate != NVDA_LOCATE) {
        count(OTHER_ITCH);
        return XDP_PASS;
    }

    count(NVDA_STOCK);
    cfg = bpf_map_lookup_elem(&policy, &zero);
    if (!cfg || cfg->mode != POLICY_BLOCK || cfg->remaining_drops == 0)
        return XDP_PASS;
    now_ns = bpf_ktime_get_ns();
    if (cfg->deadline_ns && now_ns > cfg->deadline_ns)
        return XDP_PASS;

    /* 本课策略只允许 1 -> 0。原子比较交换保证多队列并发时也只丢一次。 */
    old_remaining = __sync_val_compare_and_swap(&cfg->remaining_drops, 1, 0);
    if (old_remaining != 1)
        return XDP_PASS;

    sequence = bpf_be64_to_cpu(mold->sequence);
    audit = bpf_map_lookup_elem(&drop_audit, &zero);
    if (audit) {
        if (!audit->first_drop_sequence)
            audit->first_drop_sequence = sequence;
        audit->first_drop_locate = locate;
        audit->drops += 1;
    }
    count(POLICY_DROP);
    return XDP_DROP;
}

char LICENSE[] SEC("license") = "GPL";
