// One ordinary Socket network receiver; local clients subscribe via AF_UNIX.
#include "common.hpp"
#include "feed_ipc.hpp"
#include "market_config.hpp"
#include <sys/stat.h>
#include <poll.h>
#include <csignal>
#include <array>
#include <deque>
#include <iostream>
#include <vector>

namespace {
volatile std::sig_atomic_t stopped = 0;
void stop(int) { stopped = 1; }
std::string arg(int argc, char **argv, const std::string &key,
                const std::string &fallback) {
  for (int i = 1; i + 1 < argc; ++i) if (argv[i] == key) return argv[i + 1];
  return fallback;
}
int receive_buffer(int fd) {
  int bytes = 0;
  socklen_t size = sizeof(bytes);
  if (::getsockopt(fd, SOL_SOCKET, SO_RCVBUF, &bytes, &size))
    throw std::runtime_error("feed UDP receive buffer query failed");
  return bytes;
}
int udp(const std::string &ip, int port, int buffer_bytes, const std::string &group = {},
        const std::string &source = {}) {
  const int fd = ::socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
  if (fd < 0) throw std::runtime_error("feed UDP socket failed");
  if (::setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &buffer_bytes, sizeof(buffer_bytes)))
    throw std::runtime_error("feed UDP receive buffer setup failed");
  // Linux doubles SO_RCVBUF and otherwise silently caps it at rmem_max.
  if (receive_buffer(fd) < 2 * buffer_bytes &&
      ::setsockopt(fd, SOL_SOCKET, SO_RCVBUFFORCE, &buffer_bytes, sizeof(buffer_bytes)))
    throw std::runtime_error("feed UDP receive buffer capped: CAP_NET_ADMIN or a sufficient net.core.rmem_max is required");
  if (receive_buffer(fd) < 2 * buffer_bytes)
    throw std::runtime_error("feed UDP receive buffer is below the requested size");
  sockaddr_in addr{}; addr.sin_family = AF_INET; addr.sin_port = htons(port);
  if (::inet_pton(AF_INET, group.empty() ? ip.c_str() : group.c_str(), &addr.sin_addr) != 1)
    throw std::runtime_error("invalid feed IP");
  // Deliberately no SO_REUSEPORT: exactly one network owner in this namespace.
  if (::bind(fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) < 0)
    throw std::runtime_error("feed UDP bind failed: " + std::string(std::strerror(errno)));
  if (!group.empty()) {
    ip_mreq_source membership{};
    ::inet_pton(AF_INET, group.c_str(), &membership.imr_multiaddr);
    ::inet_pton(AF_INET, ip.c_str(), &membership.imr_interface);
    if (::inet_pton(AF_INET, source.c_str(), &membership.imr_sourceaddr) != 1 ||
        membership.imr_sourceaddr.s_addr == INADDR_ANY ||
        membership.imr_sourceaddr.s_addr == INADDR_BROADCAST ||
        IN_MULTICAST(ntohl(membership.imr_sourceaddr.s_addr)))
      throw std::runtime_error("invalid multicast source IP");
    if (::setsockopt(fd, IPPROTO_IP, IP_ADD_SOURCE_MEMBERSHIP, &membership, sizeof(membership)))
      throw std::runtime_error("feed source-specific multicast join failed: " + std::string(std::strerror(errno)));
  }
  return fd;
}

struct Client {
  int fd;
  pid_t pid;
  std::deque<std::vector<std::uint8_t>> pending;
  std::size_t bytes{};
};
}

