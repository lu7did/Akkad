#pragma once
#include <cstdint>
#include <limits>

namespace picoLichess {
// Independent monotonic pacing state for each of the four compile-time slots.
// No HTTP body, FEN, move or prior evaluation is retained here.
class SlotTiming {
public:
    struct State {
        uint64_t last_request=0;
        uint64_t guard_until=0;
        bool has_request=false;
        bool guard_active=false;
    };
    static constexpr unsigned COUNT=4;
    bool guarded(unsigned slot,uint64_t now) const {
        return slot<COUNT && guarded(states_[slot],now);
    }
    uint64_t guard_remaining(unsigned slot,uint64_t now) const {
        return slot<COUNT?guard_remaining(states_[slot],now):0;
    }
    uint64_t eligible_at(unsigned slot,uint64_t now,int throttle) const {
        return slot<COUNT?eligible_at(states_[slot],now,throttle):now;
    }
    void start(unsigned slot,uint64_t now){if(slot<COUNT)start(states_[slot],now);}
    void fail(unsigned slot,uint64_t now,int timeguard){if(slot<COUNT)fail(states_[slot],now,timeguard);}
    void success(unsigned slot){if(slot<COUNT)success(states_[slot]);}
    static bool guarded(const State& state,uint64_t now){
        return state.guard_active && now<state.guard_until;
    }
    static uint64_t guard_remaining(const State& state,uint64_t now){
        return guarded(state,now)?state.guard_until-now:0;
    }
    static uint64_t eligible_at(const State& state,uint64_t now,int throttle){
        if(throttle<0||!state.has_request)return now;
        const auto since=now>=state.last_request?now-state.last_request:0;
        return since>=static_cast<uint64_t>(throttle)?now:
            saturating_add(state.last_request,static_cast<uint64_t>(throttle));
    }
    static void start(State& state,uint64_t now){
        state.last_request=now;state.has_request=true;
    }
    static void fail(State& state,uint64_t now,int timeguard){
        if(timeguard>=0){
            state.guard_until=saturating_add(now,static_cast<uint64_t>(timeguard));
            state.guard_active=true;
        }
    }
    static void success(State& state){state.guard_active=false;state.guard_until=0;}
private:
    static uint64_t saturating_add(uint64_t a,uint64_t b){
        return b>std::numeric_limits<uint64_t>::max()-a ?
            std::numeric_limits<uint64_t>::max():a+b;
    }
    State states_[COUNT]{};
};
}
