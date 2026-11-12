#pragma once
// picoPixie ARM firmware settings. The shared picoSargon config.h is unchanged.
#include "config.h"
namespace picoLichess { namespace config {
using namespace picoSargon::config;
inline constexpr const char* UCI_NAME = "picoPixie v0.1.28";
inline constexpr unsigned PORT = 6210;
inline constexpr const char* MDNS_HOSTNAME = "picopixie";
inline constexpr const char* MDNS_SERVICE_NAME = "picoPixie UCI";

// Engine catalog: API parameters and capabilities are defined once per engine.
// Slots below contain ONLY the engine names and therefore define priority.
// -1 disables a timer (mandatory for native/null).
struct EngineSettings {
    const char* name;
    const char* url;
    const char* key;
    int throttle;
    int timeguard;
    int depth;
    int thinking_time;
    bool verbose;
    int variants;
    const char* searchmoves;
};
inline constexpr EngineSettings ENGINES[] = {
    {"chess-api", "https://chess-api.com/v1",             "", 2000, 60000, 18,  100, true, 5, ""},
    {"lichess",   "https://lichess.org/api/cloud-eval",     "", 2000, 60000, -1,   -1, true, 5, ""},
    {"stockfish", "https://stockfish.online/api/s/v2.php", "1365511f6799697fcf2c446bc38eabda", 3000, 60000, 15, 1000, true, 1, ""},
    {"native",    "",                                        "",   -1,    -1, -1,   -1, false, 1, ""},
    {"null",      "",                                        "",   -1,    -1, -1,   -1, false, 1, ""}
};
inline constexpr unsigned ENGINE_COUNT=sizeof(ENGINES)/sizeof(ENGINES[0]);
inline constexpr unsigned SLOT_COUNT=4;
// A processor can appear only once in the priority list, except null.
inline constexpr const char* SLOTS[SLOT_COUNT]={
    "chess-api", "stockfish", "lichess", "native"
};
inline constexpr bool VERBOSE=true;
inline constexpr bool DEBUG=VERBOSE;

constexpr bool same(const char* a,const char* b){
    while(*a&&*b){if(*a++!=*b++)return false;}
    return *a==*b;
}
constexpr int engine_index(const char* name){
    for(unsigned i=0;i<ENGINE_COUNT;++i)
        if(same(name,ENGINES[i].name))return static_cast<int>(i);
    return -1;
}
constexpr bool valid_engines(){
    for(unsigned i=0;i<ENGINE_COUNT;++i){
        const auto& e=ENGINES[i];
        if(e.throttle < -1||e.timeguard < -1)return false;
        for(unsigned j=0;j<i;++j)if(same(e.name,ENGINES[j].name))return false;
        if(same(e.name,"native")||same(e.name,"null")){
            if(e.throttle!=-1||e.timeguard!=-1||e.url[0]||e.key[0])return false;
        }else{
            if(!(e.url[0]=='h'&&e.url[1]=='t'&&e.url[2]=='t'&&
                 e.url[3]=='p'&&e.url[4]=='s'&&e.url[5]==':'&&
                 e.url[6]=='/'&&e.url[7]=='/'&&e.url[8]))return false;
            if(same(e.name,"chess-api")&&
                (e.depth<1||e.depth>18||e.thinking_time<1||e.thinking_time>100||
                 e.variants<1||e.variants>5||e.searchmoves[0]))return false;
            if(same(e.name,"stockfish")&&(e.depth<1||e.depth>15))return false;
            if(same(e.name,"lichess")&&(e.variants<1||e.variants>5))return false;
        }
    }
    return true;
}
constexpr bool valid_slots(){
    for(unsigned i=0;i<SLOT_COUNT;++i){
        if(engine_index(SLOTS[i])<0)return false;
        if(!same(SLOTS[i],"null"))
            for(unsigned j=0;j<i;++j)if(same(SLOTS[i],SLOTS[j]))return false;
    }
    return true;
}
static_assert(valid_engines(), "Invalid picoPixie engine catalog");
static_assert(valid_slots(), "Invalid picoPixie priority slots");
// Local NNUE fallback, not affected by remote thinking-time settings.
inline constexpr unsigned TIMEOUT_MS = 15000;
inline constexpr int DEPTH = 32;
inline constexpr int QDEPTH = 2;
static_assert(PORT > 0 && PORT <= 65535, "Invalid TCP port");
static_assert(DEPTH > 0 && DEPTH <= 32, "Fallback DEPTH must be 1..32");
static_assert(QDEPTH >= 0, "Fallback QDEPTH must be nonnegative");
} }
