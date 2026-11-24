#include "itch_book.hpp"
#include "order_transport.hpp"
#include "order_queue.hpp"

#include <poll.h>
#include <pthread.h>
#include <sched.h>
#include <sys/syscall.h>

#include <atomic>
#include <cmath>
#include <condition_variable>
#include <csignal>
#include <deque>
#include <fstream>
#include <map>
#include <mutex>
#include <numeric>
#include <optional>
#include <thread>

namespace {

namespace nasdaq = flle::nasdaq;
std::atomic<bool> g_stop{false};

std::string trader_source(const std::string &role,
                          const std::string &transport) {
  if (role == "AUTO") return "trader_auto";
  if (transport == "OPENONLOAD") return "trader_onload";
  if (transport == "TCPDIRECT_ZF") return "trader_tcpdirect";
  if (transport == "DPDK_FSTACK") return "trader_dpdk";
  return "trader_manual";
}

struct Config {
  std::string role{"AUTO"};
  std::string data_ip{"20.1.1.2"};
  std::string exchange_data_ip{"20.1.1.1"};
  std::string management_ip{"10.1.1.2"};
  std::string telemetry_host{"10.1.1.101"};
  std::string multicast_group{"239.20.1.20"};
  std::string book_checkpoint{"opening-book.checkpoint"};
  std::uint16_t multicast_port{42120};
  std::uint16_t unicast_port{42121};
  std::uint16_t order_port{43120};
  std::uint16_t management_port{48121};
  std::uint16_t telemetry_port{46120};
  std::uint32_t user_ref_base{1};
  std::uint32_t user_ref_span{2000000000U};
  std::string clordid_prefix{"AUTO"};
  std::string order_transport{std::string(flle::order_transport_name())};
  flle::OrderQueueMode order_queue{flle::OrderQueueMode::DequeCv};
  bool lock_order_queue{false};
  bool market_receiver_enabled{true};
  bool multicast_receiver_enabled{true};
  bool strategy_enabled{true};
  int order_cpu{-1};
  int management_cpu{-1};
};

std::string arg_value(int argc, char **argv, const std::string &name,
                      const std::string &fallback) {
  for (int index = 1; index + 1 < argc; ++index)
    if (argv[index] == name) return argv[index + 1];
  return fallback;
}

Config parse_config(int argc, char **argv) {
  Config c;
  c.role = arg_value(argc, argv, "--role", c.role);
  c.data_ip = arg_value(argc, argv, "--data-ip", c.data_ip);
  c.exchange_data_ip = arg_value(argc, argv, "--exchange-data-ip", c.exchange_data_ip);
  c.management_ip = arg_value(argc, argv, "--management-ip", c.management_ip);
  c.telemetry_host = arg_value(argc, argv, "--telemetry-host", c.telemetry_host);
  c.multicast_group = arg_value(argc, argv, "--multicast-group", c.multicast_group);
  c.book_checkpoint = arg_value(argc, argv, "--book-checkpoint", c.book_checkpoint);
  c.multicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--multicast-port", std::to_string(c.multicast_port))));
  c.unicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--unicast-port", std::to_string(c.unicast_port))));
  c.order_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--order-port", std::to_string(c.order_port))));
  c.management_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--management-port", std::to_string(c.management_port))));
  c.telemetry_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--telemetry-port", std::to_string(c.telemetry_port))));
  const auto user_ref_base = std::stoull(
      arg_value(argc, argv, "--user-ref-base", std::to_string(c.user_ref_base)));
  const auto user_ref_span = std::stoull(
      arg_value(argc, argv, "--user-ref-span", std::to_string(c.user_ref_span)));
  if (!user_ref_base || user_ref_base > 4294967295ULL ||
      !user_ref_span || user_ref_span > 4294967295ULL)
    throw std::runtime_error("invalid user-ref namespace");
  c.user_ref_base = static_cast<std::uint32_t>(user_ref_base);
  c.user_ref_span = static_cast<std::uint32_t>(user_ref_span);
  c.clordid_prefix = arg_value(argc, argv, "--clordid-prefix", c.clordid_prefix);
  c.order_transport = arg_value(argc, argv, "--order-transport-label",
                                c.order_transport);
  c.order_queue = flle::parse_order_queue_mode(
      arg_value(argc, argv, "--order-queue", flle::order_queue_mode_name(c.order_queue)));
  c.lock_order_queue =
      arg_value(argc, argv, "--lock-order-queue", "0") == "1";
  c.market_receiver_enabled =
      arg_value(argc, argv, "--market-receiver", "1") == "1";
  c.multicast_receiver_enabled =
      arg_value(argc, argv, "--multicast-receiver", "1") == "1";
  c.strategy_enabled =
      arg_value(argc, argv, "--strategy-enabled", "1") == "1";
  c.order_cpu = std::stoi(arg_value(argc, argv, "--order-cpu", "-1"));
  c.management_cpu =
      std::stoi(arg_value(argc, argv, "--management-cpu", "-1"));
  if (c.role != "AUTO" && c.role != "MANUAL")
    throw std::runtime_error("role must be AUTO or MANUAL");
  if (static_cast<std::uint64_t>(c.user_ref_base) + c.user_ref_span >
      4294967296ULL)
    throw std::runtime_error("invalid user-ref namespace");
  if (c.clordid_prefix.size() != 4)
    throw std::runtime_error("clordid prefix must be four bytes");
  const auto compiled_transport = flle::order_transport_name();
  if ((compiled_transport == "TCPDIRECT_ZF" &&
       c.order_transport != "TCPDIRECT_ZF") ||
      (compiled_transport == "POSIX_SOCKET" &&
       c.order_transport != "POSIX_SOCKET" &&
       c.order_transport != "OPENONLOAD"))
    throw std::runtime_error("order transport label does not match this binary");
  return c;
}

struct Delivery {
  std::vector<std::uint8_t> message;
  std::string path;
  std::uint64_t receive_ns{};
  std::uint64_t sequence{};
};

class FeedHandler {
 public:
  std::vector<Delivery> accept(const std::string &session, std::uint64_t sequence,
                               std::vector<std::uint8_t> message, std::string path,
                               std::uint64_t receive_ns, std::string &classification) {
    if (session_ != session) {
      session_ = session;
      next_expected_ = sequence;
      pending_.clear();
      last_delivered_ = 0;
      first_pending_ = 0;
      highest_received_ = 0;
      gap_started_ns_ = 0;
      delivered_in_session_ = false;
      classification = "NEW_SESSION";
    }
    highest_received_ = std::max(highest_received_, sequence);
    if (sequence < next_expected_ || pending_.count(sequence)) {
      classification = "DUPLICATE";
      return {};
    }
    if (sequence > next_expected_) {
      pending_.emplace(sequence, Delivery{std::move(message), std::move(path), receive_ns, sequence});
      first_pending_ = pending_.begin()->first;
      if (!gap_started_ns_) gap_started_ns_ = receive_ns;
      classification = "GAP";
      return {};
    }
    std::vector<Delivery> delivered;
    Delivery current{std::move(message), std::move(path), receive_ns, sequence};
    while (true) {
      last_delivered_ = current.sequence;
      ++next_expected_;
      delivered.push_back(std::move(current));
      const auto found = pending_.find(next_expected_);
      if (found == pending_.end()) break;
      current = std::move(found->second);
      pending_.erase(found);
    }
    first_pending_ = pending_.empty() ? 0 : pending_.begin()->first;
    if (pending_.empty()) gap_started_ns_ = 0;
    delivered_in_session_ = true;
    if (classification != "NEW_SESSION") classification = "DELIVER";
    return delivered;
  }

