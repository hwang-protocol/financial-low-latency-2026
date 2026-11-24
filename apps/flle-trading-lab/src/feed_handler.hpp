#pragma once

#include "common.hpp"
#include <map>

namespace flle {

struct Delivery {
  std::vector<std::uint8_t> message;
  std::string path;
  std::uint64_t receive_ns{};
  std::uint64_t sequence{};
};

class FeedHandler {
 public:
  explicit FeedHandler(std::size_t max_pending = 32768,
                       std::size_t max_bytes = 8 * 1024 * 1024,
                       std::uint64_t max_gap_ns = 5000000000ULL)
      : max_pending_(max_pending), max_bytes_(max_bytes), max_gap_ns_(max_gap_ns) {}

  std::vector<Delivery> accept(const std::string &session, std::uint64_t sequence,
                              std::vector<std::uint8_t> message, std::string path,
                              std::uint64_t receive_ns, std::string &classification) {
    const bool new_session = session_ != session;
    if (new_session) {
      session_ = session;
      // The book checkpoint is the start of the replay, not a snapshot at an
      // arbitrary reconnect sequence. Never call a partial replay complete.
      next_expected_ = 1;
      pending_.clear(); pending_bytes_ = 0;
      last_delivered_ = first_pending_ = highest_received_ = gap_started_ns_ = 0;
      discarded_ = 0; resync_reason_.clear(); delivered_in_session_ = false;
    }
    classification = new_session ? "NEW_SESSION" : "DELIVER";
    highest_received_ = std::max(highest_received_, sequence);
    if (sequence < next_expected_ || pending_.count(sequence)) {
      classification = "DUPLICATE"; return {};
    }
    if (resync_required()) {
      ++discarded_; classification = "RESYNC_REQUIRED"; return {};
    }
    if (sequence > next_expected_) {
      if (!gap_started_ns_) gap_started_ns_ = receive_ns;
      if (!first_pending_) first_pending_ = sequence;
      if (pending_.size() >= max_pending_ || pending_bytes_ + message.size() > max_bytes_ ||
          gap_age_ms(receive_ns) >= max_gap_ns_ / 1000000ULL) {
        require_resync("GAP_LIMIT", receive_ns);
        ++discarded_; classification = "RESYNC_REQUIRED"; return {};
      }
      pending_bytes_ += message.size();
      pending_.emplace(sequence, Delivery{std::move(message), std::move(path), receive_ns, sequence});
      first_pending_ = pending_.begin()->first;
      if (!new_session) classification = "GAP";
      return {};
    }
    std::vector<Delivery> delivered;
    Delivery current{std::move(message), std::move(path), receive_ns, sequence};
    while (true) {
      last_delivered_ = current.sequence; ++next_expected_;
      delivered.push_back(std::move(current));
      const auto found = pending_.find(next_expected_);
      if (found == pending_.end()) break;
      pending_bytes_ -= found->second.message.size();
      current = std::move(found->second); pending_.erase(found);
    }
    first_pending_ = pending_.empty() ? 0 : pending_.begin()->first;
    if (pending_.empty()) gap_started_ns_ = 0;
    delivered_in_session_ = true;
    return delivered;
  }

  void require_resync(const std::string &reason, std::uint64_t now_ns) {
    if (resync_reason_.empty()) resync_reason_ = reason;
    if (!gap_started_ns_) gap_started_ns_ = now_ns;
  }
  std::string session() const { return session_; }
  std::uint64_t next_expected() const { return next_expected_; }
  std::uint64_t last_delivered() const { return last_delivered_; }
  std::uint64_t first_pending() const { return first_pending_; }
  std::uint64_t highest_received() const { return highest_received_; }
  std::uint64_t gap_started_ns() const { return gap_started_ns_; }
  std::uint64_t gap_age_ms(std::uint64_t now_ns) const {
    return gap_started_ns_ && now_ns > gap_started_ns_ ? (now_ns - gap_started_ns_) / 1000000ULL : 0;
  }
  std::uint64_t gap_size() const {
    return first_pending_ > next_expected_ ? first_pending_ - next_expected_ : 0;
  }
  std::size_t pending() const { return pending_.size(); }
  std::size_t pending_bytes() const { return pending_bytes_; }
  std::uint64_t discarded() const { return discarded_; }
  bool resync_required() const { return !resync_reason_.empty(); }
  const std::string &resync_reason() const { return resync_reason_; }
  std::string diagnostics_json() const {
    std::ostringstream out;
    out << ",\"resync_required\":" << (resync_required() ? "true" : "false")
        << ",\"resync_reason\":\"" << resync_reason_ << "\""
        << ",\"pending_bytes\":" << pending_bytes_
        << ",\"pending_limit\":" << max_pending_
        << ",\"discarded_after_gap\":" << discarded_;
    return out.str();
  }
  bool delivered_in_session() const { return delivered_in_session_; }
  std::string integrity() const {
    if (resync_required() || pending() || gap_size()) return "GAP";
    if (!session_.empty() && !delivered_in_session_) return "RECOVERING";
    return "HEALTHY";
  }
  std::string trading_gate() const {
    if (integrity() == "GAP") return "INHIBITED_FEED_GAP";
    if (integrity() == "RECOVERING") return "INHIBITED_FEED_RECOVERING";
    return "OPEN";
  }

 private:
  std::string session_, resync_reason_;
  std::uint64_t next_expected_{}, last_delivered_{}, first_pending_{}, highest_received_{};
  std::uint64_t gap_started_ns_{}, discarded_{};
  bool delivered_in_session_{};
  std::map<std::uint64_t, Delivery> pending_;
  std::size_t pending_bytes_{};
  std::size_t max_pending_, max_bytes_;
  std::uint64_t max_gap_ns_;
};

}  // namespace flle
