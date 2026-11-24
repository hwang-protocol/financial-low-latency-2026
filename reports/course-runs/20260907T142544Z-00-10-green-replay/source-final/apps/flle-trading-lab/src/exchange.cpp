#include "itch_book.hpp"

#include <poll.h>

#include <atomic>
#include <condition_variable>
#include <csignal>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <thread>
#include <unordered_map>

namespace {

namespace nasdaq = flle::nasdaq;
std::atomic<bool> g_stop{false};

struct Config {
  std::string data_ip{"20.1.1.1"};
  std::string trader_data_ip{"20.1.1.2"};
  std::string management_ip{"10.1.1.1"};
  std::string telemetry_host{"10.1.1.101"};
  std::string multicast_group{"239.20.1.20"};
  std::string replay_file{"AAPL_NVDA.itch"};
  std::string book_checkpoint{"opening-book.checkpoint"};
  std::string market_date{"2026-06-12"};
  std::string market_mode{"MULTICAST"};
  std::uint16_t multicast_port{42120};
  std::uint16_t unicast_port{42121};
  std::uint16_t manual_unicast_port{42122};
  std::uint16_t onload_unicast_port{42123};
  std::uint16_t tcpdirect_unicast_port{42124};
  std::uint16_t dpdk_unicast_port{42125};
  std::uint16_t order_port{43120};
  std::uint16_t management_port{48120};
  std::uint16_t telemetry_port{46120};
  double replay_speed{1.0};
  double loop_pause_seconds{2.0};
  std::uint64_t first_source_timestamp_ns{34200000000000ULL};
  std::uint64_t last_source_timestamp_ns{57600000000000ULL};
};

std::string arg_value(int argc, char **argv, const std::string &name,
                      const std::string &fallback) {
  for (int index = 1; index + 1 < argc; ++index)
    if (argv[index] == name) return argv[index + 1];
  return fallback;
}

Config parse_config(int argc, char **argv) {
  Config c;
  c.data_ip = arg_value(argc, argv, "--data-ip", c.data_ip);
  c.trader_data_ip = arg_value(argc, argv, "--trader-data-ip", c.trader_data_ip);
  c.management_ip = arg_value(argc, argv, "--management-ip", c.management_ip);
  c.telemetry_host = arg_value(argc, argv, "--telemetry-host", c.telemetry_host);
  c.multicast_group = arg_value(argc, argv, "--multicast-group", c.multicast_group);
  c.replay_file = arg_value(argc, argv, "--replay-file", c.replay_file);
  c.book_checkpoint = arg_value(argc, argv, "--book-checkpoint", c.book_checkpoint);
  c.market_date = arg_value(argc, argv, "--market-date", c.market_date);
  c.market_mode = arg_value(argc, argv, "--market-mode", c.market_mode);
  c.replay_speed = std::stod(arg_value(argc, argv, "--replay-speed", "1"));
  c.loop_pause_seconds = std::stod(arg_value(argc, argv, "--loop-pause-seconds", "2"));
  c.multicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--multicast-port", std::to_string(c.multicast_port))));
  c.unicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--unicast-port", std::to_string(c.unicast_port))));
  c.manual_unicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--manual-unicast-port", std::to_string(c.manual_unicast_port))));
  c.onload_unicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--onload-unicast-port", std::to_string(c.onload_unicast_port))));
  c.tcpdirect_unicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--tcpdirect-unicast-port", std::to_string(c.tcpdirect_unicast_port))));
  c.dpdk_unicast_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--dpdk-unicast-port", std::to_string(c.dpdk_unicast_port))));
  c.order_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--order-port", std::to_string(c.order_port))));
  c.management_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--management-port", std::to_string(c.management_port))));
  c.telemetry_port = static_cast<std::uint16_t>(std::stoi(arg_value(argc, argv, "--telemetry-port", std::to_string(c.telemetry_port))));
  if (c.replay_speed < 0.05 || c.replay_speed > 100.0)
    throw std::runtime_error("replay speed must be 0.05..100");
  if (c.loop_pause_seconds < 0.0 || c.loop_pause_seconds > 30.0)
    throw std::runtime_error("loop pause must be 0..30 seconds");
  if (c.first_source_timestamp_ns >= c.last_source_timestamp_ns)
    throw std::runtime_error("invalid source timestamp range");
  return c;
}

std::string source_clock(std::uint64_t timestamp_ns) {
  const auto total_seconds = timestamp_ns / 1000000000ULL;
  const auto nanoseconds = timestamp_ns % 1000000000ULL;
  std::ostringstream out;
  out << std::setfill('0') << std::setw(2) << total_seconds / 3600ULL << ':'
      << std::setw(2) << (total_seconds / 60ULL) % 60ULL << ':'
      << std::setw(2) << total_seconds % 60ULL << '.' << std::setw(9) << nanoseconds;
  return out.str();
}

std::string make_session(std::uint64_t loop) {
  std::ostringstream out;
  out << "061226" << std::setfill('0') << std::setw(4) << (loop % 10000ULL);
  return out.str();
}

class Exchange {
 public:
  explicit Exchange(Config config)
      : config_(std::move(config)),
        events_("exchange", config_.telemetry_host, config_.telemetry_port) {
    std::ifstream probe(config_.replay_file, std::ios::binary);
    if (!probe) throw std::runtime_error("cannot open replay file " + config_.replay_file);
    std::ifstream checkpoint(config_.book_checkpoint, std::ios::binary);
    if (!checkpoint) throw std::runtime_error("cannot open book checkpoint " + config_.book_checkpoint);
    market_fd_ = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (market_fd_ < 0) throw std::runtime_error("market socket failed");
    sockaddr_in source{};
    source.sin_family = AF_INET;
    ::inet_pton(AF_INET, config_.data_ip.c_str(), &source.sin_addr);
    if (::bind(market_fd_, reinterpret_cast<sockaddr *>(&source), sizeof(source)) < 0)
      throw std::runtime_error("market bind failed: " + std::string(std::strerror(errno)));
    in_addr interface{};
    ::inet_pton(AF_INET, config_.data_ip.c_str(), &interface);
    ::setsockopt(market_fd_, IPPROTO_IP, IP_MULTICAST_IF, &interface, sizeof(interface));
    unsigned char ttl = 1;
    ::setsockopt(market_fd_, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, sizeof(ttl));
    multicast_target_ = target(config_.multicast_group, config_.multicast_port);
    unicast_target_ = target(config_.trader_data_ip, config_.unicast_port);
    manual_unicast_target_ = target(config_.trader_data_ip, config_.manual_unicast_port);
    onload_unicast_target_ = target(config_.trader_data_ip, config_.onload_unicast_port);
    tcpdirect_unicast_target_ = target(config_.trader_data_ip, config_.tcpdirect_unicast_port);
    dpdk_unicast_target_ = target(config_.trader_data_ip, config_.dpdk_unicast_port);
  }

