#define _GNU_SOURCE
#include <arpa/inet.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

/* 收到 EtherType 0x88B5 的帧后对调 MAC 原样回弹，给对端量往返。 */
#define ETH_HDR 14
#define ETHERTYPE_HI 0x88
#define ETHERTYPE_LO 0xB5

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <iface>\n", argv[0]);
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
    uint8_t rx[2048];
    for (;;) {
        ssize_t n = recv(fd, rx, sizeof(rx), 0);
        if (n < ETH_HDR + 4)
            continue;
        if (rx[12] != ETHERTYPE_HI || rx[13] != ETHERTYPE_LO)
            continue;
        uint8_t tmp[6];
        memcpy(tmp, rx, 6);
        memcpy(rx, rx + 6, 6);
        memcpy(rx + 6, tmp, 6);
        if (sendto(fd, rx, (size_t)n, 0, (struct sockaddr *)&sa, sizeof(sa)) != n) {
            perror("sendto");
            return 1;
        }
    }
}
