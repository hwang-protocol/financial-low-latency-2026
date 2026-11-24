/* Minimal F-Stack TCP smoke used before the DPDK trading client is started. */
#include <arpa/inet.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>

#include "ff_api.h"
#include "ff_event.h"
#include "rte_ethdev.h"

enum smoke_stage { CONNECTING, SENDING, RECEIVING };

static int socket_fd = -1;
static int queue_fd = -1;
static enum smoke_stage stage = CONNECTING;
static size_t sent_bytes;
static size_t received_bytes;
static unsigned char payload[52];
static unsigned char reply[52];

static void fail(const char *message) {
  fprintf(stderr, "FSTACK_TCP_SMOKE_FAIL stage=%d error=%s errno=%d\n",
          stage, message, errno);
  exit(1);
}

static int drive(void *unused) {
  (void)unused;
  static unsigned long iterations;
  static time_t last_report;
  if (++iterations == 1) {
    printf("FSTACK_REACTOR_RUNNING\n");
    fflush(stdout);
  }
  const time_t now = time(NULL);
  if (now != last_report) {
    struct rte_eth_stats stats;
    memset(&stats, 0, sizeof(stats));
    if (rte_eth_stats_get(0, &stats) == 0) {
      printf("FSTACK_PORT_STATS rx=%lu tx=%lu rx_errors=%lu tx_errors=%lu\n",
             stats.ipackets, stats.opackets, stats.ierrors, stats.oerrors);
      fflush(stdout);
    }
    last_report = now;
  }
  struct kevent events[4];
  // ff_run() must keep returning to the DPDK/F-Stack reactor.  A blocking
  // kevent wait here would prevent ARP, TCP retransmission and RX/TX progress.
  const struct timespec no_wait = {0, 0};
  const int count = ff_kevent(queue_fd, NULL, 0, events, 4, &no_wait);
  if (count < 0) fail("ff_kevent");
  for (int index = 0; index < count; ++index) {
    if (events[index].flags & EV_ERROR) fail("event_error");
    if (events[index].filter == EVFILT_WRITE && stage == CONNECTING) {
      int error = 0;
      socklen_t length = sizeof(error);
      if (ff_getsockopt(socket_fd, SOL_SOCKET, SO_ERROR, &error, &length) || error) {
        errno = error;
        fail("connect");
      }
      stage = SENDING;
    }
    if (events[index].filter == EVFILT_WRITE && stage == SENDING) {
      const ssize_t result = ff_send(socket_fd, payload + sent_bytes,
                                     sizeof(payload) - sent_bytes, 0);
      if (result > 0) sent_bytes += (size_t)result;
      else if (result < 0 && errno != EAGAIN) fail("send");
      if (sent_bytes == sizeof(payload)) stage = RECEIVING;
    }
    if (events[index].filter == EVFILT_READ && stage == RECEIVING) {
      const ssize_t result = ff_recv(socket_fd, reply + received_bytes,
                                     sizeof(reply) - received_bytes, 0);
      if (result > 0) received_bytes += (size_t)result;
      else if (result == 0) fail("early_eof");
      else if (errno != EAGAIN) fail("recv");
      if (received_bytes == sizeof(reply)) {
        if (memcmp(payload, reply, sizeof(payload))) fail("payload_mismatch");
        printf("FSTACK_TCP_SMOKE_PASS bytes=52\n");
        fflush(stdout);
        exit(0);
      }
    }
  }
  return 0;
}

int main(int argc, char **argv) {
  const char *host = getenv("FLLE_SMOKE_HOST");
  const char *port_text = getenv("FLLE_SMOKE_PORT");
  if (!host) host = "20.1.1.1";
  if (!port_text) port_text = "43129";
  memset(payload, 0x58, sizeof(payload));

  if (ff_init(argc, argv)) fail("ff_init");
  socket_fd = ff_socket(AF_INET, SOCK_STREAM, 0);
  if (socket_fd < 0) fail("ff_socket");
  int nonblocking = 1;
  if (ff_ioctl(socket_fd, FIONBIO, &nonblocking)) fail("FIONBIO");

  struct sockaddr_in remote;
  memset(&remote, 0, sizeof(remote));
  remote.sin_family = AF_INET;
  remote.sin_port = htons((unsigned short)strtoul(port_text, NULL, 10));
  if (inet_pton(AF_INET, host, &remote.sin_addr) != 1) fail("inet_pton");
  const int connect_result =
      ff_connect(socket_fd, (struct linux_sockaddr *)&remote, sizeof(remote));
  printf("FSTACK_CONNECT_SUBMITTED rc=%d errno=%d\n", connect_result, errno);
  fflush(stdout);
  if (connect_result && errno != EINPROGRESS)
    fail("ff_connect");

  queue_fd = ff_kqueue();
  if (queue_fd < 0) fail("ff_kqueue");
  struct kevent changes[2];
  EV_SET(&changes[0], socket_fd, EVFILT_READ, EV_ADD | EV_ENABLE | EV_CLEAR,
         0, 0, NULL);
  EV_SET(&changes[1], socket_fd, EVFILT_WRITE, EV_ADD | EV_ENABLE | EV_CLEAR,
         0, 0, NULL);
  if (ff_kevent(queue_fd, changes, 2, NULL, 0, NULL)) fail("ff_kevent_add");
  ff_run(drive, NULL);
  return 1;
}