  std::string session() const { return session_; }
  std::uint64_t next_expected() const { return next_expected_; }
  std::uint64_t last_delivered() const { return last_delivered_; }
  std::uint64_t first_pending() const { return first_pending_; }
  std::uint64_t highest_received() const { return highest_received_; }
  std::uint64_t gap_started_ns() const { return gap_started_ns_; }
  std::uint64_t gap_age_ms(std::uint64_t now_ns) const {
    return gap_started_ns_ && now_ns > gap_started_ns_
               ? (now_ns - gap_started_ns_) / 1000000ULL
               : 0;
  }
  std::uint64_t gap_size() const {
    return pending_.empty() ? 0 : pending_.begin()->first - next_expected_;
  }
  std::size_t pending() const { return pending_.size(); }
  bool delivered_in_session() const { return delivered_in_session_; }
  std::string integrity() const {
    if (pending() || gap_size()) return "GAP";
    if (!session_.empty() && !delivered_in_session_) return "RECOVERING";
    return "HEALTHY";
  }
  std::string trading_gate() const {
    if (integrity() == "GAP") return "INHIBITED_FEED_GAP";
    if (integrity() == "RECOVERING") return "INHIBITED_FEED_RECOVERING";
    return "OPEN";
  }

 private:
  std::string session_;
  std::uint64_t next_expected_{};
  std::uint64_t last_delivered_{};
  std::uint64_t first_pending_{};
  std::uint64_t highest_received_{};
  std::uint64_t gap_started_ns_{};
  bool delivered_in_session_{};
  std::map<std::uint64_t, Delivery> pending_;
};

struct WorkOrder {
  nasdaq::EnterOrder order;
  std::uint64_t signal_receive_ns{};
  std::uint64_t queued_ns{};
  double imbalance{};
  std::string origin;
  std::uint64_t paper_epoch{};
  bool measurement_sample{};
  std::uint64_t measurement_generation{};
};

class Trader {
 public:
  explicit Trader(Config config)
      : config_(std::move(config)),
        events_(trader_source(config_.role, config_.order_transport),
                config_.telemetry_host, config_.telemetry_port),
        order_queue_(config_.order_queue) {
    std::ifstream checkpoint(config_.book_checkpoint, std::ios::binary);
    if (!checkpoint) throw std::runtime_error("cannot open book checkpoint " + config_.book_checkpoint);
    book_.load_checkpoint(checkpoint);
    paper_epoch_.store(1);
    positions_["AAPL"] = 0;
    positions_["NVDA"] = 0;
    pending_delta_["AAPL"] = 0;
    pending_delta_["NVDA"] = 0;
    strategy_enabled_ = config_.role == "AUTO" && config_.strategy_enabled;
    next_user_ref_.store(config_.user_ref_base);
  }

  void run() {
    std::optional<std::thread> market;
    if (config_.market_receiver_enabled) {
      market.emplace([this] {
        pthread_setname_np(pthread_self(), "flle-market");
        run_guarded(&Trader::market_loop);
      });
    }
    std::thread orders([this] {
      pthread_setname_np(pthread_self(), "flle-order");
      flle::pin_current_thread(config_.order_cpu);
      run_guarded(&Trader::order_loop);
    });
    std::thread management([this] {
      pthread_setname_np(pthread_self(), "flle-mgmt");
      flle::pin_current_thread(config_.management_cpu);
      run_guarded(&Trader::management_server);
    });
    events_.emit("component_start",
                 "{\"status\":\"ONLINE\",\"market_protocol\":\"" +
                     std::string(config_.market_receiver_enabled
                                     ? "ITCH_5.0_OVER_MOLDUDP64"
                                     : "COMMON_GATEWAY_BOOK") +
                     "\","
                 "\"order_protocol\":\"OUCH_5.0_OVER_SOUPBINTCP\",\"role\":\"" +
                     config_.role + "\",\"order_transport\":\"" +
                     config_.order_transport +
                     "\",\"order_queue\":\"" +
                     order_queue_.mode_name() + "\"}");
    if (market) market->join();
    order_queue_.wake();
    orders.join();
    management.join();
    if (failure_) std::rethrow_exception(failure_);
  }

 private:
  Config config_;
  flle::EventEmitter events_;
  nasdaq::ItchBook book_;
  FeedHandler feed_;
  std::mutex mutex_;
  std::mutex feed_mutex_;
  flle::OrderQueue<WorkOrder, 1024> order_queue_;
  std::map<std::string, std::int64_t> positions_;
  std::map<std::string, std::int64_t> pending_delta_;
  std::map<std::string, std::uint64_t> last_action_ns_;
  std::map<std::string, std::chrono::steady_clock::time_point> last_quote_event_;
  std::int64_t cash_x10000_{};
  bool strategy_enabled_{true};
  double imbalance_threshold_{0.35};
  std::uint32_t strategy_quantity_{25};
  std::int64_t max_position_{200};
  std::uint64_t cooldown_ms_{5000};
  std::atomic<std::uint64_t> next_user_ref_{1};
  std::atomic<std::uint64_t> received_{0};
  std::atomic<std::uint64_t> delivered_{0};
  std::atomic<std::uint64_t> duplicates_{0};
  std::atomic<std::uint64_t> gaps_{0};
  std::atomic<std::uint64_t> bad_packets_{0};
  std::atomic<std::uint64_t> orders_{0};
  std::atomic<std::uint64_t> fills_{0};
  std::atomic<std::uint64_t> rejects_{0};
  std::atomic<std::uint64_t> transport_retries_{0};
  std::atomic<std::uint64_t> paper_epoch_{0};
  std::atomic<bool> market_receiver_ready_{false};
  std::deque<std::uint64_t> latency_samples_;
  std::deque<std::uint32_t> latency_order_refs_;
  std::deque<char> latency_results_;
  std::deque<std::uint64_t> measurement_samples_;
  std::deque<std::uint64_t> measurement_queue_samples_;
  std::deque<std::uint64_t> measurement_total_samples_;
  std::deque<std::uint32_t> measurement_order_refs_;
  std::deque<char> measurement_results_;
  std::atomic<std::uint64_t> measurement_generation_{0};
  std::atomic<std::uint64_t> measurement_ready_samples_{0};
  std::deque<std::uint64_t> reaction_samples_;
  std::atomic<std::uint64_t> queue_full_drops_{0};
  std::atomic<int> order_thread_tid_{-1};
  std::atomic<int> order_thread_cpu_{-1};
  std::atomic<int> order_rx_cpu_{-1};
  std::atomic<int> management_thread_tid_{-1};
  std::atomic<int> management_thread_cpu_{-1};
  std::mutex failure_mutex_;
  std::exception_ptr failure_;

