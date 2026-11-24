#include "common.hpp"
#include "nasdaq_protocol.hpp"
#include "order_queue.hpp"

#include <ff_api.h>
#include <ff_event.h>
#include <rte_ethdev.h>

#include <arpa/inet.h>
#include <poll.h>
#include <pthread.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>

#include <atomic>
#include <condition_variable>
#include <csignal>
#include <cstdlib>
#include <deque>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>

namespace {

namespace nasdaq = flle::nasdaq;
std::atomic<bool> g_stop{false};

std::string env_text(const char *name, const char *fallback) {
  const char *value = std::getenv(name);
  return value && *value ? value : fallback;
}

std::uint16_t env_port(const char *name, std::uint16_t fallback) {
  const char *value = std::getenv(name);
  return value && *value ? static_cast<std::uint16_t>(std::stoul(value))
                         : fallback;
}

int env_int(const char *name, int fallback) {
  const char *value = std::getenv(name);
  return value && *value ? std::stoi(value) : fallback;
}

std::uint64_t required_env_u64(const char *name) {
  const char *value = std::getenv(name);
  if (!value || !*value)
    throw std::runtime_error(std::string("missing required environment ") +
                             name);
  const std::string text(value);
  for (const char character : text)
    if (character < '0' || character > '9')
      throw std::runtime_error(std::string("invalid unsigned environment ") +
                               name + '=' + text);
  try {
    std::size_t parsed{};
    const auto result = std::stoull(text, &parsed, 10);
    if (parsed != text.size()) throw std::invalid_argument("trailing bytes");
    return result;
  } catch (const std::exception &) {
    throw std::runtime_error(std::string("invalid unsigned environment ") +
                             name + '=' + text);
  }
}

struct Config {
  std::string data_ip{env_text("FLLE_DPDK_DATA_IP", "20.1.1.2")};
  std::string exchange_ip{env_text("FLLE_EXCHANGE_DATA_IP", "20.1.1.1")};
  std::string management_ip{env_text("FLLE_MANAGEMENT_IP", "10.1.1.2")};
  std::string telemetry_host{env_text("FLLE_TELEMETRY_HOST", "10.1.1.101")};
  std::uint16_t order_port{env_port("FLLE_ORDER_PORT", 43120)};
  std::uint16_t management_port{env_port("FLLE_MANAGEMENT_PORT", 48125)};
  std::uint16_t telemetry_port{env_port("FLLE_TELEMETRY_PORT", 46120)};
  int helper_cpu{env_int("FLLE_DPDK_HELPER_CPU", 3)};
  bool heartbeat_enabled{env_int("FLLE_DPDK_HEARTBEAT", 0) == 1};
  std::uint64_t user_ref_base{
      required_env_u64("FLLE_DPDK_USER_REF_BASE")};
  std::uint64_t user_ref_span{
      required_env_u64("FLLE_DPDK_USER_REF_SPAN")};
};

struct WorkOrder {
  nasdaq::EnterOrder order;
  std::uint64_t queued_ns{};
  std::string origin{"MANUAL_GUI"};
  bool measurement{};
  std::uint64_t measurement_generation{};
  std::uint64_t send_ns{};
};

class DpdkTrader {
 public:
  explicit DpdkTrader(Config config)
      : config_(std::move(config)),
        events_("trader_dpdk", config_.telemetry_host, config_.telemetry_port),
        queue_(flle::OrderQueueMode::DequeCv) {
    constexpr auto kUserRefLimit =
        static_cast<std::uint64_t>(
            std::numeric_limits<std::uint32_t>::max()) +
        1;
    if (config_.user_ref_base == 0 ||
        config_.user_ref_base >= kUserRefLimit ||
        config_.user_ref_span == 0 ||
        config_.user_ref_span > kUserRefLimit - config_.user_ref_base)
      throw std::runtime_error("invalid DPDK user_ref base/span contract");
    positions_["AAPL"] = 0;
    positions_["NVDA"] = 0;
    pending_["AAPL"] = 0;
    pending_["NVDA"] = 0;
    next_user_ref_.store(config_.user_ref_base);
  }

  int run(int argc, char **argv) {
    if (ff_init(argc, argv) != 0) throw std::runtime_error("ff_init failed");
    initialize_order_session();

    bridge_thread_ = std::thread([this] {
      pthread_setname_np(pthread_self(), "flle-bridge");
      flle::pin_current_thread(config_.helper_cpu);
      bridge_loop();
    });
    management_thread_ = std::thread([this] {
      try {
        pthread_setname_np(pthread_self(), "flle-mgmt");
        flle::pin_current_thread(config_.helper_cpu);
        management_loop();
      } catch (const std::exception &error) {
        failed_.store(true);
        g_stop.store(true);
        events_.emit("component_stop",
                     "{\"status\":\"FAILED\",\"stage\":\"MANAGEMENT\","
                     "\"reason\":\"" +
                         std::string(error.what()) + "\"}");
      }
    });
    ff_run(&DpdkTrader::drive_entry, this);

    g_stop.store(true);
    queue_.wake();
    mailbox_condition_.notify_all();
    if (management_thread_.joinable()) management_thread_.join();
    if (bridge_thread_.joinable()) bridge_thread_.join();
    events_.emit("component_stop", "{\"status\":\"OFFLINE\"}");
    return failed_.load() ? 1 : 0;
  }