  ~Exchange() { if (market_fd_ >= 0) ::close(market_fd_); }

  void run() {
    std::thread replay([this] { run_guarded(&Exchange::replay_loop); });
    std::thread orders([this] { run_guarded(&Exchange::order_server); });
    std::thread management([this] { run_guarded(&Exchange::management_server); });
    events_.emit("component_start",
                 "{\"status\":\"ONLINE\",\"protocol\":\"ITCH_5.0_OVER_MOLDUDP64\"," 
                 "\"source\":\"NASDAQ_PUBLIC_ITCH_SAMPLE\",\"market_date\":\"" +
                     config_.market_date + "\"}");
    replay.join();
    orders.join();
    management.join();
    shutdown_clients();
    for (auto &thread : client_threads_) if (thread.joinable()) thread.join();
    if (failure_) std::rethrow_exception(failure_);
  }

 private:
  Config config_;
  flle::EventEmitter events_;
  nasdaq::ItchBook book_;
  std::mutex state_mutex_;
  std::condition_variable replay_condition_;
  int market_fd_{-1};
  sockaddr_in multicast_target_{};
  sockaddr_in unicast_target_{};
  sockaddr_in manual_unicast_target_{};
  sockaddr_in onload_unicast_target_{};
  sockaddr_in tcpdirect_unicast_target_{};
  sockaddr_in dpdk_unicast_target_{};
  std::string session_;
  std::uint64_t mold_sequence_{1};
  std::uint64_t source_timestamp_ns_{};
  std::uint64_t loop_{};
  std::uint64_t replay_messages_{};
  std::uint64_t order_reference_{100000};
  std::uint64_t match_number_{900000};
  std::atomic<std::uint64_t> soup_sequence_{1};
  bool paused_{};
  std::optional<std::chrono::steady_clock::time_point> pause_deadline_;
  std::uint64_t pause_lease_ms_{};
  bool restart_requested_{};
  bool loop_complete_{};
  std::uint64_t timing_epoch_{};
  std::map<std::string, std::chrono::steady_clock::time_point> last_quote_event_;
  std::mutex failure_mutex_;
  std::exception_ptr failure_;
  std::mutex clients_mutex_;
  std::set<int> clients_;
  std::vector<std::thread> client_threads_;