  void run_guarded(void (Trader::*function)()) {
    try { (this->*function)(); }
    catch (...) {
      {
        std::lock_guard<std::mutex> lock(failure_mutex_);
        if (!failure_) failure_ = std::current_exception();
      }
      g_stop.store(true);
      order_queue_.wake();
    }
  }

  void reset_paper_state_locked() {
    ++paper_epoch_;
    book_.clear();
    std::ifstream checkpoint(config_.book_checkpoint, std::ios::binary);
    if (!checkpoint) throw std::runtime_error("cannot reopen book checkpoint");
    book_.load_checkpoint(checkpoint);
    positions_["AAPL"] = 0;
    positions_["NVDA"] = 0;
    pending_delta_["AAPL"] = 0;
    pending_delta_["NVDA"] = 0;
    cash_x10000_ = 0;
    last_action_ns_.clear();
    latency_samples_.clear();
    latency_order_refs_.clear();
    latency_results_.clear();
    measurement_samples_.clear();
    measurement_queue_samples_.clear();
    measurement_total_samples_.clear();
    measurement_order_refs_.clear();
    measurement_results_.clear();
    measurement_ready_samples_ = 0;
    ++measurement_generation_;
    reaction_samples_.clear();
    orders_ = 0;
    fills_ = 0;
    rejects_ = 0;
    transport_retries_ = 0;
    received_ = 0;
    delivered_ = 0;
    duplicates_ = 0;
    gaps_ = 0;
    bad_packets_ = 0;
    queue_full_drops_ = 0;
    order_queue_.wake();
  }

  int multicast_socket() {
    const int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    int one = 1;
    ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(config_.multicast_port);
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    if (::bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0)
      throw std::runtime_error("multicast bind failed: " + std::string(std::strerror(errno)));
    ip_mreq membership{};
    ::inet_pton(AF_INET, config_.multicast_group.c_str(), &membership.imr_multiaddr);
    ::inet_pton(AF_INET, config_.data_ip.c_str(), &membership.imr_interface);
    if (::setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &membership, sizeof(membership)) < 0)
      throw std::runtime_error("multicast join failed: " + std::string(std::strerror(errno)));
    return fd;
  }

  int unicast_socket() {
    const int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    int one = 1;
    ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(config_.unicast_port);
    ::inet_pton(AF_INET, config_.data_ip.c_str(), &address.sin_addr);
    if (::bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0)
      throw std::runtime_error("unicast bind failed: " + std::string(std::strerror(errno)));
    return fd;
  }

  void market_loop() {
    const int unicast = unicast_socket();
    const int multicast = config_.multicast_receiver_enabled ? multicast_socket() : -1;
    market_receiver_ready_ = true;
    std::array<pollfd, 2> descriptors{{{unicast, POLLIN, 0}, {multicast, POLLIN, 0}}};
    const nfds_t descriptor_count = multicast >= 0 ? 2 : 1;
    std::array<std::uint8_t, 65536> buffer{};
    auto heartbeat = std::chrono::steady_clock::now();
    while (!g_stop.load()) {
      const int ready = ::poll(descriptors.data(), descriptor_count, 200);
      if (ready > 0) {
        for (std::size_t path_index = 0; path_index < descriptor_count; ++path_index) {
          if (!(descriptors[path_index].revents & POLLIN)) continue;
          const auto length = ::recv(descriptors[path_index].fd, buffer.data(), buffer.size(), 0);
          const auto receive_ns = flle::monotonic_ns();
          nasdaq::MoldPacket packet;
          std::string error;
          if (length < 0 || !nasdaq::decode_mold(
                  buffer.data(), static_cast<std::size_t>(std::max<ssize_t>(0, length)),
                  packet, error)) {
            ++bad_packets_;
            continue;
          }
          const char *path = path_index == 0 ? "UNICAST" : "MULTICAST";
          for (std::size_t index = 0; index < packet.messages.size(); ++index) {
            std::string classification;
            std::vector<Delivery> deliveries;
            {
              std::lock_guard<std::mutex> feed_lock(feed_mutex_);
              deliveries = feed_.accept(packet.session, packet.first_sequence + index,
                  std::move(packet.messages[index]), path, receive_ns,
                  classification);
            }
            if (classification == "DUPLICATE") ++duplicates_;
            if (classification == "GAP") {
              ++gaps_;
              emit_feed_gap(packet.session, packet.first_sequence + index);
            }
            if (classification == "NEW_SESSION") {
              {
                std::lock_guard<std::mutex> lock(mutex_);
                reset_paper_state_locked();
              }
              events_.emit("paper_reset", "{\"reason\":\"NEW_REPLAY_SESSION\",\"session\":\"" +
                               packet.session + "\",\"paper_epoch\":" +
                               std::to_string(paper_epoch_.load()) + "}");
            }
            for (const auto &delivery : deliveries) apply_market(delivery);
          }
          received_ += packet.messages.size();
        }
      }
      if (std::chrono::steady_clock::now() >= heartbeat) {
        emit_heartbeat();
        heartbeat = std::chrono::steady_clock::now() + std::chrono::seconds(1);
      }
    }
    market_receiver_ready_ = false;
    if (multicast >= 0) ::close(multicast);
    ::close(unicast);
  }

  void emit_feed_gap(const std::string &session, std::uint64_t observed) {
    std::uint64_t next_expected{};
    std::uint64_t last_delivered{};
    std::uint64_t first_pending{};
    std::uint64_t highest_received{};
    std::uint64_t gap_size{};
    std::size_t pending{};
    std::string integrity;
    std::string trading_gate;
    std::uint64_t gap_age_ms{};
    {
      std::lock_guard<std::mutex> feed_lock(feed_mutex_);
      next_expected = feed_.next_expected();
      last_delivered = feed_.last_delivered();
      first_pending = feed_.first_pending();
      highest_received = feed_.highest_received();
      gap_size = feed_.gap_size();
      pending = feed_.pending();
      integrity = feed_.integrity();
      trading_gate = feed_.trading_gate();
      gap_age_ms = feed_.gap_age_ms(flle::monotonic_ns());
    }
    std::ostringstream fields;
    fields << "{\"session\":\"" << session << "\",\"observed\":" << observed
           << ",\"next_expected\":" << next_expected
           << ",\"last_delivered\":" << last_delivered
           << ",\"first_pending\":" << first_pending
           << ",\"highest_received\":" << highest_received
           << ",\"gap_size\":" << gap_size << ",\"pending\":" << pending
           << ",\"gap_age_ms\":" << gap_age_ms
           << ",\"integrity\":\"" << integrity
           << "\",\"trading_gate\":\"" << trading_gate << "\"}";
    events_.emit("feed_gap", fields.str());
  }

