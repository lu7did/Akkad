#pragma once
#include <algorithm>
#include <cstdint>
namespace picoLichess {
// Transport-level in-flight guard. Slot pacing and TIMEGUARD are exclusively
// owned by SlotTiming; CloudHttps passes an interval of zero to this guard.
class CloudPolicy {
    uint64_t last_request_=0;
    bool has_request_=false,in_flight_=false;
public:
    bool eligible(uint64_t now,uint32_t throttle_ms) const {
        return !in_flight_ && (!has_request_ ||
            (now>=last_request_ && now-last_request_>=throttle_ms));
    }
    uint64_t wait_until(uint64_t now,uint32_t throttle_ms) const {
        if(!has_request_)return now;
        return std::max(now,last_request_+throttle_ms);
    }
    void start(uint64_t now){last_request_=now;has_request_=true;in_flight_=true;}
    void finish(int, uint64_t, uint32_t=0){in_flight_=false;}
    void cancel(){in_flight_=false;}
};
}
