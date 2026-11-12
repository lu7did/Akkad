#include "cloud_pv.hpp"
#include <cassert>
#include <string>
#include <vector>
using namespace picoLichess;
int main(){
    const auto p=parse_cloud_pvs(R"({"depth":32,"pvs":[{"moves":"e2e4 e7e5","cp":20},{"moves":"d2d4 d7d5","cp":20},{"moves":"g1f3","cp":18}]})");
    assert(p.size()==3);
    CloudPV c;size_t ties=0;
    assert(choose_best_tie(p,1,0,c,ties)&&ties==2&&c.move=="e2e4");
    assert(choose_best_tie(p,1,1,c,ties)&&ties==2&&c.move=="d2d4");
    assert(choose_best_tie(p,-1,1,c,ties)&&ties==1&&c.move=="g1f3");
    auto mate=parse_cloud_pvs(R"({"pvs":[{"moves":"e2e4","cp":200},{"moves":"d2d4","mate":3},{"moves":"c2c4","mate":3}]})");
    assert(choose_best_tie(mate,1,1,c,ties)&&ties==2&&c.move=="c2c4");
    assert(choose_best_tie(mate,-1,0,c,ties)&&ties==1&&c.move=="e2e4");
    assert(parse_cloud_pvs(R"({"pvs":[{"moves":"invalid","cp":9}]})").empty());
    assert(parse_cloud_pvs(R"({"pvs":[{"moves":"e2e4","mate":-4}]})").size()==1);
    assert(parse_cloud_pvs(R"({"pvs":[{"moves":"e2e4","cp":9,"mate":1}]})").empty());
    // Exact Stockfish debug sample supplied by the remote API.
    const auto stats=parse_stockfish_debug("info depth 11 seldepth 23 multipv 1 score cp 87 nodes 2658863 nps 26588630 hashfull 32 tbhits 0 time 100 pv c7c5 d2d4");
    assert(stats.complete && stats.depth==11 && stats.nodes==2658863ULL && stats.nps==26588630ULL);
    // Last complete UCI info record wins, incomplete records do not overwrite it.
    const auto multiple=parse_stockfish_debug("info depth 10 nodes 500 nps 10000\\ninfo depth 11 nodes 600 nps 12000\\ninfo depth 12 nodes 700");
    assert(multiple.complete && multiple.depth==11 && multiple.nodes==600 && multiple.nps==12000);
    assert(!parse_stockfish_debug("info depth 11 score cp 87 time 100").complete);
    assert(!parse_stockfish_debug("info depth 11 nodes -1 nps 300").complete);
}