  void apply_market(const Delivery &delivery) {
    std::lock_guard<std::mutex> lock(mutex_);
    book_.apply(delivery.message.data(), delivery.message.size());
    ++delivered_;
    const auto symbol = nasdaq::itch_symbol(delivery.message.data(), delivery.message.size());
    if (symbol == "AAPL" || symbol == "NVDA") {
      on_book(symbol, delivery);
    } else if (delivery.message[0] == 'E' || delivery.message[0] == 'C' ||
               delivery.message[0] == 'X' || delivery.message[0] == 'D' ||
               delivery.message[0] == 'U') {
      on_book("AAPL", delivery);
      on_book("NVDA", delivery);
    }
  }

  void on_book(const std::string &symbol, const Delivery &delivery) {
    const auto top = book_.top(symbol);
    if (!top.ready()) return;
    maybe_trade(symbol, delivery.sequence, delivery.receive_ns, top);
    if (config_.role != "AUTO") return;
    const auto now = std::chrono::steady_clock::now();
    if (now - last_quote_event_[symbol] < std::chrono::milliseconds(80)) return;
    last_quote_event_[symbol] = now;
    std::uint64_t next_expected{};
    std::uint64_t last_delivered{};
    std::uint64_t first_pending{};
    std::uint64_t highest_received{};
    std::uint64_t gap_age_ms{};
    std::size_t pending{};
    std::string session;
    std::string integrity;
    std::string trading_gate;
    {
      std::lock_guard<std::mutex> feed_lock(feed_mutex_);
      next_expected = feed_.next_expected();
      last_delivered = feed_.last_delivered();
      first_pending = feed_.first_pending();
      highest_received = feed_.highest_received();
      gap_age_ms = feed_.gap_age_ms(flle::monotonic_ns());
      pending = feed_.pending();
      session = feed_.session();
      integrity = feed_.integrity();
      trading_gate = feed_.trading_gate();
    }
    std::ostringstream fields;
    fields << "{\"symbol\":\"" << symbol << "\",\"session\":\""
           << session << "\",\"market_sequence\":" << delivery.sequence
           << ",\"market_path\":\"" << delivery.path << "\",\"next_expected\":"
           << next_expected << ",\"last_delivered\":" << last_delivered
           << ",\"first_pending\":" << first_pending
           << ",\"highest_received\":" << highest_received
           << ",\"gap_age_ms\":" << gap_age_ms
           << ",\"pending\":" << pending << ",\"duplicates\":"
           << duplicates_.load() << ",\"bids\":" << nasdaq::levels_json(top.bids)
           << ",\"asks\":" << nasdaq::levels_json(top.asks)
           << ",\"integrity\":\"" << integrity
           << "\",\"trading_gate\":\"" << trading_gate << "\"}";
    events_.emit("book_applied", fields.str());
  }

  void maybe_trade(const std::string &symbol, std::uint64_t sequence,
                   std::uint64_t receive_ns, const nasdaq::TopOfBook &top) {
    if (config_.role != "AUTO" || !strategy_enabled_) return;
    {
      std::lock_guard<std::mutex> feed_lock(feed_mutex_);
      if (feed_.pending() || feed_.gap_size()) return;
    }
    const auto bid_quantity = static_cast<double>(top.bids[0].shares);
    const auto ask_quantity = static_cast<double>(top.asks[0].shares);
    const double imbalance = (bid_quantity - ask_quantity) / (bid_quantity + ask_quantity);
    if (std::abs(imbalance) < imbalance_threshold_) return;
    const auto now = flle::monotonic_ns();
    if (now - last_action_ns_[symbol] < cooldown_ms_ * 1000000ULL) return;
    const auto side = imbalance > 0 ? nasdaq::Side::Buy : nasdaq::Side::Sell;
    const auto delta = side == nasdaq::Side::Buy
                           ? static_cast<std::int64_t>(strategy_quantity_)
                           : -static_cast<std::int64_t>(strategy_quantity_);
    const auto exposure = positions_[symbol] + pending_delta_[symbol];
    if (std::abs(exposure + delta) > max_position_) return;
    last_action_ns_[symbol] = now;
    queue_order(symbol, side, strategy_quantity_,
                side == nasdaq::Side::Buy ? top.asks[0].price_x10000
                                          : top.bids[0].price_x10000,
                sequence, receive_ns, imbalance, "AUTO_STRATEGY");
  }

  std::string clordid(std::uint32_t user_ref, bool measurement) {
    std::ostringstream out;
    const auto prefix = measurement
                            ? "M" + config_.clordid_prefix.substr(1)
                            : config_.clordid_prefix;
    out << prefix << std::setfill('0') << std::setw(10) << user_ref;
    return out.str();
  }

  std::optional<std::uint32_t> allocate_user_ref() {
    const auto end = static_cast<std::uint64_t>(config_.user_ref_base) +
                     config_.user_ref_span;
    return flle::allocate_bounded_user_ref(next_user_ref_, end);
  }

  std::uint32_t queue_order(const std::string &symbol, nasdaq::Side side,
                            std::uint32_t quantity, std::uint64_t price,
                            std::uint64_t signal_sequence, std::uint64_t receive_ns,
                            double imbalance, const std::string &origin,
                            bool measurement_sample = false) {
    const auto allocated_user_ref = allocate_user_ref();
    if (!allocated_user_ref) return 0;
    const auto user_ref = *allocated_user_ref;
    nasdaq::EnterOrder order{user_ref, side, quantity, symbol, price, '3', 'Y',
                             'A', 'N', 'N',
                             clordid(user_ref, measurement_sample)};
    const auto delta = side == nasdaq::Side::Buy
                           ? static_cast<std::int64_t>(quantity)
                           : -static_cast<std::int64_t>(quantity);
    pending_delta_[symbol] += delta;
    const auto queued_ns = flle::monotonic_ns();
    if (!order_queue_.push(WorkOrder{order, receive_ns, queued_ns, imbalance, origin,
                                     paper_epoch_.load(), measurement_sample,
                                     measurement_generation_.load()})) {
      pending_delta_[symbol] -= delta;
      ++queue_full_drops_;
      return 0;
    }
    ++orders_;
    if (!measurement_sample) {
      std::ostringstream fields;
      fields << "{\"client_order_id\":" << user_ref << ",\"user_ref\":" << user_ref
             << ",\"clordid\":\"" << order.clordid << "\",\"origin\":\"" << origin
             << "\",\"order_transport\":\"" << config_.order_transport
             << "\",\"symbol\":\"" << symbol << "\",\"side\":\""
             << nasdaq::side_name(side) << "\",\"quantity\":" << quantity
             << ",\"limit_price_x10000\":" << price << ",\"signal_sequence\":"
             << signal_sequence << ",\"imbalance\":" << imbalance
             << ",\"paper_epoch\":" << paper_epoch_.load() << '}';
      events_.emit("order_queued", fields.str());
    }
    return user_ref;
  }

