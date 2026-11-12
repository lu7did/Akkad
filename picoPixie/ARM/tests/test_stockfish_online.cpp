#include "cloud_pv.hpp"
#include "remote_provider.hpp"
#include <cassert>
#include <string>
using namespace picoLichess;
int main(){
    CloudPV pv;
    assert(parse_stockfish_online_response(R"({"success":true,"evaluation":1.36,"mate":null,"bestmove":"bestmove b7b6 ponder f3e5","continuation":"b7b6 f3e5"})",pv));
    assert(pv.move=="b7b6" && pv.cp==136 && !pv.is_mate);
    assert(parse_stockfish_online_response(R"({"success":true,"evaluation":null,"mate":-3,"bestmove":"bestmove e7e8q"})",pv));
    assert(pv.move=="e7e8q" && pv.is_mate && pv.mate==-3);
    // Regression: real response from the 2026-11-12 picoPixie telemetry.
    assert(parse_stockfish_online_response(R"({"success":true,"evaluation":null,"mate":"2","bestmove":"bestmove g5f6 ponder e7f6","continuation":"g5f6 e7f6 d2h6"})",pv));
    assert(pv.move=="g5f6" && pv.is_mate && pv.mate==2);
    assert(parse_stockfish_online_response(R"({"success":true,"evaluation":null,"mate":"-2","bestmove":"bestmove g5f6"})",pv));
    assert(pv.is_mate && pv.mate==-2);
    assert(!parse_stockfish_online_response(R"({"success":true,"evaluation":null,"mate":"bad","bestmove":"bestmove g5f6"})",pv));
    assert(!parse_stockfish_online_response(R"({"success":false,"data":"busy"})",pv));
    assert(!parse_stockfish_online_response(R"({"success":true,"evaluation":2,"bestmove":"bestmove z9z0"})",pv));
    assert(!parse_stockfish_online_response("}{\"success\":true}",pv));
    std::string host,path;
    assert(split_https_url("https://stockfish.online/api/s/v2.php",host,path));
    assert(host=="stockfish.online"&&path=="/api/s/v2.php");
    assert(!split_https_url("http://stockfish.online/api/s/v2.php",host,path));
}
