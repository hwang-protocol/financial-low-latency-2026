#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

/* 52 字节 payload + 14 字节以太网头。对端若做 macswap 转发，源目的 MAC 对调后原样回来。 */
#define PAYLOAD 52
#define WARMUP 1000
#define MEASURED 10000
#define ETH_HDR 14
#define FRAME (ETH_HDR + PAYLOAD)

static int64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static int cmp_i64(const void *a, const void *b)
{
    int64_t da = *(const int64_t *)a;
    int64_t db = *(const int64_t *)b;
    return (da > db) - (da < db);
}

/* nearest-rank percentile: rank=ceil(p*n/100), then convert to zero-based index. */
static size_t percentile_index(size_t n, unsigned p)
{
    return (p * n + 99U) / 100U - 1U;
}

static int parse_mac(const char *s, uint8_t mac[6])
{
    unsigned a, b, c, d, e, f;
    if (sscanf(s, "%02x:%02x:%02x:%02x:%02x:%02x", &a, &b, &c, &d, &e, &f) != 6)
        return -1;
    mac[0] = (uint8_t)a; mac[1] = (uint8_t)b; mac[2] = (uint8_t)c;
    mac[3] = (uint8_t)d; mac[4] = (uint8_t)e; mac[5] = (uint8_t)f;
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 4 && argc != 5) {
        fprintf(stderr, "usage: %s <iface> <src-mac> <dst-mac> [raw.csv]\n", argv[0]);
        return 2;
    }
    uint8_t src[6], dst[6];
    if (parse_mac(argv[2], src) != 0 || parse_mac(argv[3], dst) != 0) {
        fprintf(stderr, "bad mac\n");
        return 2;
    }
    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (fd < 0) {
        perror("socket");
        return 1;
    }
    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    snprintf(ifr.ifr_name, IFNAMSIZ, "%s", argv[1]);
    if (ioctl(fd, SIOCGIFINDEX, &ifr) != 0) {
        perror("SIOCGIFINDEX");
        return 1;
    }
    struct sockaddr_ll sa;
    memset(&sa, 0, sizeof(sa));
    sa.sll_family = AF_PACKET;
    sa.sll_protocol = htons(ETH_P_ALL);
    sa.sll_ifindex = ifr.ifr_ifindex;
    if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
        perror("bind");
        return 1;
    }
    uint8_t frame[FRAME];
    memset(frame, 0, sizeof(frame));
    memcpy(frame, dst, 6);
    memcpy(frame + 6, src, 6);
    frame[12] = 0x88;
    frame[13] = 0xB5; /* 实验用 EtherType，避免和 IPv4 业务混 */
    int64_t *samples = (int64_t *)calloc((size_t)MEASURED, sizeof(int64_t));
    if (!samples)
        return 1;
    struct timeval tv;
    tv.tv_sec = 1;
    tv.tv_usec = 0;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) != 0) {
        perror("setsockopt SO_RCVTIMEO");
        return 1;
    }
    int i;
    uint8_t rx[2048];
    for (i = 0; i < WARMUP + MEASURED; i++) {
        uint32_t seq = (uint32_t)i;
        memcpy(frame + ETH_HDR, &seq, 4);
        int64_t t0 = now_ns();
        memcpy(frame + ETH_HDR + 4, &t0, 8);
        if (sendto(fd, frame, FRAME, 0, (struct sockaddr *)&sa, sizeof(sa)) != FRAME) {
            perror("sendto");
            return 1;
        }
        for (;;) {
            ssize_t n = recv(fd, rx, sizeof(rx), 0);
            if (n < 0) {
                fprintf(stderr, "timeout waiting seq=%u errno=%d\n", seq, errno);
                return 1;
            }
            if (n < FRAME)
                continue;
            if (memcmp(rx, src, 6) != 0)
                continue;
            if (memcmp(rx + 6, dst, 6) != 0)
                continue;
            if (rx[12] != 0x88 || rx[13] != 0xB5)
                continue;
            uint32_t got = 0;
            memcpy(&got, rx + ETH_HDR, 4);
            if (got != seq)
                continue;
            int64_t dt = now_ns() - t0;
            if (i >= WARMUP)
                samples[i - WARMUP] = dt;
            break;
        }
    }
    if (argc == 5) {
        FILE *raw = fopen(argv[4], "w");
        if (raw == NULL) {
            perror("fopen raw samples");
            return 1;
        }
        fputs("sample_index,rtt_ns\n", raw);
        for (i = 0; i < MEASURED; i++)
            fprintf(raw, "%d,%lld\n", i, (long long)samples[i]);
        if (fclose(raw) != 0) {
            perror("fclose raw samples");
            return 1;
        }
    }
    int64_t sum = 0;
    for (i = 0; i < MEASURED; i++)
        sum += samples[i];
    qsort(samples, MEASURED, sizeof(int64_t), cmp_i64);
    printf("payload=%d frame_bytes_no_fcs=%d warmup=%d measured=%d ethertype=0x88b5\n",
           PAYLOAD, FRAME, WARMUP, MEASURED);
    printf("percentile_method=nearest_rank\n");
    printf("completed=%d lost=0\n", MEASURED);
    printf("rtt_p50_ns=%lld\n", (long long)samples[percentile_index(MEASURED, 50)]);
    printf("rtt_p99_ns=%lld\n", (long long)samples[percentile_index(MEASURED, 99)]);
    printf("rtt_max_ns=%lld\n", (long long)samples[MEASURED - 1]);
    printf("rtt_avg_ns=%lld\n", (long long)(sum / MEASURED));
    free(samples);
    close(fd);
    return 0;
}