 private:
  enum class SessionState { Connecting, LoginPending, Online, Failed };

  Config config_;
  flle::EventEmitter events_;
  flle::OrderQueue<WorkOrder, 1024> queue_;
  std::thread management_thread_;
  std::thread bridge_thread_;
  std::mutex state_mutex_;
  std::mutex submission_mutex_;
  std::mutex mailbox_mutex_;
  std::condition_variable mailbox_condition_;
  std::optional<WorkOrder> mailbox_;
  std::optional<WorkOrder> active_;
  std::map<std::string, std::int64_t> positions_;
  std::map<std::string, std::int64_t> pending_;
  std::deque<std::uint64_t> latency_samples_;
  std::deque<std::uint64_t> measurement_samples_;
  std::deque<std::uint64_t> measurement_queue_samples_;
  std::deque<std::uint64_t> measurement_total_samples_;
  std::deque<std::uint32_t> measurement_refs_;
  std::deque<char> measurement_results_;
  std::deque<std::uint32_t> sample_refs_;
  std::deque<char> sample_results_;
  std::atomic<std::uint64_t> next_user_ref_{0};
  std::atomic<std::uint64_t> measurement_generation_{0};
  std::atomic<std::uint64_t> measurement_ready_samples_{0};
  std::atomic<std::uint64_t> orders_{0};
  std::atomic<std::uint64_t> fills_{0};
  std::atomic<std::uint64_t> rejects_{0};
  std::atomic<std::uint64_t> queue_drops_{0};
  std::atomic<bool> failed_{false};
  std::atomic<bool> session_online_{false};
  std::atomic<int> order_cpu_{-1};
  std::atomic<int> reactor_tid_{-1};
  std::atomic<int> bridge_tid_{-1};
  std::atomic<int> bridge_cpu_{-1};
  std::atomic<int> management_tid_{-1};
  std::atomic<int> management_cpu_{-1};
  std::string session_;
  bool tcp_nodelay_{false};
  int tcp_nodelay_value_{0};
  int order_fd_{-1};
  int kqueue_fd_{-1};
  SessionState session_state_{SessionState::Connecting};
  bool reactor_shutdown_started_{false};
  bool peer_eof_{false};
  int shutdown_rc_{-1};
  std::chrono::steady_clock::time_point reactor_shutdown_deadline_{};
  std::vector<std::uint8_t> tx_buffer_;
  std::size_t tx_offset_{};
  std::vector<std::uint8_t> rx_buffer_;
  std::chrono::steady_clock::time_point next_heartbeat_{};

  static int drive_entry(void *opaque) {
    return static_cast<DpdkTrader *>(opaque)->drive();
  }

  static std::array<std::uint64_t, 3> percentiles(
      std::vector<std::uint64_t> samples) {
    if (samples.empty()) return {};
    std::sort(samples.begin(), samples.end());
    return {samples[(samples.size() - 1) / 2],
            samples[(samples.size() - 1) * 99 / 100], samples.back()};
  }

  static void keep_sample(std::deque<std::uint64_t> &samples,
                          std::uint64_t value) {
    samples.push_back(value);
    if (samples.size() > 20000) samples.pop_front();
  }

  static std::string clordid(std::uint32_t user_ref, bool measurement) {
    std::ostringstream out;
    out << (measurement ? "MDPK" : "DPDK") << std::setfill('0')
        << std::setw(10) << user_ref;
    return out.str();
  }

  std::optional<std::uint32_t> allocate_user_ref() {
    const auto end = config_.user_ref_base + config_.user_ref_span;
    return flle::allocate_bounded_user_ref(next_user_ref_, end);
  }

  void fail(std::string_view stage) {
    if (!failed_.exchange(true)) {
      events_.emit("component_stop",
                   "{\"status\":\"FAILED\",\"stage\":\"" +
                       std::string(stage) + "\"}");
    }
    session_state_ = SessionState::Failed;
    g_stop.store(true);
  }