  bool connect_order_session(flle::OrderTransport &transport) {
    if (!transport.connect(config_.data_ip, config_.exchange_data_ip,
                           config_.order_port))
      return false;
    const auto login = nasdaq::soup_login_request(
        config_.role == "AUTO"
            ? "FLLEA1"
            : (config_.order_transport == "TCPDIRECT_ZF"
                   ? "FLLET1"
                   : (config_.order_transport == "OPENONLOAD" ? "FLLEO1"
                                                               : "FLLEM1")),
        "PAPER");
    if (!nasdaq::send_soup(transport, 'L', login.data(), login.size())) {
      transport.close();
      return false;
    }
    char type{};
    std::vector<std::uint8_t> payload;
    if (!nasdaq::recv_soup(transport, type, payload) || type != 'A' ||
        payload.size() != nasdaq::kSoupLoginAcceptedBytes) {
      transport.close();
      return false;
    }
    events_.emit("order_session",
                 "{\"status\":\"LOGIN_ACCEPTED\",\"protocol\":\"SoupBinTCP\","
                 "\"order_transport\":\"" +
                     config_.order_transport + "\"}");
    return true;
  }

  bool transact(flle::OrderTransport &transport, const WorkOrder &work) {
    if (work.paper_epoch != paper_epoch_.load()) return true;
    const auto encoded = nasdaq::encode_enter(work.order);
    const auto send_ns = flle::monotonic_ns();
    order_thread_cpu_.store(::sched_getcpu());
    if (!nasdaq::send_soup(transport, 'U', encoded.data(), encoded.size()))
      return false;
    if (work.signal_receive_ns) {
      std::lock_guard<std::mutex> lock(mutex_);
      if (work.paper_epoch == paper_epoch_.load())
        push_sample(reaction_samples_, send_ns - work.signal_receive_ns);
    }
    bool terminal = false;
    while (!terminal) {
      char type{};
      std::vector<std::uint8_t> payload;
      if (!nasdaq::recv_soup(transport, type, payload)) return false;
      if (type != 'S') continue;
      nasdaq::OuchResponse response;
      std::string error;
      if (!nasdaq::decode_response(payload.data(), payload.size(), response, error) ||
          response.user_ref != work.order.user_ref) return false;
      if (response.type == 'A') {
        // Keep synchronous UI telemetry outside the formal order-session
        // measurement window.
        if (!work.measurement_sample &&
            work.paper_epoch == paper_epoch_.load())
          events_.emit("order_accepted", "{\"client_order_id\":" +
                           std::to_string(work.order.user_ref) + ",\"user_ref\":" +
                           std::to_string(work.order.user_ref) + ",\"order_reference\":" +
                           std::to_string(response.order_reference) + "}");
        continue;
      }
      terminal = response.type == 'E' || response.type == 'J';
      if (!terminal) continue;
      const auto completed_ns = flle::monotonic_ns();
      order_rx_cpu_.store(transport.incoming_cpu());
      order_thread_cpu_.store(::sched_getcpu());
      const auto queue_to_send_ns = send_ns - work.queued_ns;
      const auto submit_to_final_ns = completed_ns - work.queued_ns;
      const auto delta = work.order.side == nasdaq::Side::Buy
                             ? static_cast<std::int64_t>(work.order.quantity)
                             : -static_cast<std::int64_t>(work.order.quantity);
      std::int64_t position{};
      std::int64_t pnl{};
      {
        std::lock_guard<std::mutex> lock(mutex_);
        if (work.paper_epoch != paper_epoch_.load()) return true;
        pending_delta_[work.order.symbol] -= delta;
        if (response.type == 'E') {
          positions_[work.order.symbol] += delta;
          cash_x10000_ -= delta * static_cast<std::int64_t>(response.price_x10000);
          ++fills_;
        } else {
          ++rejects_;
        }
        push_order_sample(work.order.user_ref, response.type, completed_ns - send_ns);
        if (work.measurement_sample &&
            work.measurement_generation == measurement_generation_.load()) {
          measurement_samples_.push_back(completed_ns - send_ns);
          measurement_queue_samples_.push_back(queue_to_send_ns);
          measurement_total_samples_.push_back(submit_to_final_ns);
          measurement_order_refs_.push_back(work.order.user_ref);
          measurement_results_.push_back(response.type);
        }
        position = positions_[work.order.symbol];
        pnl = mark_to_market();
      }
      if (!work.measurement_sample) {
        std::ostringstream fields;
        fields << "{\"client_order_id\":" << work.order.user_ref
             << ",\"user_ref\":" << work.order.user_ref << ",\"clordid\":\""
             << work.order.clordid << "\",\"origin\":\"" << work.origin
             << "\",\"order_transport\":\"" << config_.order_transport
             << "\",\"symbol\":\"" << work.order.symbol << "\",\"side\":\""
             << nasdaq::side_name(work.order.side) << "\",\"quantity\":"
             << work.order.quantity << ",\"filled_quantity\":"
             << (response.type == 'E' ? response.quantity : 0)
             << ",\"position_delta\":"
             << (response.type == 'E'
                     ? (work.order.side == nasdaq::Side::Buy
                            ? static_cast<std::int64_t>(response.quantity)
                            : -static_cast<std::int64_t>(response.quantity))
                     : 0)
             << ",\"fill_price_x10000\":" << response.price_x10000
             << ",\"exchange_source_timestamp_ns\":" << response.timestamp_ns
             << ",\"result\":\"" << (response.type == 'E' ? "ORDER_EXECUTED" : "ORDER_REJECTED")
             << "\",\"reject_reason\":\"" << response.reason
             << "\",\"order_rtt_ns\":" << completed_ns - send_ns
             << ",\"queue_to_send_ns\":" << queue_to_send_ns
             << ",\"submit_to_final_ns\":" << submit_to_final_ns
             << ",\"order_queue\":\"" << order_queue_.mode_name() << "\""
             << ",\"position\":" << position
             << ",\"pnl_x10000\":" << pnl << '}';
        events_.emit("order_complete", fields.str());
      }
    }
    return true;
  }

