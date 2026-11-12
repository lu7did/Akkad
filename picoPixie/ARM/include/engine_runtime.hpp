#pragma once
#include "config.hpp"
#include "remote_provider.hpp"
#include "slot_timing.hpp"

namespace picoLichess {
// Each priority slot has its own independent timers, even though its static
// configuration is looked up by engine name exactly once at boot.
struct EngineRuntimeSlot {
    const config::EngineSettings* settings=nullptr;
    RemoteProvider provider=RemoteProvider::CHESS_API;
    bool remote=false;
    bool native=false;
    SlotTiming::State timing{};
};
struct EngineRuntime {
    EngineRuntimeSlot slots[config::SLOT_COUNT]{};
    bool initialized=false;
};
inline EngineRuntime& engine_runtime(){static EngineRuntime runtime{};return runtime;}
inline void initialize_engines(){
    auto& runtime=engine_runtime();
    if(runtime.initialized)return;
    for(unsigned i=0;i<config::SLOT_COUNT;++i){
        auto& slot=runtime.slots[i];
        const int index=config::engine_index(config::SLOTS[i]);
        // Verified at compile time via valid_slots(); no string resolution at runtime.
        slot.settings=&config::ENGINES[static_cast<unsigned>(index)];
        slot.native=config::same(slot.settings->name,"native");
        slot.remote=!(slot.native||config::same(slot.settings->name,"null"));
        if(config::same(slot.settings->name,"lichess"))slot.provider=RemoteProvider::LICHESS;
        else if(config::same(slot.settings->name,"stockfish"))slot.provider=RemoteProvider::STOCKFISH;
        else slot.provider=RemoteProvider::CHESS_API;
    }
    runtime.initialized=true;
}
inline EngineRuntimeSlot& engine_slot(unsigned slot){return engine_runtime().slots[slot];}
}