  void initialize_order_session() {
    order_fd_ = ff_socket(AF_INET, SOCK_STREAM, 0);
    if (order_fd_ < 0) throw std::runtime_error("ff_socket failed");
    int one = 1;
    if (ff_setsockopt(order_fd_, IPPROTO_TCP, TCP_NODELAY, &one,
                      sizeof(one)) != 0)
      throw std::runtime_error("ff_setsockopt(TCP_NODELAY) failed");
    int observed = 0;
    socklen_t observed_length = sizeof(observed);
    const int nodelay_result =
        ff_getsockopt(order_fd_, IPPROTO_TCP, TCP_NODELAY, &observed,
                      &observed_length);
    if (nodelay_result != 0 || observed == 0)
      throw std::runtime_error(
          "ff_getsockopt(TCP_NODELAY) verification failed: result=" +
          std::to_string(nodelay_result) + " value=" +
          std::to_string(observed) + " errno=" + std::to_string(errno));
    tcp_nodelay_ = true;
    tcp_nodelay_value_ = observed;
    int nonblocking = 1;
    if (ff_ioctl(order_fd_, FIONBIO, &nonblocking) != 0)
      throw std::runtime_error("ff_ioctl(FIONBIO) failed");

    sockaddr_in remote{};
    remote.sin_family = AF_INET;
    remote.sin_port = htons(config_.order_port);
    if (::inet_pton(AF_INET, config_.exchange_ip.c_str(), &remote.sin_addr) != 1)
      throw std::runtime_error("invalid exchange data IP");
    const int result = ff_connect(order_fd_,
                                  reinterpret_cast<linux_sockaddr *>(&remote),
                                  sizeof(remote));
    if (result != 0 && errno != EINPROGRESS)
      throw std::runtime_error("ff_connect failed: " +
                               std::string(std::strerror(errno)));

    kqueue_fd_ = ff_kqueue();
    if (kqueue_fd_ < 0) throw std::runtime_error("ff_kqueue failed");
    struct kevent changes[2];
    EV_SET(&changes[0], order_fd_, EVFILT_READ,
           EV_ADD | EV_ENABLE | EV_CLEAR, 0, 0, nullptr);
    EV_SET(&changes[1], order_fd_, EVFILT_WRITE,
           EV_ADD | EV_ENABLE | EV_CLEAR, 0, 0, nullptr);
    if (ff_kevent(kqueue_fd_, changes, 2, nullptr, 0, nullptr) != 0)
      throw std::runtime_error("ff_kevent add failed");
    next_heartbeat_ = std::chrono::steady_clock::now();
  }

  void queue_soup(char packet_type, const std::uint8_t *payload,
                  std::size_t payload_size) {
    if (!tx_buffer_.empty()) throw std::runtime_error("overlapping Soup writes");
    tx_buffer_.resize(payload_size + 3);
    flle::put_u16(tx_buffer_.data(),
                  static_cast<std::uint16_t>(payload_size + 1));
    tx_buffer_[2] = static_cast<std::uint8_t>(packet_type);
    if (payload_size)
      std::memcpy(tx_buffer_.data() + 3, payload, payload_size);
    tx_offset_ = 0;
  }

  void connected() {
    const auto login = nasdaq::soup_login_request("FLLED1", "PAPER");
    queue_soup('L', login.data(), login.size());
    session_state_ = SessionState::LoginPending;
  }

  void flush_tx() {
    if (tx_buffer_.empty()) return;
    while (tx_offset_ < tx_buffer_.size()) {
      const auto sent = ff_send(order_fd_, tx_buffer_.data() + tx_offset_,
                                tx_buffer_.size() - tx_offset_, 0);
      if (sent > 0) {
        tx_offset_ += static_cast<std::size_t>(sent);
        continue;
      }
      if (sent < 0 && errno == EAGAIN) return;
      fail("SOUP_SEND");
      return;
    }
    tx_buffer_.clear();
    tx_offset_ = 0;
  }

  void drain_rx() {
    std::array<std::uint8_t, 4096> chunk{};
    while (true) {
      const auto received = ff_recv(order_fd_, chunk.data(), chunk.size(), 0);
      if (received > 0) {
        rx_buffer_.insert(rx_buffer_.end(), chunk.begin(),
                          chunk.begin() + received);
        continue;
      }
      if (received == 0) {
        if (reactor_shutdown_started_) {
          peer_eof_ = true;
          session_online_.store(false);
        } else {
          fail("SOUP_EOF");
        }
      } else if (errno != EAGAIN) {
        fail("SOUP_RECV");
      }
      break;
    }
    while (rx_buffer_.size() >= 3) {
      const auto body_size = flle::get_u16(rx_buffer_.data());
      if (body_size < 1) {
        fail("SOUP_BAD_LENGTH");
        return;
      }
      const auto frame_size = static_cast<std::size_t>(body_size) + 2;
      if (rx_buffer_.size() < frame_size) break;
      const char type = static_cast<char>(rx_buffer_[2]);
      process_soup(type, rx_buffer_.data() + 3, body_size - 1);
      rx_buffer_.erase(rx_buffer_.begin(), rx_buffer_.begin() + frame_size);
      if (g_stop.load() && !reactor_shutdown_started_) return;
    }
  }

