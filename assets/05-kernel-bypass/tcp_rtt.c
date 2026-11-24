#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* 52 字节教学消息的往返尺子：同一份程序，普通启动或 onload 启动。 */
#define PAYLOAD 52
#define WARMUP 1000
#define MEASURED 10000

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

static void die(const char *msg)
{
    perror(msg);
    exit(1);
}

static void send_all(int fd, const void *buf, size_t len)
{
    const char *p = (const char *)buf;
    while (len > 0) {
        ssize_t n = send(fd, p, len, 0);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
            die("send");
        p += n;
        len -= (size_t)n;
    }
}

static void recv_all(int fd, void *buf, size_t len)
{
    char *p = (char *)buf;
    while (len > 0) {
        ssize_t n = recv(fd, p, len, 0);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
            die("recv");
        p += n;
        len -= (size_t)n;
    }
}

/* nearest-rank percentile: rank=ceil(p*n/100), then convert to zero-based index. */
static size_t percentile_index(size_t n, unsigned p)
{
    return (p * n + 99U) / 100U - 1U;
}

static void run_server(uint16_t port)
{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0)
        die("socket");
    int yes = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(port);
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0)
        die("bind");
    if (listen(fd, 1) != 0)
        die("listen");
    printf("server_listen=%u\n", port);
    fflush(stdout);
    int conn = accept(fd, NULL, NULL);
    if (conn < 0)
        die("accept");
    setsockopt(conn, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
    char buf[PAYLOAD];
    int left = WARMUP + MEASURED;
    while (left-- > 0) {
        recv_all(conn, buf, PAYLOAD);
        send_all(conn, buf, PAYLOAD);
    }
    close(conn);
    close(fd);
}

static void run_client(const char *ip, uint16_t port, const char *raw_path)
{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0)
        die("socket");
    int yes = 1;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    if (inet_pton(AF_INET, ip, &addr.sin_addr) != 1)
        die("inet_pton");
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0)
        die("connect");
    char buf[PAYLOAD];
    memset(buf, 'A', PAYLOAD);
    int64_t *samples = calloc(MEASURED, sizeof(int64_t));
    if (!samples)
        die("calloc");
    int i;
    for (i = 0; i < WARMUP + MEASURED; i++) {
        int64_t t0 = now_ns();
        send_all(fd, buf, PAYLOAD);
        recv_all(fd, buf, PAYLOAD);
        int64_t dt = now_ns() - t0;
        if (i >= WARMUP)
            samples[i - WARMUP] = dt;
    }
    if (raw_path != NULL) {
        FILE *raw = fopen(raw_path, "w");
        if (raw == NULL)
            die("fopen raw samples");
        fputs("sample_index,rtt_ns\n", raw);
        for (i = 0; i < MEASURED; i++)
            fprintf(raw, "%d,%lld\n", i, (long long)samples[i]);
        if (fclose(raw) != 0)
            die("fclose raw samples");
    }
    int64_t sum = 0;
    for (i = 0; i < MEASURED; i++)
        sum += samples[i];
    qsort(samples, MEASURED, sizeof(int64_t), cmp_i64);
    printf("payload=%d warmup=%d measured=%d\n", PAYLOAD, WARMUP, MEASURED);
    printf("percentile_method=nearest_rank\n");
    printf("completed=%d lost=0\n", MEASURED);
    printf("rtt_p50_ns=%lld\n", (long long)samples[percentile_index(MEASURED, 50)]);
    printf("rtt_p99_ns=%lld\n", (long long)samples[percentile_index(MEASURED, 99)]);
    printf("rtt_max_ns=%lld\n", (long long)samples[MEASURED - 1]);
    printf("rtt_avg_ns=%lld\n", (long long)(sum / MEASURED));
    close(fd);
    free(samples);
}

int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "server") == 0) {
        run_server((uint16_t)atoi(argv[2]));
        return 0;
    }
    if ((argc == 4 || argc == 5) && strcmp(argv[1], "client") == 0) {
        run_client(argv[2], (uint16_t)atoi(argv[3]), argc == 5 ? argv[4] : NULL);
        return 0;
    }
    fprintf(stderr, "usage: %s server <port> | %s client <ip> <port> [raw.csv]\n", argv[0], argv[0]);
    return 2;
}