  struct LedgerEntry {
    nasdaq::EnterOrder order;
    std::vector<std::vector<std::uint8_t>> responses;
  };
  std::unordered_map<std::uint32_t, LedgerEntry> ledger_;
  std::vector<std::uint32_t> auto_ledger_order_;
  std::vector<std::uint32_t> manual_ledger_order_;

  void run_guarded(void (Exchange::*function)()) {
    try { (this->*function)(); }
    catch (...) {
      {
        std::lock_guard<std::mutex> lock(failure_mutex_);
        if (!failure_) failure_ = std::current_exception();
      }
      g_stop.store(true);
      replay_condition_.notify_all();
    }
  }

  static sockaddr_in target(const std::string &ip, std::uint16_t port) {
    sockaddr_in result{};
    result.sin_family = AF_INET;
    result.sin_port = htons(port);
    if (::inet_pton(AF_INET, ip.c_str(), &result.sin_addr) != 1)
      throw std::runtime_error("invalid target " + ip);
    return result;
  }

  bool read_record(std::ifstream &input, std::vector<std::uint8_t> &message) {
    std::array<std::uint8_t, 2> prefix{};
    input.read(reinterpret_cast<char *>(prefix.data()), prefix.size());
    if (input.gcount() == 0) return false;
    if (input.gcount() != 2) throw std::runtime_error("truncated BinaryFILE prefix");
    const auto length = flle::get_u16(prefix.data());
    if (!length) return read_record(input, message);
    message.resize(length);
    input.read(reinterpret_cast<char *>(message.data()), length);
    if (input.gcount() != length) throw std::runtime_error("truncated BinaryFILE message");
    return true;
  }

  bool pace(std::uint64_t timestamp_ns, std::uint64_t &anchor_source,
            std::chrono::steady_clock::time_point &anchor_wall,
            std::uint64_t &seen_timing_epoch) {
    std::unique_lock<std::mutex> lock(state_mutex_);
    while (true) {
      while (paused_ && !restart_requested_ && !g_stop.load()) {
        if (!pause_deadline_) {
          replay_condition_.wait(lock);
          continue;
        }
        const auto deadline = *pause_deadline_;
        if (std::chrono::steady_clock::now() >= deadline) {
          paused_ = false;
          pause_deadline_.reset();
          pause_lease_ms_ = 0;
          ++timing_epoch_;
          break;
        }
        replay_condition_.wait_until(lock, deadline);
      }
      if (restart_requested_ || g_stop.load()) return false;
      if (!anchor_source || seen_timing_epoch != timing_epoch_) {
        seen_timing_epoch = timing_epoch_;
        anchor_source = source_timestamp_ns_ ? source_timestamp_ns_ : timestamp_ns;
        anchor_wall = std::chrono::steady_clock::now();
      }
      const auto source_delta = timestamp_ns > anchor_source
                                    ? timestamp_ns - anchor_source : 0;
      const auto scaled = static_cast<std::uint64_t>(
          static_cast<double>(source_delta) / config_.replay_speed);
      const auto target_time = anchor_wall + std::chrono::nanoseconds(scaled);
      if (!replay_condition_.wait_until(lock, target_time, [this, seen_timing_epoch] {
            return paused_ || restart_requested_ || g_stop.load() ||
                   timing_epoch_ != seen_timing_epoch;
          })) {
        source_timestamp_ns_ = timestamp_ns;
        return true;
      }
    }
  }

