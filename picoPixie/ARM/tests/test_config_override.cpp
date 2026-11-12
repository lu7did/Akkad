#include "config.hpp"
#include "engine_runtime.hpp"
static_assert(picoLichess::config::PORT == 6210);
static_assert(picoLichess::config::DEPTH == 32);
static_assert(picoLichess::config::QDEPTH == 2);
static_assert(picoLichess::config::TIMEOUT_MS == 15000);
static_assert(picoLichess::config::PLL_SYS == picoSargon::config::PLL_SYS);
static_assert(picoLichess::config::PORT != picoSargon::config::PORT);
static_assert(picoLichess::config::valid_engines());
static_assert(picoLichess::config::valid_slots());
static_assert(picoLichess::config::engine_index("stockfish")==2);
static_assert(picoLichess::config::ENGINES[0].throttle == 2000);
static_assert(picoLichess::config::ENGINES[1].timeguard == 60000);
static_assert(picoLichess::config::ENGINES[2].depth == 15);
static_assert(picoLichess::config::ENGINES[2].thinking_time == 1000);
static_assert(picoLichess::config::ENGINES[3].throttle == -1);
static_assert(picoLichess::config::same(picoLichess::config::ENGINES[2].name,"stockfish"));
int main(){
    picoLichess::initialize_engines();
    auto& runtime=picoLichess::engine_runtime();
    if(!runtime.initialized || !runtime.slots[3].native || !runtime.slots[0].remote)return 1;
    if(runtime.slots[2].settings!=&picoLichess::config::ENGINES[2])return 2;
    auto& a=runtime.slots[0].timing;
    auto& b=runtime.slots[1].timing;
    picoLichess::SlotTiming::start(a,100);
    if(picoLichess::SlotTiming::eligible_at(a,150,2000)!=2100)return 3;
    if(picoLichess::SlotTiming::eligible_at(b,150,2000)!=150)return 4;
    picoLichess::SlotTiming::fail(a,200,60000);
    if(!picoLichess::SlotTiming::guarded(a,210)||picoLichess::SlotTiming::guarded(b,210))return 5;
    return 0;
}
