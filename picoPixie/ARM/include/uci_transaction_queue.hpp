#pragma once
#include <cstddef>
#include <deque>
#include <string>
#include <utility>

namespace picoLichess {
// Preserve every complete UCI command in order while a search is executing.
// Memory is bounded: exceeding the queue limit fails closed, never drops a move.
class UciTransactionQueue {
public:
    static constexpr std::size_t MAX_QUEUED_COMMANDS = 32;
    bool push(std::string command) {
        if(commands_.size()>=MAX_QUEUED_COMMANDS) return false;
        commands_.push_back(std::move(command));
        return true;
    }
    bool pop(std::string& command) {
        if(commands_.empty()) return false;
        command=std::move(commands_.front());
        commands_.pop_front();
        return true;
    }
    bool empty() const { return commands_.empty(); }
    std::size_t size() const { return commands_.size(); }
    void clear() { std::deque<std::string>().swap(commands_); }
private:
    std::deque<std::string> commands_;
};
}