  void send_market(const std::vector<std::uint8_t> &message) {
    const auto packet = nasdaq::encode_mold(session_, mold_sequence_, {message});
    ++mold_sequence_;
    if (config_.market_mode == "MULTICAST" || config_.market_mode == "DUAL")
      ::sendto(market_fd_, packet.data(), packet.size(), 0,
               reinterpret_cast<sockaddr *>(&multicast_target_), sizeof(multicast_target_));
    if (config_.market_mode == "UNICAST" || config_.market_mode == "DUAL") {
      ::sendto(market_fd_, packet.data(), packet.size(), 0,
               reinterpret_cast<sockaddr *>(&unicast_target_), sizeof(unicast_target_));
      ::sendto(market_fd_, packet.data(), packet.size(), 0,
               reinterpret_cast<sockaddr *>(&manual_unicast_target_),
               sizeof(manual_unicast_target_));
      ::sendto(market_fd_, packet.data(), packet.size(), 0,
               reinterpret_cast<sockaddr *>(&onload_unicast_target_),
               sizeof(onload_unicast_target_));
      ::sendto(market_fd_, packet.data(), packet.size(), 0,
               reinterpret_cast<sockaddr *>(&tcpdirect_unicast_target_),
               sizeof(tcpdirect_unicast_target_));
      ::sendto(market_fd_, packet.data(), packet.size(), 0,
               reinterpret_cast<sockaddr *>(&dpdk_unicast_target_),
               sizeof(dpdk_unicast_target_));
    }
  }

  void emit_quote(const std::string &symbol) {
    const auto now = std::chrono::steady_clock::now();
    if (now - last_quote_event_[symbol] < std::chrono::milliseconds(80)) return;
    const auto top = book_.top(symbol);
    if (!top.ready()) return;
    last_quote_event_[symbol] = now;
    std::ostringstream fields;
    fields << "{\"source\":\"NASDAQ_PUBLIC_ITCH_SAMPLE\",\"historical_market\":true"
           << ",\"paper_execution\":true,\"market_date\":\"" << config_.market_date
           << "\",\"source_timestamp_ns\":" << source_timestamp_ns_
           << ",\"source_clock\":\"" << source_clock(source_timestamp_ns_)
           << "\",\"replay_loop\":" << loop_ << ",\"replay_speed\":"
           << config_.replay_speed << ",\"session\":\"" << session_
           << "\",\"market_mode\":\"" << config_.market_mode
           << "\",\"market_sequence\":" << mold_sequence_ - 1
           << ",\"symbol\":\"" << symbol << "\",\"bids\":"
           << nasdaq::levels_json(top.bids) << ",\"asks\":"
           << nasdaq::levels_json(top.asks) << ",\"last_x10000\":"
           << (top.last_x10000 ? top.last_x10000
                               : (top.bids[0].price_x10000 + top.asks[0].price_x10000) / 2)
           << ",\"volume\":" << top.volume << '}';
    events_.emit("market_update", fields.str());
  }