  void process_soup(char type, const std::uint8_t *payload,
                    std::size_t payload_size) {
    if (type == 'A' && session_state_ == SessionState::LoginPending &&
        payload_size == nasdaq::kSoupLoginAcceptedBytes) {
      {
        std::lock_guard<std::mutex> lock(state_mutex_);
        session_ = flle::get_ascii(payload, 10);
      }
      session_state_ = SessionState::Online;
      session_online_.store(true);
      events_.emit(
          "component_start",
          "{\"status\":\"ONLINE\",\"role\":\"MANUAL\","
          "\"order_protocol\":\"OUCH_5.0_OVER_SOUPBINTCP\","
          "\"order_transport\":\"DPDK_FSTACK\","
          "\"order_queue\":\"DEQUE_CV\"}");
      events_.emit("order_session",
                   "{\"status\":\"LOGIN_ACCEPTED\","
                   "\"protocol\":\"SoupBinTCP\","
                   "\"order_transport\":\"DPDK_FSTACK\"}");
      return;
    }
    if (type != 'S' || !active_) return;
    nasdaq::OuchResponse response;
    std::string error;
    if (!nasdaq::decode_response(payload, payload_size, response, error) ||
        response.user_ref != active_->order.user_ref) {
      fail("OUCH_DECODE");
      return;
    }
    if (response.type == 'A') {
      // Match trader.cpp: keep synchronous UI telemetry outside the formal
      // order-session measurement window.
      if (!active_->measurement)
        events_.emit("order_accepted",
                     "{\"client_order_id\":" +
                         std::to_string(response.user_ref) +
                         ",\"user_ref\":" +
                         std::to_string(response.user_ref) +
                         ",\"order_reference\":" +
                         std::to_string(response.order_reference) + "}");
      return;
    }
    if (response.type == 'E' || response.type == 'J') complete(response);
  }

  void complete(const nasdaq::OuchResponse &response) {
    WorkOrder work = *active_;
    const auto completed_ns = flle::monotonic_ns();
    const auto order_rtt_ns = completed_ns - work.send_ns;
    const auto queue_to_send_ns = work.send_ns - work.queued_ns;
    const auto submit_to_final_ns = completed_ns - work.queued_ns;
    const auto delta = work.order.side == nasdaq::Side::Buy
                           ? static_cast<std::int64_t>(work.order.quantity)
                           : -static_cast<std::int64_t>(work.order.quantity);
    std::int64_t position{};
    {
      std::lock_guard<std::mutex> lock(state_mutex_);
      pending_[work.order.symbol] -= delta;
      if (response.type == 'E') {
        positions_[work.order.symbol] += delta;
        ++fills_;
      } else {
        ++rejects_;
      }
      position = positions_[work.order.symbol];
      keep_sample(latency_samples_, order_rtt_ns);
      sample_refs_.push_back(work.order.user_ref);
      sample_results_.push_back(response.type);
      if (sample_refs_.size() > 20000) {
        sample_refs_.pop_front();
        sample_results_.pop_front();
      }
      if (work.measurement &&
          work.measurement_generation == measurement_generation_.load()) {
        keep_sample(measurement_samples_, order_rtt_ns);
        keep_sample(measurement_queue_samples_, queue_to_send_ns);
        keep_sample(measurement_total_samples_, submit_to_final_ns);
        measurement_refs_.push_back(work.order.user_ref);
        measurement_results_.push_back(response.type);
        if (measurement_refs_.size() > 20000) {
          measurement_refs_.pop_front();
          measurement_results_.pop_front();
        }
      }
    }

    if (!work.measurement) {
      std::ostringstream fields;
      fields << "{\"client_order_id\":" << work.order.user_ref
           << ",\"user_ref\":" << work.order.user_ref
           << ",\"clordid\":\"" << work.order.clordid
           << "\",\"origin\":\"" << work.origin
           << "\",\"order_transport\":\"DPDK_FSTACK\""
           << ",\"symbol\":\"" << work.order.symbol
           << "\",\"side\":\"" << nasdaq::side_name(work.order.side)
           << "\",\"quantity\":" << work.order.quantity
           << ",\"filled_quantity\":"
           << (response.type == 'E' ? response.quantity : 0)
           << ",\"position_delta\":"
           << (response.type == 'E' ? delta : 0)
           << ",\"fill_price_x10000\":" << response.price_x10000
           << ",\"exchange_source_timestamp_ns\":" << response.timestamp_ns
           << ",\"result\":\""
           << (response.type == 'E' ? "ORDER_EXECUTED" : "ORDER_REJECTED")
           << "\",\"reject_reason\":\"" << response.reason
           << "\",\"order_rtt_ns\":" << order_rtt_ns
           << ",\"queue_to_send_ns\":" << queue_to_send_ns
           << ",\"submit_to_final_ns\":" << submit_to_final_ns
           << ",\"order_queue\":\"DEQUE_CV\",\"position\":"
           << position << ",\"pnl_x10000\":0}";
      events_.emit("order_complete", fields.str());
    }
    active_.reset();
    mailbox_condition_.notify_one();
    if (work.measurement &&
        work.measurement_generation == measurement_generation_.load())
      ++measurement_ready_samples_;
  }

  void maybe_start_order() {
    if (session_state_ != SessionState::Online || active_ ||
        !tx_buffer_.empty())
      return;
    std::optional<WorkOrder> work;
    {
      std::lock_guard<std::mutex> lock(mailbox_mutex_);
      if (mailbox_) {
        work = std::move(mailbox_);
        mailbox_.reset();
      }
    }
    if (!work) return;
    mailbox_condition_.notify_one();
    active_ = std::move(work);
    const auto encoded = nasdaq::encode_enter(active_->order);
    // Match trader.cpp: OUCH is encoded, but Soup framing and Transport work
    // have not started when the send-to-final clock begins.
    active_->send_ns = flle::monotonic_ns();
    order_cpu_.store(::sched_getcpu());
    queue_soup('U', encoded.data(), encoded.size());
  }