int main(int argc, char **argv) {
  const auto path = arg(argc, argv, "--socket", "feed.sock");
  bool owns_path = false;
  std::uint64_t received = 0, delivered = 0, backpressure = 0, overflows = 0;
  std::uint64_t discarded = 0;
  std::array<std::uint64_t, 3> path_received{};
  try {
    ::signal(SIGINT, stop); ::signal(SIGTERM, stop); ::signal(SIGPIPE, SIG_IGN);
    const auto ip = arg(argc, argv, "--data-ip", "20.1.1.2");
    const auto group = arg(argc, argv, "--multicast-group", flle::market_group_a);
    const auto group_b = arg(argc, argv, "--multicast-group-b", flle::market_group_b);
    const auto source = arg(argc, argv, "--multicast-source", flle::market_source);
    const int unicast_port = std::stoi(arg(argc, argv, "--unicast-port", "42121"));
    const int multicast_port = std::stoi(arg(argc, argv, "--multicast-port", std::to_string(flle::market_port_a)));
    const int multicast_port_b = std::stoi(arg(argc, argv, "--multicast-port-b", std::to_string(flle::market_port_b)));
    const bool multicast = arg(argc, argv, "--multicast-receiver", "1") == "1";
    const int buffer_bytes = std::stoi(arg(argc, argv, "--receive-buffer-bytes", "4194304"));
    const int queue_bytes = std::stoi(arg(argc, argv, "--client-queue-bytes", "8388608"));
    const int queue_packets = std::stoi(arg(argc, argv, "--client-queue-packets", "32768"));
    if (queue_bytes < 65536 || queue_bytes > 64 * 1024 * 1024 ||
        queue_packets < 1 || queue_packets > 262144)
      throw std::runtime_error("invalid feed client queue limit");
    if (buffer_bytes < 65536 || buffer_bytes > 64 * 1024 * 1024)
      throw std::runtime_error("invalid feed receive buffer size");
    if (unicast_port < 1 || unicast_port > 65535 || multicast_port < 1 || multicast_port > 65535 ||
        multicast_port_b < 1 || multicast_port_b > 65535)
      throw std::runtime_error("invalid feed port");
    flle::validate_market_groups(group, group_b);
    const int unicast = udp(ip, unicast_port, buffer_bytes);
    const int multi = multicast ? udp(ip, multicast_port, buffer_bytes, group, source) : -1;
    const int multi_b = multicast ? udp(ip, multicast_port_b, buffer_bytes, group_b, source) : -1;
    flle::EventEmitter events("feed_receiver", arg(argc, argv, "--telemetry-host", "off"),
                             46120);
    const int server = ::socket(AF_UNIX, SOCK_SEQPACKET | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    const auto address = flle::feed_address(path);
    if (server < 0 || ::bind(server, reinterpret_cast<const sockaddr *>(&address), sizeof(address)))
      throw std::runtime_error("local feed socket already exists or cannot bind");
    owns_path = true;
    if (::chmod(path.c_str(), 0600) || ::listen(server, 16))
      throw std::runtime_error("local feed listen failed");
    std::cout << "feed_receiver=READY unicast=" << ip << ':' << unicast_port
              << " multicast=" << (multicast ? group : "DISABLED") << ':' << multicast_port
              << " multicast_b=" << (multicast ? group_b : "DISABLED") << ':' << multicast_port_b
              << " market_schema=" << flle::market_schema
              << " multicast_source=" << source << " pid=" << ::getpid()
              << " ipc=" << path << " unicast_rcvbuf=" << receive_buffer(unicast)
              << " multicast_rcvbuf=" << (multicast ? receive_buffer(multi) : 0)
              << " client_queue_bytes=" << queue_bytes
              << " client_queue_packets=" << queue_packets << std::endl;
    std::vector<Client> clients;
    std::vector<pollfd> fds;
    std::array<std::uint8_t, 65536 + flle::feed_header_size> packet{};
    std::size_t peak_bytes = 0, peak_packets = 0;
    auto heartbeat = std::chrono::steady_clock::now();
    const auto close_client = [&](Client &client, const char *reason) {
      discarded += client.pending.size();
      std::cerr << "feed_client=CLOSED pid=" << client.pid << " reason=" << reason
                << " pending_packets=" << client.pending.size() << std::endl;
      ::close(client.fd); client.fd = -1;
      client.pending.clear(); client.bytes = 0;
    };
    const auto report = [&] {
      std::size_t bytes = 0, packets = 0;
      for (const auto &client : clients) {
        bytes += client.bytes; packets += client.pending.size();
      }
      std::ostringstream fields;
      fields << "{\"status\":\"ONLINE\",\"pid\":" << ::getpid()
             << ",\"received\":" << received << ",\"delivered\":" << delivered
             << ",\"unicast_received\":" << path_received[0]
             << ",\"multicast_a_received\":" << path_received[1]
             << ",\"multicast_b_received\":" << path_received[2]
             << ",\"backpressure_events\":" << backpressure
             << ",\"overflow_disconnects\":" << overflows
             << ",\"discarded_queue_packets\":" << discarded
             << ",\"clients\":" << clients.size()
             << ",\"queued_packets\":" << packets << ",\"queued_bytes\":" << bytes
             << ",\"peak_client_packets\":" << peak_packets
             << ",\"peak_client_bytes\":" << peak_bytes
             << ",\"client_queue_packets_limit\":" << queue_packets
             << ",\"client_queue_bytes_limit\":" << queue_bytes << '}';
      events.emit("feed_receiver_status", fields.str());
      std::cout << "feed_receiver=STATUS " << fields.str() << std::endl;
    };
    while (!stopped) {
      fds = {{server, POLLIN, 0}, {unicast, POLLIN, 0}, {multi, POLLIN, 0}, {multi_b, POLLIN, 0}};
      for (const auto &client : clients)
        fds.push_back({client.fd, static_cast<short>(client.pending.empty() ? 0 : POLLOUT), 0});
      if (::poll(fds.data(), fds.size(), 200) < 0) {
        if (errno == EINTR) continue;
        throw std::runtime_error("feed poll failed");
      }
      // Retry each subscriber independently. Bound one flush so a recovering
      // subscriber cannot starve network reception or other subscribers.
      for (std::size_t index = 0; index < clients.size(); ++index) {
        auto &client = clients[index];
        const auto revents = fds[index + 4].revents;
        if (revents & (POLLERR | POLLHUP | POLLNVAL)) {
          close_client(client, "PEER_DISCONNECTED"); continue;
        }
        if (!(revents & POLLOUT)) continue;
        for (unsigned budget = 0; budget < 128 && !client.pending.empty(); ++budget) {
          const auto &front = client.pending.front();
          const auto sent = ::send(client.fd, front.data(), front.size(), MSG_DONTWAIT | MSG_NOSIGNAL);
          if (sent == static_cast<ssize_t>(front.size())) {
            ++delivered; client.bytes -= front.size(); client.pending.pop_front();
          } else if (sent < 0 && errno == EINTR) { continue; }
          else if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            ++backpressure; break;
          } else { close_client(client, "SEND_FAILED"); break; }
        }
      }
      clients.erase(std::remove_if(clients.begin(), clients.end(),
                                   [](const Client &client) { return client.fd < 0; }), clients.end());
      if (fds[0].revents & POLLIN) {
        for (;;) {
          const int client = ::accept4(server, nullptr, nullptr, SOCK_NONBLOCK | SOCK_CLOEXEC);
          if (client < 0) break;
          if (clients.size() >= 32) { ::close(client); continue; }
          ucred peer{}; socklen_t length = sizeof(peer);
          if (::getsockopt(client, SOL_SOCKET, SO_PEERCRED, &peer, &length)) {
            ::close(client); continue;
          }
          clients.push_back(Client{client, peer.pid, {}, 0});
        }
      }
      for (unsigned i = 1; i <= 3; ++i) {
        if (!(fds[i].revents & POLLIN)) continue;
        const auto size = ::recv(fds[i].fd, packet.data() + flle::feed_header_size,
                                 packet.size() - flle::feed_header_size, MSG_TRUNC);
        if (size < 0 || static_cast<std::size_t>(size) > packet.size() - flle::feed_header_size) continue;
        ++received;
        ++path_received[i - 1];
        // Preserve FLF1 compatibility: both A/B packets are multicast (1).
        // Deduplication uses the unchanged Mold session and sequence number.
        flle::feed_header(packet.data(), i == 1 ? 0 : 1, flle::monotonic_ns());
        const auto total = static_cast<std::size_t>(size) + flle::feed_header_size;
        for (auto &client : clients) {
          if (client.fd < 0) continue;
          if (client.pending.empty()) {
            ssize_t sent;
            do { sent = ::send(client.fd, packet.data(), total, MSG_DONTWAIT | MSG_NOSIGNAL); }
            while (sent < 0 && errno == EINTR);
            if (sent == static_cast<ssize_t>(total)) { ++delivered; continue; }
            if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) ++backpressure;
            else { close_client(client, "SEND_FAILED"); continue; }
          }
          if (client.pending.size() >= static_cast<std::size_t>(queue_packets) ||
              client.bytes + total > static_cast<std::size_t>(queue_bytes)) {
            ++overflows; ++discarded;
            close_client(client, "QUEUE_LIMIT_RESYNC_REQUIRED"); continue;
          }
          client.pending.emplace_back(packet.begin(), packet.begin() + total);
          client.bytes += total;
          peak_bytes = std::max(peak_bytes, client.bytes);
          peak_packets = std::max(peak_packets, client.pending.size());
        }
      }
      clients.erase(std::remove_if(clients.begin(), clients.end(),
                                   [](const Client &client) { return client.fd < 0; }), clients.end());
      if (std::chrono::steady_clock::now() >= heartbeat) {
        report(); heartbeat = std::chrono::steady_clock::now() + std::chrono::seconds(1);
      }
    }
    report();
    for (const auto &client : clients) ::close(client.fd);
    ::close(server); ::close(unicast); if (multi >= 0) ::close(multi);
    if (multi_b >= 0) ::close(multi_b);
    ::unlink(path.c_str()); owns_path = false;
    std::cout << "feed_receiver=STOPPED received=" << received << " delivered=" << delivered
              << " backpressure_events=" << backpressure
              << " overflow_disconnects=" << overflows
              << " discarded_queue_packets=" << discarded << std::endl;
    return 0;
  } catch (const std::exception &e) {
    if (owns_path) ::unlink(path.c_str());
    std::cerr << "feed_receiver: " << e.what() << '\n';
    return 1;
  }
}