  void replay_loop() {
    while (!g_stop.load()) {
      {
        std::lock_guard<std::mutex> lock(state_mutex_);
        restart_requested_ = false;
        ++loop_;
        session_ = make_session(loop_);
        mold_sequence_ = 1;
        source_timestamp_ns_ = config_.first_source_timestamp_ns;
        replay_messages_ = 0;
        loop_complete_ = false;
        book_.clear();
        ledger_.clear();
        auto_ledger_order_.clear();
        manual_ledger_order_.clear();
        std::ifstream checkpoint(config_.book_checkpoint, std::ios::binary);
        if (!checkpoint) throw std::runtime_error("cannot reopen book checkpoint");
        book_.load_checkpoint(checkpoint);
      }
      std::ifstream input(config_.replay_file, std::ios::binary);
      if (!input) throw std::runtime_error("cannot reopen replay file");
      events_.emit("replay_started", "{\"source\":\"NASDAQ_PUBLIC_ITCH_SAMPLE\"," 
                   "\"market_date\":\"" + config_.market_date + "\",\"loop\":" +
                       std::to_string(loop_) + ",\"session\":\"" + session_ + "\"}");
      std::uint64_t anchor_source = 0;
      std::uint64_t seen_timing_epoch = timing_epoch_;
      auto anchor_wall = std::chrono::steady_clock::now();
      std::vector<std::uint8_t> message;
      while (!g_stop.load() && read_record(input, message)) {
        const auto timestamp = nasdaq::itch_timestamp(message.data(), message.size());
        if (!timestamp || *timestamp < config_.first_source_timestamp_ns) continue;
        if (*timestamp >= config_.last_source_timestamp_ns) break;
        if (!pace(*timestamp, anchor_source, anchor_wall, seen_timing_epoch)) break;
        std::lock_guard<std::mutex> lock(state_mutex_);
        if (restart_requested_) break;
        send_market(message);
        book_.apply(message.data(), message.size());
        ++replay_messages_;
        const auto symbol = nasdaq::itch_symbol(message.data(), message.size());
        if (symbol == "AAPL" || symbol == "NVDA") emit_quote(symbol);
        else if (message[0] == 'E' || message[0] == 'C' || message[0] == 'X' ||
                 message[0] == 'D' || message[0] == 'U') {
          emit_quote("AAPL");
          emit_quote("NVDA");
        }
      }
      if (!restart_requested_ && !g_stop.load()) {
        {
          std::lock_guard<std::mutex> lock(state_mutex_);
          source_timestamp_ns_ = config_.last_source_timestamp_ns;
          loop_complete_ = true;
        }
        events_.emit("replay_completed", "{\"market_date\":\"" + config_.market_date +
                         "\",\"loop\":" + std::to_string(loop_) + "}");
      }
      if (!restart_requested_ && !g_stop.load()) {
        std::unique_lock<std::mutex> lock(state_mutex_);
        replay_condition_.wait_for(
            lock, std::chrono::duration<double>(config_.loop_pause_seconds),
            [this] { return restart_requested_ || g_stop.load(); });
      }
    }
  }

  static bool same_order(const nasdaq::EnterOrder &a, const nasdaq::EnterOrder &b) {
    return a.user_ref == b.user_ref && a.side == b.side && a.quantity == b.quantity &&
           a.symbol == b.symbol && a.price_x10000 == b.price_x10000 &&
           a.clordid == b.clordid;
  }

  std::vector<std::vector<std::uint8_t>> process_order(const nasdaq::EnterOrder &order) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    const auto previous = ledger_.find(order.user_ref);
    if (previous != ledger_.end()) {
      if (same_order(previous->second.order, order)) return previous->second.responses;
      const auto reject = nasdaq::encode_rejected(
          nasdaq::Rejected{source_timestamp_ns_, order.user_ref, "DU", order.clordid});
      return {{reject.begin(), reject.end()}};
    }
    std::vector<std::vector<std::uint8_t>> responses;
    const auto top = book_.top(order.symbol);
    const bool known_symbol = order.symbol == "AAPL" || order.symbol == "NVDA";
    const bool crosses = known_symbol && top.ready() &&
        ((order.side == nasdaq::Side::Buy && order.price_x10000 >= top.asks[0].price_x10000) ||
         (order.side == nasdaq::Side::Sell && order.price_x10000 <= top.bids[0].price_x10000));
    if (!known_symbol || !top.ready() || !crosses) {
      const std::string reason = !known_symbol ? "SY" : (!top.ready() ? "NQ" : "PX");
      const auto reject = nasdaq::encode_rejected(
          nasdaq::Rejected{source_timestamp_ns_, order.user_ref, reason, order.clordid});
      responses.emplace_back(reject.begin(), reject.end());
    } else {
      const auto reference = ++order_reference_;
      const auto accepted = nasdaq::encode_accepted(
          nasdaq::Accepted{source_timestamp_ns_, order, reference, 'L'});
      const auto fill_price = order.side == nasdaq::Side::Buy
                                  ? top.asks[0].price_x10000 : top.bids[0].price_x10000;
      const auto executed = nasdaq::encode_executed(
          nasdaq::Executed{source_timestamp_ns_, order.user_ref, order.quantity,
                           fill_price, 'A', ++match_number_});
      responses.emplace_back(accepted.begin(), accepted.end());
      responses.emplace_back(executed.begin(), executed.end());
    }
    ledger_[order.user_ref] = LedgerEntry{order, responses};
    (order.clordid.rfind("AUTO", 0) == 0 ? auto_ledger_order_ : manual_ledger_order_)
        .push_back(order.user_ref);
    return responses;
  }