  [[noreturn]] void finish_reactor_shutdown(
      int status, std::string_view reason = {}) {
    std::ostringstream receipt;
    receipt
        << "cleanup_mode=PROCESS_EXIT_BYPASS_INCOMPLETE_FSTACK_CLEANUP"
        << " shutdown_rc=" << shutdown_rc_
        << " peer_eof=" << (peer_eof_ ? 1 : 0);
    if (!reason.empty()) receipt << " error=" << reason;
    receipt << '\n';

    // The fixed F-Stack build has no complete FreeBSD/DPDK teardown.  Flush
    // normal diagnostics, then use one direct write for the machine receipt
    // before the process boundary lets the kernel reclaim all stack state.
    std::cout.flush();
    std::cerr.flush();
    const auto text = receipt.str();
    std::size_t written = 0;
    while (written < text.size()) {
      const auto result =
          ::write(STDERR_FILENO, text.data() + written, text.size() - written);
      if (result > 0) {
        written += static_cast<std::size_t>(result);
        continue;
      }
      if (result < 0 && errno == EINTR) continue;
      break;
    }
    const bool persisted =
        written == text.size() && ::fsync(STDERR_FILENO) == 0;
    std::_Exit(persisted ? status : 1);
  }

  void begin_reactor_shutdown() {
    // A process-boundary exit is safe only after the one live TCP session has
    // no application work left and its peer has acknowledged the half-close.
    // Do not enter ff_run()'s post-loop cleanup: this fixed F-Stack version
    // explicitly documents that global cleanup as incomplete.
    reactor_shutdown_started_ = true;
    session_online_.store(false);

    {
      // Close the submit/check race: once this lock is held, no management
      // request can pass its stop check and enqueue work behind our audit.
      std::lock_guard<std::mutex> submission_lock(submission_mutex_);
      bool mailbox_busy = false;
      {
        std::lock_guard<std::mutex> lock(mailbox_mutex_);
        mailbox_busy = mailbox_.has_value();
      }
      if (failed_.load() || active_.has_value() || mailbox_busy ||
          !tx_buffer_.empty() || queue_.depth() != 0) {
        finish_reactor_shutdown(1, "INFLIGHT_OR_FAILED");
      }
      if (order_fd_ < 0 || kqueue_fd_ < 0) {
        finish_reactor_shutdown(1, "INVALID_FSTACK_DESCRIPTOR");
      }

      shutdown_rc_ = ff_shutdown(order_fd_, SHUT_WR);
      if (shutdown_rc_ != 0) {
        finish_reactor_shutdown(1, "FF_SHUTDOWN_FAILED");
      }
    }
    reactor_shutdown_deadline_ =
        std::chrono::steady_clock::now() + std::chrono::seconds(2);
  }

  int drive() {
    if (reactor_tid_.load() < 0) {
      reactor_tid_.store(static_cast<int>(::syscall(SYS_gettid)));
      order_cpu_.store(::sched_getcpu());
    }
    if (g_stop.load()) {
      if (!reactor_shutdown_started_) begin_reactor_shutdown();
    }
    struct kevent events[4];
    const struct timespec no_wait{0, 0};
    const int count =
        ff_kevent(kqueue_fd_, nullptr, 0, events, 4, &no_wait);
    if (count < 0) {
      if (reactor_shutdown_started_ && errno == EINTR) return 0;
      if (reactor_shutdown_started_)
        finish_reactor_shutdown(1, "KQUEUE_POLL_FAILED");
      fail("KQUEUE");
      return 0;
    }
    if (reactor_shutdown_started_) {
      for (int index = 0; index < count; ++index) {
        if (events[index].flags & EV_ERROR)
          finish_reactor_shutdown(1, "SOCKET_EVENT_FAILED");
        if (events[index].filter == EVFILT_READ ||
            (events[index].flags & EV_EOF))
          drain_rx();
      }
      if (peer_eof_) {
        if (!rx_buffer_.empty())
          finish_reactor_shutdown(1, "PARTIAL_SOUP_FRAME_AT_EOF");
        finish_reactor_shutdown(0);
      }
      if (std::chrono::steady_clock::now() >= reactor_shutdown_deadline_)
        finish_reactor_shutdown(1, "PEER_EOF_TIMEOUT");
      return 0;
    }
    for (int index = 0; index < count; ++index) {
      if (events[index].flags & EV_ERROR) {
        fail("SOCKET_EVENT");
        return 0;
      }
      if (events[index].filter == EVFILT_WRITE &&
          session_state_ == SessionState::Connecting) {
        int error = 0;
        socklen_t length = sizeof(error);
        if (ff_getsockopt(order_fd_, SOL_SOCKET, SO_ERROR, &error, &length) ||
            error) {
          fail("CONNECT");
          return 0;
        }
        connected();
      }
      if (events[index].filter == EVFILT_READ) drain_rx();
    }
    if (session_state_ != SessionState::Connecting) drain_rx();
    maybe_start_order();
    flush_tx();
    return 0;
  }

