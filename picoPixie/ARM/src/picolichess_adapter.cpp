#include "picolichess_adapter.hpp"
#include "cloud_fen.hpp"
#include "cloud_https.hpp"
#include "cloud_policy.hpp"
#include "slot_timing.hpp"
#include "config.hpp"
#include "engine_runtime.hpp"
#include "pico/stdlib.h"
#include "pico/rand.h"
#include <algorithm>
#include <cstdio>
#include <string>
#include <vector>

namespace picoLichess {
namespace {
uint64_t now_ms(){return to_ms_since_boot(get_absolute_time());}
void service_wait(bool (*interrupted)(),void (*service)(),uint64_t until){
    while(!interrupted()&&now_ms()<until){service();sleep_ms(1);}
}
}
CloudOutcome cloud_evaluate(const picoSargon::Board& board,
    uint64_t,
    bool (*interrupted)(),void (*service)()){
    // Only the independent slot timers persist between searches.
    // The HTTPS transport is shared, but its request/response buffers are not.
    static CloudPolicy transport_policy;
    static CloudHttps cloud(transport_policy);
    struct ExchangeCleanup {
        CloudHttps& connection;
        ~ExchangeCleanup(){connection.clear_exchange();}
    } cleanup{cloud};
    CloudOutcome outcome;
    if(interrupted())return outcome;
    picoSargon::Board copy=board;
    std::vector<picoSargon::Move> legal;
    copy.legal(legal);
    if(legal.empty())return outcome;
    // The boot-initialized engine table is immutable for this session.
    initialize_engines();
    for(unsigned slot=0;slot<config::SLOT_COUNT && !interrupted();++slot){
        auto& engine=engine_slot(slot);
        auto& timing=engine.timing;
        const auto& settings=*engine.settings;
        const char* name=settings.name;
        if(!engine.remote && !engine.native)continue;
        if(engine.native){
            if(config::VERBOSE)std::printf("SLOTS slot=%u processor=native action=local-nnue\n",slot);
            outcome.fallback=true;
            return outcome;
        }
        const RemoteProvider provider=engine.provider;
        // A valid capturable en-passant square was rejected by chess-api in
        // the recorded game. Do not corrupt the FEN to work around that
        // validator; route directly to the next independent engine instead.
        if(provider==RemoteProvider::CHESS_API && chess_api_ep_unsupported(board)){
            if(config::VERBOSE)std::printf(
                "SLOTS slot=%u processor=%s action=skip reason=unsupported-legal-en-passant fen=%s\n",
                slot,name,board_fen(board).c_str());
            continue; // no TIMEGUARD: this is a position capability, not failure
        }
        if(SlotTiming::guarded(timing,now_ms())){
            if(config::VERBOSE)std::printf("SLOTS slot=%u processor=%s action=skip reason=timeguard remaining_ms=%llu\n",
                slot,name,(unsigned long long)SlotTiming::guard_remaining(timing,now_ms()));
            continue;
        }
        const std::string fen=board_fen(board,provider!=RemoteProvider::LICHESS);
        // A slot attempts exactly one transaction. Error -> next slot; do not
        // consume the next slot's context, or retry forever within this slot.
        const uint64_t eligible=SlotTiming::eligible_at(timing,now_ms(),settings.throttle);
        if(config::VERBOSE && eligible>now_ms())
            std::printf("SLOTS slot=%u processor=%s action=throttle wait_ms=%llu\n",
                slot,name,(unsigned long long)(eligible-now_ms()));
        service_wait(interrupted,service,eligible);
        if(interrupted())break;
        cloud.clear_exchange();
        const uint64_t start=now_ms();
        SlotTiming::start(timing,start);
        if(settings.verbose)
            std::printf("REMOTE request slot=%u processor=%s method=%s fen=%s throttle_ms=%lu\n",
                slot,name,provider==RemoteProvider::CHESS_API?"POST":"GET",fen.c_str(),
                (unsigned long)(settings.throttle<0?0:settings.throttle));
        if(!cloud.start(provider,settings,fen,start,0)){
            if(settings.verbose)std::printf("REMOTE error slot=%u processor=%s stage=start\n",slot,name);
            SlotTiming::fail(timing,now_ms(),settings.timeguard);
            cloud.clear_exchange();
            continue;
        }
        // No concurrent UCI position changes: the transaction queue in the
        // picoPixie overlay defers commands until this search completes.
        while(cloud.busy()&&!interrupted()){
            cloud.tick(now_ms(),config::TIMEOUT_MS);
            service();sleep_ms(1);
        }
        if(interrupted()){
            if(cloud.busy())cloud.cancel();
            return outcome;
        }
        const uint64_t elapsed=now_ms()-start;
        if(!cloud.done()){
            SlotTiming::fail(timing,now_ms(),settings.timeguard);
            cloud.clear_exchange();continue;
        }
        const CloudResult& reply=cloud.result();
        const int status=reply.http_status;
        if(settings.verbose){
            std::printf("REMOTE response slot=%u processor=%s http=%d depth=%d pvs=%u elapsed_ms=%llu\n",
                slot,name,status,reply.depth,(unsigned)reply.pvs.size(),
                (unsigned long long)elapsed);
            // One ordered output stream for delimiters and bytes. Interleaving
            // std::printf with std::fwrite caused apparent `}{` concatenations.
            std::fflush(stdout);
            const std::string heading="REMOTE json begin slot="+std::to_string(slot)+
                " processor="+name+" bytes="+std::to_string(reply.body.size())+"\n";
            std::fwrite(heading.data(),1,heading.size(),stdout);
            if(!reply.body.empty())std::fwrite(reply.body.data(),1,reply.body.size(),stdout);
            constexpr char end_marker[]="\nREMOTE json end\n";
            std::fwrite(end_marker,1,sizeof(end_marker)-1,stdout);
            if(status!=200){
                const auto& raw=cloud.raw_response();
                const std::string raw_heading="REMOTE raw-response begin bytes="+
                    std::to_string(raw.size())+"\n";
                std::fwrite(raw_heading.data(),1,raw_heading.size(),stdout);
                if(!raw.empty())std::fwrite(raw.data(),1,raw.size(),stdout);
                constexpr char raw_end[]="\nREMOTE raw-response end\n";
                std::fwrite(raw_end,1,sizeof(raw_end)-1,stdout);
            }
            std::fflush(stdout);
        }
        // Never accept a response from another position. Stockfish's v2
        // does not return a FEN; correlate it with this exchange and validate
        // the move against the immutable snapshot of legal moves.
        if(status==200){
            std::vector<CloudPV> candidates;
            for(const auto& pv:reply.pvs)
                for(const auto& move:legal)
                    if(picoSargon::Board::notation(move)==pv.move){
                        candidates.push_back(pv);break;
                    }
            CloudPV selected;size_t ties=0;
            if(choose_best_tie(candidates,board.turn,get_rand_32(),selected,ties)){
                outcome.has_move=true;outcome.move=selected.move;
                outcome.cp=selected.cp;outcome.depth=reply.depth;
                outcome.is_mate=selected.is_mate;outcome.mate=selected.mate;
                outcome.nodes=reply.nodes;outcome.nps=reply.nps;
                outcome.time_ms=elapsed;
                SlotTiming::success(timing);
                cloud.clear_exchange();
                return outcome;
            }
            if(config::VERBOSE)std::printf("SLOTS slot=%u processor=%s action=next reason=no-legal-bestmove\n",slot,name);
        } else if(config::VERBOSE)
            std::printf("SLOTS slot=%u processor=%s action=next reason=http-%d\n",slot,name,status);
        // Any unsuccessful remote transaction makes only this slot ineligible
        // for its own TIMEGUARD. Others remain immediately eligible.
        SlotTiming::fail(timing,now_ms(),settings.timeguard);
        if(config::VERBOSE && settings.timeguard>=0)
            std::printf("SLOTS slot=%u processor=%s action=timeguard duration_ms=%d\n",
                slot,name,settings.timeguard);
        cloud.clear_exchange();
    }
    if(!interrupted()){
        outcome.no_evaluator=true;
        if(config::VERBOSE)std::printf("SLOTS error=no-evaluator-available\n");
    }
    return outcome;
}
}