  void client_loop(int client) {
    {
      std::lock_guard<std::mutex> lock(clients_mutex_);
      clients_.insert(client);
    }
    const auto cleanup = [this, client] {
      {
        std::lock_guard<std::mutex> lock(clients_mutex_);
        clients_.erase(client);
      }
      ::close(client);
    };
    char packet_type{};
    std::vector<std::uint8_t> payload;
    if (!nasdaq::recv_soup(client, packet_type, payload) || packet_type != 'L' ||
        payload.size() != nasdaq::kSoupLoginRequestBytes) {
      cleanup();
      return;
    }
    std::string session;
    {
      std::lock_guard<std::mutex> lock(state_mutex_);
      session = session_;
    }
    const auto accepted = nasdaq::soup_login_accepted(session, soup_sequence_.load());
    if (!nasdaq::send_soup(client, 'A', accepted.data(), accepted.size())) {
      cleanup();
      return;
    }
    while (!g_stop.load() && nasdaq::recv_soup(client, packet_type, payload)) {
      if (packet_type == 'R') { nasdaq::send_soup(client, 'H', nullptr, 0); continue; }
      if (packet_type != 'U') continue;
      nasdaq::EnterOrder order;
      std::string error;
      if (!nasdaq::decode_enter(payload.data(), payload.size(), order, error)) continue;
      const auto responses = process_order(order);
      for (const auto &response : responses) {
        if (!nasdaq::send_soup(client, 'S', response)) break;
        ++soup_sequence_;
      }
      nasdaq::OuchResponse result;
      if (!responses.empty() && nasdaq::decode_response(responses.back().data(),
                                                        responses.back().size(), result, error)) {
        const bool formal_measurement =
            order.clordid.size() == 14 && order.clordid.front() == 'M';
        if (!formal_measurement) {
          std::ostringstream fields;
          fields << "{\"user_ref\":" << order.user_ref << ",\"clordid\":\""
                 << order.clordid << "\",\"symbol\":\"" << order.symbol
                 << "\",\"side\":\"" << nasdaq::side_name(order.side)
                 << "\",\"quantity\":" << order.quantity
                 << ",\"result\":\"" << (result.type == 'E' ? "EXECUTED" : "REJECTED")
                 << "\",\"paper_execution\":true,\"historical_market\":true}";
          events_.emit(result.type == 'E' ? "order_executed" : "order_rejected",
                       fields.str());
        }
      }
    }
    cleanup();
  }