  void bridge_loop() {
    bridge_tid_.store(static_cast<int>(::syscall(SYS_gettid)));
    bridge_cpu_.store(::sched_getcpu());
    while (!g_stop.load()) {
      WorkOrder work;
      if (!queue_.front(work, g_stop)) continue;
      std::unique_lock<std::mutex> lock(mailbox_mutex_);
      mailbox_condition_.wait_for(lock, std::chrono::milliseconds(20), [this] {
        return g_stop.load() || !mailbox_.has_value();
      });
      if (g_stop.load()) break;
      if (mailbox_) continue;
      mailbox_ = std::move(work);
      queue_.pop();
    }
  }

  std::uint32_t queue_order(const std::string &symbol, nasdaq::Side side,
                            std::uint32_t quantity, std::uint64_t price,
                            bool measurement) {
    const auto allocated_user_ref = allocate_user_ref();
    if (!allocated_user_ref) return 0;
    const auto user_ref = *allocated_user_ref;
    nasdaq::EnterOrder order{user_ref, side, quantity, symbol, price, '3', 'Y',
                             'A', 'N', 'N', clordid(user_ref, measurement)};
    const auto delta = side == nasdaq::Side::Buy
                           ? static_cast<std::int64_t>(quantity)
                           : -static_cast<std::int64_t>(quantity);
    {
      std::lock_guard<std::mutex> lock(state_mutex_);
      const auto exposure = positions_[symbol] + pending_[symbol];
      if (std::abs(exposure + delta) > 200 &&
          std::abs(exposure + delta) >= std::abs(exposure))
        return 0;
      pending_[symbol] += delta;
    }
    const auto queued_ns = flle::monotonic_ns();
    if (!queue_.push(WorkOrder{order, queued_ns, "MANUAL_GUI", measurement,
                               measurement_generation_.load(), 0})) {
      std::lock_guard<std::mutex> lock(state_mutex_);
      pending_[symbol] -= delta;
      ++queue_drops_;
      return 0;
    }
    ++orders_;
    if (!measurement) {
      std::ostringstream fields;
      fields << "{\"client_order_id\":" << user_ref
           << ",\"user_ref\":" << user_ref
           << ",\"clordid\":\"" << order.clordid
           << "\",\"origin\":\"MANUAL_GUI\","
           << "\"order_transport\":\"DPDK_FSTACK\",\"symbol\":\""
           << symbol << "\",\"side\":\"" << nasdaq::side_name(side)
           << "\",\"quantity\":" << quantity
           << ",\"limit_price_x10000\":" << price
           << ",\"paper_epoch\":1}";
      events_.emit("order_queued", fields.str());
    }
    return user_ref;
  }