  void order_loop() {
    order_thread_tid_.store(static_cast<int>(::syscall(SYS_gettid)));
    order_thread_cpu_.store(::sched_getcpu());
    auto transport = flle::make_order_transport();
    bool connected = false;
    std::uint64_t connected_epoch{};
    while (!g_stop.load()) {
      WorkOrder work;
      if (!order_queue_.front(work, g_stop)) continue;
      if (connected && connected_epoch != work.paper_epoch) {
        transport->close();
        connected = false;
      }
      if (!connected) {
        connected = connect_order_session(*transport);
        if (!connected) {
          std::this_thread::sleep_for(std::chrono::milliseconds(250));
          continue;
        }
        connected_epoch = work.paper_epoch;
      }
      if (!transact(*transport, work)) {
        transport->close();
        connected = false;
        ++transport_retries_;
        continue;
      }
      order_queue_.pop();
      if (work.measurement_sample &&
          work.measurement_generation == measurement_generation_.load())
        ++measurement_ready_samples_;
    }
    transport->close();
  }

  static void push_sample(std::deque<std::uint64_t> &samples, std::uint64_t value) {
    samples.push_back(value);
    if (samples.size() > 20000) samples.pop_front();
  }

  void push_order_sample(std::uint32_t user_ref, char result, std::uint64_t value) {
    latency_samples_.push_back(value);
    latency_order_refs_.push_back(user_ref);
    latency_results_.push_back(result);
    if (latency_samples_.size() > 20000) {
      latency_samples_.pop_front();
      latency_order_refs_.pop_front();
      latency_results_.pop_front();
    }
  }

  static std::array<std::uint64_t, 3> percentiles(std::vector<std::uint64_t> samples) {
    if (samples.empty()) return {};
    std::sort(samples.begin(), samples.end());
    return {samples[(samples.size() - 1) / 2], samples[(samples.size() - 1) * 99 / 100], samples.back()};
  }

  std::int64_t mark_to_market() const {
    auto value = cash_x10000_;
    for (const auto &[symbol, position] : positions_) {
      const auto top = book_.top(symbol);
      if (top.ready()) value += position * static_cast<std::int64_t>(
          (top.bids[0].price_x10000 + top.asks[0].price_x10000) / 2);
    }
    return value;
  }

  std::string samples_json() {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto count = std::min(
        latency_samples_.size(), std::min(latency_order_refs_.size(), latency_results_.size()));
    std::ostringstream out;
    out << "{\"status\":\"ONLINE\",\"role\":\"" << config_.role
        << "\",\"paper_epoch\":" << paper_epoch_.load()
        << ",\"clock\":\"CLOCK_MONOTONIC\""
        << ",\"measurement\":\"OUCH_SEND_TO_FINAL_RESPONSE\",\"samples\":[";
    for (std::size_t index = 0; index < count; ++index) {
      if (index) out << ',';
      out << "{\"client_order_id\":" << latency_order_refs_[index]
          << ",\"result\":\"" << latency_results_[index]
          << "\",\"order_rtt_ns\":" << latency_samples_[index] << '}';
    }
    out << "]}";
    return out.str();
  }

  std::string measurement_samples_json() {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto count = std::min(measurement_samples_.size(),
        std::min(measurement_queue_samples_.size(),
        std::min(measurement_total_samples_.size(),
        std::min(measurement_order_refs_.size(), measurement_results_.size()))));
    std::ostringstream out;
    out << "{\"status\":\"ONLINE\",\"role\":\"" << config_.role
        << "\",\"paper_epoch\":" << paper_epoch_.load()
        << ",\"measurement_generation\":" << measurement_generation_.load()
        << ",\"clock\":\"CLOCK_MONOTONIC\""
        << ",\"measurement\":\"OUCH_SEND_TO_FINAL_RESPONSE\",\"samples\":[";
    for (std::size_t index = 0; index < count; ++index) {
      if (index) out << ',';
      out << "{\"client_order_id\":" << measurement_order_refs_[index]
          << ",\"result\":\"" << measurement_results_[index]
          << "\",\"queue_to_send_ns\":" << measurement_queue_samples_[index]
          << ",\"order_rtt_ns\":" << measurement_samples_[index]
          << ",\"submit_to_final_ns\":" << measurement_total_samples_[index]
          << '}';
    }
    out << "]}";
    return out.str();
  }

