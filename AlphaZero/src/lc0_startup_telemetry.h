#pragma once
// Akkad AlphaZero v0.2.8: mark LC0 initialization diagnostics without
// changing UCI protocol output. Intercepts C++ iostreams only.
#include <iostream>
#include <mutex>
#include <streambuf>
#include <string>

namespace az_lc0_telemetry {
inline bool is_backend_startup(const std::string& line) {
  return line.rfind("Loading weights file from:", 0) == 0 ||
         line.rfind("Using Eigen version", 0) == 0 ||
         line.rfind("Eigen max batch size is", 0) == 0;
}

class LineFilter final : public std::streambuf {
  std::streambuf* downstream_;
  std::streambuf* diagnostics_;
  std::mutex mutex_;
  std::string pending_;

  void emit_line(const std::string& line) {
    if (is_backend_startup(line)) {
      const std::string marked = "⚙️ " + line;
      diagnostics_->sputn(marked.data(), static_cast<std::streamsize>(marked.size()));
      diagnostics_->sputc('\n');
      diagnostics_->pubsync();
    } else {
      downstream_->sputn(line.data(), static_cast<std::streamsize>(line.size()));
      downstream_->sputc('\n');
    }
  }

  void append(const char* bytes, std::streamsize count) {
    std::lock_guard<std::mutex> lock(mutex_);
    for (std::streamsize i = 0; i < count; ++i) {
      const char c = bytes[i];
      if (c == '\n') {
        if (!pending_.empty() && pending_.back() == '\r') pending_.pop_back();
        emit_line(pending_);
        pending_.clear();
      } else {
        pending_ += c;
        // Avoid indefinitely retaining unusual, non-line-oriented output.
        if (pending_.size() > 65536) {
          downstream_->sputn(pending_.data(), static_cast<std::streamsize>(pending_.size()));
          pending_.clear();
        }
      }
    }
  }
 public:
  LineFilter(std::streambuf* destination, std::streambuf* diagnostic)
      : downstream_(destination), diagnostics_(diagnostic) {}
  ~LineFilter() override { flush_pending(); }

  void flush_pending() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!pending_.empty()) {
      downstream_->sputn(pending_.data(), static_cast<std::streamsize>(pending_.size()));
      pending_.clear();
    }
    downstream_->pubsync();
  }
 protected:
  int overflow(int ch) override {
    if (ch == traits_type::eof()) return traits_type::not_eof(ch);
    const char c = static_cast<char>(ch);
    append(&c, 1);
    return ch;
  }
  std::streamsize xsputn(const char* bytes, std::streamsize count) override {
    append(bytes, count);
    return count;
  }
  int sync() override {
    std::lock_guard<std::mutex> lock(mutex_);
    return downstream_->pubsync();
  }
};

class ScopedFilters final {
  std::streambuf* original_out_;
  std::streambuf* original_err_;
  LineFilter stdout_filter_;
  LineFilter stderr_filter_;
 public:
  ScopedFilters()
      : original_out_(std::cout.rdbuf()), original_err_(std::cerr.rdbuf()),
        stdout_filter_(original_out_, original_err_),
        stderr_filter_(original_err_, original_err_) {
    std::cout.rdbuf(&stdout_filter_);
    std::cerr.rdbuf(&stderr_filter_);
  }
  ~ScopedFilters() {
    std::cout.rdbuf(original_out_);
    std::cerr.rdbuf(original_err_);
    stdout_filter_.flush_pending();
    stderr_filter_.flush_pending();
  }
  ScopedFilters(const ScopedFilters&) = delete;
  ScopedFilters& operator=(const ScopedFilters&) = delete;
};
} // namespace az_lc0_telemetry