  std::string state_json() {
    std::vector<std::uint64_t> latency;
    std::vector<std::uint64_t> measurement;
    std::vector<std::uint64_t> queue_latency;
    std::vector<std::uint64_t> total_latency;
    std::int64_t aapl{};
    std::int64_t nvda{};
    std::size_t latency_count{};
    std::size_t measurement_count{};
    std::string session;
    {
      std::lock_guard<std::mutex> lock(state_mutex_);
      latency.assign(latency_samples_.begin(), latency_samples_.end());
      measurement.assign(measurement_samples_.begin(),
                         measurement_samples_.end());
      queue_latency.assign(measurement_queue_samples_.begin(),
                           measurement_queue_samples_.end());
      total_latency.assign(measurement_total_samples_.begin(),
                           measurement_total_samples_.end());
      aapl = positions_["AAPL"];
      nvda = positions_["NVDA"];
      latency_count = latency_samples_.size();
      measurement_count = measurement_samples_.size();
      session = session_;
    }
    const auto latency_values = percentiles(std::move(latency));
    const auto measurement_values = percentiles(std::move(measurement));
    const auto queue_values = percentiles(std::move(queue_latency));
    const auto total_values = percentiles(std::move(total_latency));
    const auto reactor_tid = reactor_tid_.load();
    const auto bridge_tid = bridge_tid_.load();
    const auto management_tid = management_tid_.load();
    rte_eth_stats port_stats{};
    const int port_stats_rc = rte_eth_stats_get(0, &port_stats);
    if (port_stats_rc != 0)
      throw std::runtime_error(
          "rte_eth_stats_get(port=0) failed: rc=" +
          std::to_string(port_stats_rc));
    std::ostringstream out;
    out << "{\"status\":\""
        << (session_online_.load() ? "ONLINE" : "STARTING")
        << "\",\"role\":\"MANUAL\","
        << "\"market_protocol\":\"CENTRAL_GATEWAY_BOOK\","
        << "\"order_protocol\":\"OUCH_5.0_OVER_SOUPBINTCP\","
        << "\"order_transport\":\"DPDK_FSTACK\",\"tcp_nodelay\":"
        << (tcp_nodelay_ ? "true" : "false")
        << ",\"tcp_nodelay_value\":" << tcp_nodelay_value_
        << ",\"nagle_semantics\":\"FSTACK_GETSOCKOPT_VERIFIED\""
        << ",\"user_ref_base\":" << config_.user_ref_base
        << ",\"user_ref_span\":" << config_.user_ref_span
        << ",\"user_ref_end_exclusive\":"
        << config_.user_ref_base + config_.user_ref_span
        << ",\"user_ref_next\":" << next_user_ref_.load()
        << ",\"session\":\""
        << session << "\",\"paper_epoch\":1,"
        << "\"market_receiver_ready\":false,\"heartbeat_enabled\":"
        << (config_.heartbeat_enabled ? "true" : "false")
        << ",\"positions\":{\"AAPL\":"
        << aapl << ",\"NVDA\":" << nvda << "},\"pnl_x10000\":0,"
        << "\"stats\":{\"orders\":" << orders_.load()
        << ",\"fills\":" << fills_.load() << ",\"rejects\":"
        << rejects_.load() << ",\"transport_retries\":0},"
        << "\"dpdk_port_stats\":{\"port_id\":0,\"ipackets\":"
        << port_stats.ipackets << ",\"opackets\":" << port_stats.opackets
        << ",\"imissed\":" << port_stats.imissed << ",\"ierrors\":"
        << port_stats.ierrors << ",\"oerrors\":" << port_stats.oerrors
        << ",\"rx_nombuf\":" << port_stats.rx_nombuf << "},"
        << "\"latency\":{\"samples\":" << latency_count
        << ",\"p50_ns\":" << latency_values[0] << ",\"p99_ns\":"
        << latency_values[1] << ",\"max_ns\":" << latency_values[2]
        << "},\"measurement_latency\":{\"samples\":"
        << measurement_count << ",\"ready_samples\":"
        << measurement_ready_samples_.load() << ",\"p50_ns\":"
        << measurement_values[0] << ",\"p99_ns\":"
        << measurement_values[1] << ",\"max_ns\":"
        << measurement_values[2] << ",\"generation\":"
        << measurement_generation_.load() << "},"
        << "\"software_latency\":{\"samples\":"
        << measurement_count
        << ",\"queue_mode\":\"DEQUE_CV\",\"queue_locked\":true,"
        << "\"network_reactor\":\"FSTACK_POLL\",\"queue_capacity\":"
        << queue_.capacity() << ",\"queue_depth\":" << queue_.depth()
        << ",\"queue_full_drops\":" << queue_drops_.load()
        << ",\"order_thread_tid\":" << reactor_tid
        << ",\"order_thread_cpu\":"
        << order_cpu_.load()
        << ",\"order_thread_allowed_count\":"
        << flle::affinity_count(reactor_tid) << ",\"order_rx_cpu\":"
        << order_cpu_.load()
        << ",\"bridge_thread_tid\":" << bridge_tid
        << ",\"bridge_thread_cpu\":" << bridge_cpu_.load()
        << ",\"bridge_thread_allowed_count\":"
        << flle::affinity_count(bridge_tid)
        << ",\"management_thread_tid\":" << management_tid
        << ",\"management_thread_cpu\":" << management_cpu_.load()
        << ",\"management_thread_allowed_count\":"
        << flle::affinity_count(management_tid)
        << ",\"queue_to_send\":{\"p50_ns\":"
        << queue_values[0] << ",\"p99_ns\":" << queue_values[1]
        << ",\"max_ns\":" << queue_values[2]
        << "},\"submit_to_final\":{\"p50_ns\":" << total_values[0]
        << ",\"p99_ns\":" << total_values[1] << ",\"max_ns\":"
        << total_values[2] << "}},\"reaction_latency\":{\"samples\":0,"
        << "\"p50_ns\":0,\"p99_ns\":0,\"max_ns\":0}}";
    return out.str();
  }