  void emit_heartbeat() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::lock_guard<std::mutex> feed_lock(feed_mutex_);
    std::ostringstream fields;
    fields << "{\"status\":\"ONLINE\",\"session\":\"" << feed_.session()
           << "\",\"next_expected\":" << feed_.next_expected()
           << ",\"last_delivered\":" << feed_.last_delivered()
           << ",\"first_pending\":" << feed_.first_pending()
           << ",\"highest_received\":" << feed_.highest_received()
           << ",\"gap_age_ms\":"
           << feed_.gap_age_ms(flle::monotonic_ns())
           << ",\"integrity\":\"" << feed_.integrity()
           << "\",\"trading_gate\":\"" << feed_.trading_gate()
           << "\",\"pending\":" << feed_.pending()
           << ",\"gap_size\":" << feed_.gap_size()
           << ",\"received\":" << received_
           << ",\"delivered\":" << delivered_ << ",\"duplicates\":" << duplicates_
           << ",\"gaps\":" << gaps_ << ",\"bad_packets\":" << bad_packets_
           << ",\"orders\":" << orders_ << ",\"fills\":" << fills_
           << ",\"rejects\":" << rejects_ << ",\"transport_retries\":"
           << transport_retries_ << ",\"order_queue\":\""
           << order_queue_.mode_name() << "\",\"order_transport\":\""
           << config_.order_transport << "\"}";
    events_.emit("component_heartbeat", fields.str());
  }

  std::string state_json() {
    std::string session;
    std::uint64_t next_expected{};
    std::uint64_t last_delivered{};
    std::uint64_t first_pending{};
    std::uint64_t highest_received{};
    std::size_t pending{};
    std::uint64_t gap_size{};
    std::uint64_t gap_age_ms{};
    std::string integrity;
    std::string trading_gate;
    bool strategy_enabled{};
    double imbalance_threshold{};
    std::uint32_t strategy_quantity{};
    std::int64_t max_position{};
    std::uint64_t cooldown_ms{};
    std::int64_t aapl_position{};
    std::int64_t nvda_position{};
    std::int64_t pnl{};
    std::vector<std::uint64_t> latency_samples;
    std::vector<std::uint64_t> measurement_samples;
    std::vector<std::uint64_t> measurement_queue_samples;
    std::vector<std::uint64_t> measurement_total_samples;
    std::vector<std::uint64_t> reaction_samples;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      std::lock_guard<std::mutex> feed_lock(feed_mutex_);
      session = feed_.session();
      next_expected = feed_.next_expected();
      last_delivered = feed_.last_delivered();
      first_pending = feed_.first_pending();
      highest_received = feed_.highest_received();
      pending = feed_.pending();
      gap_size = feed_.gap_size();
      gap_age_ms = feed_.gap_age_ms(flle::monotonic_ns());
      integrity = feed_.integrity();
      trading_gate = feed_.trading_gate();
      strategy_enabled = strategy_enabled_;
      imbalance_threshold = imbalance_threshold_;
      strategy_quantity = strategy_quantity_;
      max_position = max_position_;
      cooldown_ms = cooldown_ms_;
      aapl_position = positions_["AAPL"];
      nvda_position = positions_["NVDA"];
      pnl = mark_to_market();
      latency_samples.assign(latency_samples_.begin(), latency_samples_.end());
      measurement_samples.assign(measurement_samples_.begin(), measurement_samples_.end());
      measurement_queue_samples.assign(measurement_queue_samples_.begin(),
                                       measurement_queue_samples_.end());
      measurement_total_samples.assign(measurement_total_samples_.begin(),
                                       measurement_total_samples_.end());
      reaction_samples.assign(reaction_samples_.begin(), reaction_samples_.end());
    }
    const auto latency_count = latency_samples.size();
    const auto measurement_count = measurement_samples.size();
    const auto reaction_count = reaction_samples.size();
    const auto latency = percentiles(std::move(latency_samples));
    const auto measurement = percentiles(std::move(measurement_samples));
    const auto measurement_queue = percentiles(std::move(measurement_queue_samples));
    const auto measurement_total = percentiles(std::move(measurement_total_samples));
    const auto reaction = percentiles(std::move(reaction_samples));
    const auto order_tid = order_thread_tid_.load();
    const auto order_allowed_count = flle::affinity_count(order_tid);
    const auto management_tid = management_thread_tid_.load();
    const auto management_allowed_count = flle::affinity_count(management_tid);
    std::ostringstream out;
    out << "{\"status\":\"ONLINE\",\"role\":\"" << config_.role
        << "\",\"market_protocol\":\""
        << (config_.market_receiver_enabled ? "ITCH_5.0_OVER_MOLDUDP64"
                                            : "COMMON_GATEWAY_BOOK")
        << "\""
        << ",\"order_protocol\":\"OUCH_5.0_OVER_SOUPBINTCP\""
        << ",\"order_transport\":\"" << config_.order_transport
        << "\",\"tcp_nodelay\":"
        << (config_.order_transport == "TCPDIRECT_ZF" ? "null" : "true")
        << ",\"nagle_semantics\":\""
        << (config_.order_transport == "TCPDIRECT_ZF"
                ? "ZF_API_NO_POSIX_TCP_NODELAY"
                : "POSIX_CONNECT_GETSOCKOPT_VERIFIED")
        << "\",\"session\":\""
        << session << "\",\"next_expected\":" << next_expected
        << ",\"last_delivered\":" << last_delivered
        << ",\"first_pending\":" << first_pending
        << ",\"highest_received\":" << highest_received
        << ",\"pending\":" << pending << ",\"gap_size\":" << gap_size
        << ",\"gap_age_ms\":" << gap_age_ms
        << ",\"integrity\":\"" << integrity
        << "\",\"trading_gate\":\"" << trading_gate << "\""
        << ",\"paper_epoch\":" << paper_epoch_.load()
        << ",\"user_ref_base\":" << config_.user_ref_base
        << ",\"user_ref_span\":" << config_.user_ref_span
        << ",\"user_ref_end_exclusive\":"
        << static_cast<std::uint64_t>(config_.user_ref_base) +
               config_.user_ref_span
        << ",\"user_ref_next\":" << next_user_ref_.load()
        << ",\"market_receiver_ready\":" << (market_receiver_ready_ ? "true" : "false")
        << ",\"strategy\":{\"enabled\":" << (strategy_enabled ? "true" : "false")
        << ",\"imbalance_threshold\":" << imbalance_threshold << ",\"quantity\":"
        << strategy_quantity << ",\"max_position\":" << max_position
        << ",\"cooldown_ms\":" << cooldown_ms << "},\"positions\":{\"AAPL\":"
        << aapl_position << ",\"NVDA\":" << nvda_position
        << "},\"pnl_x10000\":" << pnl
        << ",\"stats\":{\"orders\":" << orders_ << ",\"fills\":" << fills_
        << ",\"rejects\":" << rejects_ << ",\"transport_retries\":" << transport_retries_
        << ",\"received\":" << received_ << ",\"delivered\":" << delivered_
        << "},\"latency\":{\"samples\":" << latency_count
        << ",\"p50_ns\":" << latency[0] << ",\"p99_ns\":" << latency[1]
        << ",\"max_ns\":" << latency[2]
        << "},\"measurement_latency\":{\"samples\":" << measurement_count
        << ",\"ready_samples\":" << measurement_ready_samples_.load()
        << ",\"p50_ns\":" << measurement[0] << ",\"p99_ns\":" << measurement[1]
        << ",\"max_ns\":" << measurement[2]
        << ",\"generation\":" << measurement_generation_.load()
        << "},\"software_latency\":{\"samples\":" << measurement_count
        << ",\"queue_mode\":\"" << order_queue_.mode_name()
        << "\",\"queue_locked\":"
        << (config_.lock_order_queue ? "true" : "false")
        << ",\"network_engine\":\""
        << (config_.order_transport == "TCPDIRECT_ZF"
                ? "ZF_REACTOR_POLL"
                : (config_.order_transport == "OPENONLOAD"
                       ? "ONLOAD_USER_STACK"
                       : "KERNEL_SOCKET"))
        << "\",\"queue_capacity\":" << order_queue_.capacity()
        << ",\"queue_depth\":" << order_queue_.depth()
        << ",\"queue_full_drops\":" << queue_full_drops_.load()
        << ",\"order_thread_tid\":" << order_tid
        << ",\"order_thread_cpu\":" << order_thread_cpu_.load()
        << ",\"order_thread_allowed_count\":" << order_allowed_count
        << ",\"order_rx_cpu\":" << order_rx_cpu_.load()
        << ",\"management_thread_tid\":" << management_tid
        << ",\"management_thread_cpu\":" << management_thread_cpu_.load()
        << ",\"management_thread_allowed_count\":"
        << management_allowed_count
        << ",\"queue_to_send\":{\"p50_ns\":" << measurement_queue[0]
        << ",\"p99_ns\":" << measurement_queue[1]
        << ",\"max_ns\":" << measurement_queue[2]
        << "},\"submit_to_final\":{\"p50_ns\":" << measurement_total[0]
        << ",\"p99_ns\":" << measurement_total[1]
        << ",\"max_ns\":" << measurement_total[2] << "}"
        << "},\"reaction_latency\":{\"samples\":"
        << reaction_count << ",\"p50_ns\":" << reaction[0]
        << ",\"p99_ns\":" << reaction[1] << ",\"max_ns\":" << reaction[2] << "}}";
    return out.str();
  }

  std::string command(const std::string &line) {
    const auto parts = flle::split(line, '|');
    if (parts.size() == 1 && parts[0] == "STATE") return state_json();
    if (parts.size() == 1 && parts[0] == "MEASUREMENT_PROGRESS")
      return "{\"measurement_generation\":" +
             std::to_string(measurement_generation_.load()) +
             ",\"ready_samples\":" +
             std::to_string(measurement_ready_samples_.load()) + "}";
    if (parts.size() == 1 && parts[0] == "SAMPLES") return samples_json();
    if (parts.size() == 1 && parts[0] == "MEASUREMENT_SAMPLES")
      return measurement_samples_json();
    if (parts.size() == 2 && parts[0] == "SOFTWARE_PROFILE") {
      if (config_.role != "MANUAL")
        return "{\"error\":\"only manual client changes the software profile\"}";
      if (config_.lock_order_queue)
        return "{\"error\":\"chapter 06 locks order_queue to DEQUE_CV\"}";
      flle::OrderQueueMode mode;
      if (parts[1] == "DEQUE_CV") mode = flle::OrderQueueMode::DequeCv;
      else if (parts[1] == "FIXED_CV") mode = flle::OrderQueueMode::FixedCv;
      else if (parts[1] == "SPSC_SPIN") mode = flle::OrderQueueMode::SpscSpin;
      else return "{\"error\":\"unknown software profile\"}";
      if (!order_queue_.set_mode(mode))
        return "{\"error\":\"order queue must be empty before profile change\"}";
      return "{\"ok\":true,\"order_queue\":\"" +
             std::string(order_queue_.mode_name()) + "\",\"capacity\":" +
             std::to_string(order_queue_.capacity()) + "}";
    }
    if (parts.size() == 1 && parts[0] == "MEASUREMENT_RESET") {
      std::lock_guard<std::mutex> lock(mutex_);
      measurement_samples_.clear();
      measurement_queue_samples_.clear();
      measurement_total_samples_.clear();
      measurement_order_refs_.clear();
      measurement_results_.clear();
      measurement_ready_samples_ = 0;
      const auto generation = ++measurement_generation_;
      return "{\"ok\":true,\"measurement_generation\":" +
             std::to_string(generation) + ",\"paper_epoch\":" +
             std::to_string(paper_epoch_.load()) + "}";
    }
    std::lock_guard<std::mutex> lock(mutex_);
    if (parts.size() == 6 && parts[0] == "STRATEGY") {
      if (config_.role != "AUTO")
        return "{\"error\":\"manual client has no automatic strategy\"}";
      const bool enabled = parts[1] == "1";
      const auto threshold = std::stod(parts[2]);
      const auto quantity = static_cast<std::uint32_t>(std::stoul(parts[3]));
      const auto max_position = std::stoll(parts[4]);
      const auto cooldown = std::stoull(parts[5]);
      if (threshold < 0.05 || threshold > 0.95 || !quantity || max_position < 1 ||
          cooldown < 100) return "{\"error\":\"invalid strategy values\"}";
      strategy_enabled_ = enabled;
      imbalance_threshold_ = threshold;
      strategy_quantity_ = quantity;
      max_position_ = max_position;
      cooldown_ms_ = cooldown;
      return "{\"ok\":true}";
    }
    if (parts.size() == 5 &&
        (parts[0] == "ORDER" || parts[0] == "MEASUREMENT_ORDER")) {
      const bool measurement_order = parts[0] == "MEASUREMENT_ORDER";
      if (!measurement_order && config_.role != "MANUAL")
        return "{\"error\":\"automatic client does not accept manual orders\"}";
      const auto symbol = parts[1];
      if (parts[2] != "BUY" && parts[2] != "SELL")
        return "{\"error\":\"invalid side\"}";
      const auto side = parts[2] == "BUY" ? nasdaq::Side::Buy : nasdaq::Side::Sell;
      const auto quantity = static_cast<std::uint32_t>(std::stoul(parts[3]));
      auto price = std::stoull(parts[4]);
      if ((symbol != "AAPL" && symbol != "NVDA") || !quantity)
        return "{\"error\":\"invalid order\"}";
      const auto top = book_.top(symbol);
      if (!top.ready()) return "{\"error\":\"book not ready\"}";
      {
        std::lock_guard<std::mutex> feed_lock(feed_mutex_);
        if (feed_.integrity() != "HEALTHY")
          return "{\"error\":\"FEED_NOT_HEALTHY\",\"integrity\":\"" +
                 feed_.integrity() + "\",\"trading_gate\":\"" +
                 feed_.trading_gate() + "\"}";
      }
      const auto delta = side == nasdaq::Side::Buy
                             ? static_cast<std::int64_t>(quantity)
                             : -static_cast<std::int64_t>(quantity);
      const auto exposure = positions_[symbol] + pending_delta_[symbol];
      if (std::abs(exposure + delta) > max_position_ &&
          std::abs(exposure + delta) >= std::abs(exposure))
        return "{\"error\":\"position limit\"}";
      if (!price) price = side == nasdaq::Side::Buy ? top.asks[0].price_x10000
                                                    : top.bids[0].price_x10000;
      const auto user_ref = queue_order(symbol, side, quantity, price, 0, 0, 0,
                                        measurement_order && config_.role == "AUTO"
                                            ? "AUTO_CONTROL"
                                            : "MANUAL_GUI",
                                        measurement_order);
      if (!user_ref) {
        const auto user_ref_end =
            static_cast<std::uint64_t>(config_.user_ref_base) +
            config_.user_ref_span;
        if (next_user_ref_.load() >= user_ref_end)
          return "{\"error\":\"user-ref namespace exhausted\"}";
        return "{\"error\":\"order queue full\"}";
      }
      return "{\"ok\":true,\"client_order_id\":" + std::to_string(user_ref) + "}";
    }
    return "{\"error\":\"invalid command\"}";
  }

  void management_server() {
    management_thread_tid_.store(static_cast<int>(::syscall(SYS_gettid)));
    management_thread_cpu_.store(::sched_getcpu());
    const int listener = flle::tcp_listener(config_.management_ip, config_.management_port);
    while (!g_stop.load()) {
      pollfd descriptor{listener, POLLIN, 0};
      if (::poll(&descriptor, 1, 200) <= 0) continue;
      const int client = ::accept(listener, nullptr, nullptr);
      if (client < 0) continue;
      std::array<char, 2048> buffer{};
      const auto length = ::recv(client, buffer.data(), buffer.size() - 1, 0);
      if (length > 0) {
        std::string line(buffer.data(), static_cast<std::size_t>(length));
        const auto last = line.find_last_not_of("\r\n");
        line.erase(last == std::string::npos ? 0 : last + 1);
        const auto response = command(line) + "\n";
        flle::send_all(client, response.data(), response.size());
      }
      ::close(client);
    }
    ::close(listener);
  }
};

void signal_handler(int) { g_stop.store(true); }

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);
  try {
    Trader(parse_config(argc, argv)).run();
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "flle-trader: " << error.what() << '\n';
    return 1;
  }
}