  void order_server() {
    const int listener = flle::tcp_listener(config_.data_ip, config_.order_port);
    while (!g_stop.load()) {
      pollfd descriptor{listener, POLLIN, 0};
      if (::poll(&descriptor, 1, 200) <= 0) continue;
      const int client = ::accept(listener, nullptr, nullptr);
      if (client >= 0) {
        int one = 1;
        if (::setsockopt(client, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one)) < 0) {
          ::close(client);
          continue;
        }
        client_threads_.emplace_back([this, client] { client_loop(client); });
      }
    }
    ::close(listener);
  }

  void shutdown_clients() {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    for (const int client : clients_) ::shutdown(client, SHUT_RDWR);
  }

  std::string state_json() {
    std::lock_guard<std::mutex> lock(state_mutex_);
    if (paused_ && pause_deadline_ &&
        std::chrono::steady_clock::now() >= *pause_deadline_) {
      paused_ = false;
      pause_deadline_.reset();
      pause_lease_ms_ = 0;
      ++timing_epoch_;
      replay_condition_.notify_all();
    }
    const auto pause_lease_remaining_ms =
        paused_ && pause_deadline_
            ? std::max<std::int64_t>(
                  0, std::chrono::duration_cast<std::chrono::milliseconds>(
                         *pause_deadline_ - std::chrono::steady_clock::now())
                         .count())
            : 0;
    const auto progress = source_timestamp_ns_ <= config_.first_source_timestamp_ns
                              ? 0.0
                              : std::min(1.0, static_cast<double>(
                                    source_timestamp_ns_ - config_.first_source_timestamp_ns) /
                                    static_cast<double>(config_.last_source_timestamp_ns -
                                                        config_.first_source_timestamp_ns));
    const auto remaining_source_ns = source_timestamp_ns_ < config_.last_source_timestamp_ns
                                         ? config_.last_source_timestamp_ns - source_timestamp_ns_
                                         : 0;
    std::ostringstream out;
    out << "{\"status\":\"ONLINE\",\"protocol\":\"ITCH_5.0_OVER_MOLDUDP64\""
        << ",\"order_protocol\":\"OUCH_5.0_OVER_SOUPBINTCP\""
        << ",\"source\":\"NASDAQ_PUBLIC_ITCH_SAMPLE\",\"historical_market\":true"
        << ",\"paper_execution\":true,\"market_date\":\"" << config_.market_date
        << "\",\"market_mode\":\"" << config_.market_mode << "\",\"session\":\""
        << session_ << "\",\"replay_status\":\""
        << (paused_ ? "PAUSED" : (loop_complete_ ? "COMPLETE" : "PLAYING"))
        << "\",\"replay_pause_lease_ms\":" << pause_lease_ms_
        << ",\"replay_pause_lease_remaining_ms\":" << pause_lease_remaining_ms
        << ",\"replay_speed\":" << config_.replay_speed << ",\"replay_loop\":"
        << loop_ << ",\"source_timestamp_ns\":" << source_timestamp_ns_
        << ",\"source_clock\":\"" << source_clock(source_timestamp_ns_)
        << "\",\"first_source_timestamp_ns\":" << config_.first_source_timestamp_ns
        << ",\"last_source_timestamp_ns\":" << config_.last_source_timestamp_ns
        << ",\"first_source_clock\":\"" << source_clock(config_.first_source_timestamp_ns)
        << "\",\"last_source_clock\":\"" << source_clock(config_.last_source_timestamp_ns)
        << "\",\"replay_window\":\"REGULAR_SESSION\""
        << ",\"paper_ledger_entries\":" << ledger_.size()
        << ",\"paper_ledger\":[";
    bool first_ledger = true;
    const auto emit_recent = [&](const std::vector<std::uint32_t> &order_ids) {
      const auto begin = order_ids.size() > 40 ? order_ids.size() - 40 : 0;
      for (std::size_t index = begin; index < order_ids.size(); ++index) {
        const auto found = ledger_.find(order_ids[index]);
        if (found == ledger_.end() || found->second.responses.empty()) continue;
        nasdaq::OuchResponse result;
        std::string error;
        if (!nasdaq::decode_response(found->second.responses.back().data(),
                                     found->second.responses.back().size(), result, error))
          continue;
        if (!first_ledger) out << ',';
        first_ledger = false;
        const auto &order = found->second.order;
        out << "{\"client_order_id\":" << order.user_ref << ",\"clordid\":\""
            << order.clordid << "\",\"client_role\":\""
            << (order.clordid.rfind("AUTO", 0) == 0 ? "AUTO" : "MANUAL")
            << "\",\"symbol\":\"" << order.symbol << "\",\"side\":\""
            << nasdaq::side_name(order.side) << "\",\"quantity\":" << order.quantity
            << ",\"limit_price_x10000\":" << order.price_x10000
            << ",\"result\":\"" << (result.type == 'E' ? "ORDER_EXECUTED" : "ORDER_REJECTED")
            << "\",\"filled_quantity\":" << (result.type == 'E' ? result.quantity : 0)
            << ",\"fill_price_x10000\":" << result.price_x10000 << '}';
      }
    };
    emit_recent(auto_ledger_order_);
    emit_recent(manual_ledger_order_);
    out << ']'
        << ",\"replay_progress\":" << progress
        << ",\"remaining_source_ns\":" << remaining_source_ns
        << ",\"estimated_remaining_wall_ns\":"
        << static_cast<std::uint64_t>(remaining_source_ns / config_.replay_speed)
        << ",\"market_sequence\":"
        << mold_sequence_ - 1 << ",\"replay_messages\":" << replay_messages_ << '}';
    return out.str();
  }

  std::string command(const std::string &line) {
    const auto parts = flle::split(line, '|');
    if (parts.size() == 1 && parts[0] == "STATE") return state_json();
    std::lock_guard<std::mutex> lock(state_mutex_);
    if (parts.size() == 2 && parts[0] == "MARKET" &&
        (parts[1] == "MULTICAST" || parts[1] == "UNICAST" || parts[1] == "DUAL")) {
      config_.market_mode = parts[1];
    } else if (parts.size() == 2 && parts[0] == "REPLAY" && parts[1] == "PAUSE") {
      paused_ = true;
      pause_deadline_.reset();
      pause_lease_ms_ = 0;
      replay_condition_.notify_all();
    } else if (parts.size() == 3 && parts[0] == "REPLAY" &&
               parts[1] == "PAUSE_LEASE_MS") {
      std::uint64_t lease_ms{};
      try {
        std::size_t consumed{};
        lease_ms = std::stoull(parts[2], &consumed);
        if (consumed != parts[2].size())
          return "{\"error\":\"pause lease must be an integer\"}";
      } catch (const std::exception &) {
        return "{\"error\":\"pause lease must be an integer\"}";
      }
      if (lease_ms < 1000 || lease_ms > 900000)
        return "{\"error\":\"pause lease must be 1000..900000 ms\"}";
      paused_ = true;
      pause_lease_ms_ = lease_ms;
      pause_deadline_ = std::chrono::steady_clock::now() +
                        std::chrono::milliseconds(lease_ms);
      replay_condition_.notify_all();
    } else if (parts.size() == 2 && parts[0] == "REPLAY" && parts[1] == "RESUME") {
      paused_ = false;
      pause_deadline_.reset();
      pause_lease_ms_ = 0;
      ++timing_epoch_;
      replay_condition_.notify_all();
    } else if (parts.size() == 2 && parts[0] == "REPLAY" && parts[1] == "RESTART") {
      restart_requested_ = true;
      paused_ = false;
      pause_deadline_.reset();
      pause_lease_ms_ = 0;
      replay_condition_.notify_all();
    } else if (parts.size() == 3 && parts[0] == "REPLAY" && parts[1] == "SPEED") {
      const auto speed = std::stod(parts[2]);
      if (speed < 0.05 || speed > 100.0) return "{\"error\":\"speed must be 0.05..100\"}";
      config_.replay_speed = speed;
      ++timing_epoch_;
      replay_condition_.notify_all();
    } else {
      return "{\"error\":\"invalid command\"}";
    }
    return "{\"ok\":true}";
  }

  void management_server() {
    const int listener = flle::tcp_listener(config_.management_ip, config_.management_port);
    while (!g_stop.load()) {
      pollfd descriptor{listener, POLLIN, 0};
      if (::poll(&descriptor, 1, 200) <= 0) continue;
      const int client = ::accept(listener, nullptr, nullptr);
      if (client < 0) continue;
      std::array<char, 1024> buffer{};
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

void signal_handler(int) {
  g_stop.store(true);
}

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);
  try {
    Exchange(parse_config(argc, argv)).run();
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "flle-exchange: " << error.what() << '\n';
    return 1;
  }
}