  std::string samples_json(bool measurement_only) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    const auto count = measurement_only
                           ? std::min(
                                 measurement_samples_.size(),
                                 std::min(
                                     measurement_queue_samples_.size(),
                                     std::min(
                                         measurement_total_samples_.size(),
                                         std::min(measurement_refs_.size(),
                                                  measurement_results_.size()))))
                           : std::min(latency_samples_.size(),
                                      std::min(sample_refs_.size(),
                                               sample_results_.size()));
    std::ostringstream out;
    out << "{\"status\":\"ONLINE\",\"role\":\"MANUAL\","
        << "\"paper_epoch\":1,\"clock\":\"CLOCK_MONOTONIC\","
        << "\"measurement\":\"OUCH_SEND_TO_FINAL_RESPONSE\"";
    if (measurement_only)
      out << ",\"measurement_generation\":"
          << measurement_generation_.load();
    out << ",\"samples\":[";
    for (std::size_t index = 0; index < count; ++index) {
      if (index) out << ',';
      out << '{';
      out << "\"client_order_id\":"
          << (measurement_only ? measurement_refs_[index]
                               : sample_refs_[index])
          << ",\"result\":\""
          << (measurement_only ? measurement_results_[index]
                               : sample_results_[index])
          << "\",";
      if (measurement_only)
        out << "\"queue_to_send_ns\":"
            << measurement_queue_samples_[index] << ',';
      out << "\"order_rtt_ns\":"
          << (measurement_only ? measurement_samples_[index]
                               : latency_samples_[index]);
      if (measurement_only)
        out << ",\"submit_to_final_ns\":"
            << measurement_total_samples_[index];
      out << '}';
    }
    out << "]}";
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
    if (parts.size() == 1 && parts[0] == "SAMPLES")
      return samples_json(false);
    if (parts.size() == 1 && parts[0] == "MEASUREMENT_SAMPLES")
      return samples_json(true);
    if (parts.size() == 1 && parts[0] == "MEASUREMENT_RESET") {
      std::lock_guard<std::mutex> lock(state_mutex_);
      measurement_samples_.clear();
      measurement_queue_samples_.clear();
      measurement_total_samples_.clear();
      measurement_refs_.clear();
      measurement_results_.clear();
      measurement_ready_samples_ = 0;
      const auto generation = ++measurement_generation_;
      return "{\"ok\":true,\"measurement_generation\":" +
             std::to_string(generation) + ",\"paper_epoch\":1}";
    }
    if (parts.size() == 2 && parts[0] == "SOFTWARE_PROFILE")
      return "{\"error\":\"chapter 06 locks order_queue to DEQUE_CV\"}";
    if (parts.size() == 5 &&
        (parts[0] == "ORDER" || parts[0] == "MEASUREMENT_ORDER")) {
      std::lock_guard<std::mutex> submission_lock(submission_mutex_);
      if (g_stop.load())
        return "{\"error\":\"DPDK trader is stopping\"}";
      if (!session_online_.load())
        return "{\"error\":\"DPDK order session is not online\"}";
      if (parts[1] != "AAPL" && parts[1] != "NVDA")
        return "{\"error\":\"invalid symbol\"}";
      if (parts[2] != "BUY" && parts[2] != "SELL")
        return "{\"error\":\"invalid side\"}";
      const auto quantity = static_cast<std::uint32_t>(std::stoul(parts[3]));
      const auto price = std::stoull(parts[4]);
      if (!quantity || !price)
        return "{\"error\":\"quantity and resolved limit price are required\"}";
      const auto side =
          parts[2] == "BUY" ? nasdaq::Side::Buy : nasdaq::Side::Sell;
      const auto user_ref = queue_order(parts[1], side, quantity, price,
                                        parts[0] == "MEASUREMENT_ORDER");
      if (!user_ref)
        return "{\"error\":\"position limit, queue full, or user_ref range exhausted\"}";
      return "{\"ok\":true,\"client_order_id\":" +
             std::to_string(user_ref) + "}";
    }
    return "{\"error\":\"invalid command\"}";
  }

  void management_loop() {
    management_tid_.store(static_cast<int>(::syscall(SYS_gettid)));
    management_cpu_.store(::sched_getcpu());
    const int listener =
        flle::tcp_listener(config_.management_ip, config_.management_port);
    while (!g_stop.load()) {
      if (config_.heartbeat_enabled &&
          std::chrono::steady_clock::now() >= next_heartbeat_) {
        emit_heartbeat();
        next_heartbeat_ = std::chrono::steady_clock::now() +
                          std::chrono::seconds(1);
      }
      pollfd descriptor{listener, POLLIN, 0};
      if (::poll(&descriptor, 1, 200) <= 0) continue;
      const int client = ::accept(listener, nullptr, nullptr);
      if (client < 0) continue;
      std::array<char, 2048> buffer{};
      const auto received =
          ::recv(client, buffer.data(), buffer.size() - 1, 0);
      if (received > 0) {
        std::string line(buffer.data(), static_cast<std::size_t>(received));
        const auto last = line.find_last_not_of("\r\n");
        line.erase(last == std::string::npos ? 0 : last + 1);
        const auto response = command(line) + '\n';
        flle::send_all(client, response.data(), response.size());
      }
      ::close(client);
    }
    ::close(listener);
  }

  void emit_heartbeat() {
    events_.emit("component_heartbeat",
                 "{\"status\":\"" +
                     std::string(session_online_.load() ? "ONLINE" : "STARTING") +
                     "\",\"orders\":" + std::to_string(orders_.load()) +
                     ",\"fills\":" + std::to_string(fills_.load()) +
                     ",\"rejects\":" + std::to_string(rejects_.load()) +
                     ",\"order_queue\":\"DEQUE_CV\","
                     "\"order_transport\":\"DPDK_FSTACK\"}");
  }
};

void signal_handler(int) { g_stop.store(true); }

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);
  try {
    return DpdkTrader(Config{}).run(argc, argv);
  } catch (const std::exception &error) {
    std::cerr << "flle-trader-dpdk: " << error.what() << '\n';
    return 1;
  }
}
