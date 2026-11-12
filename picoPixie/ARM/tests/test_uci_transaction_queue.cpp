#include "uci_transaction_queue.hpp"
#include <cassert>
#include <string>
int main(){
 picoLichess::UciTransactionQueue q;
 assert(q.push("ucinewgame"));
 assert(q.push("position fen 1k1r4/pp1b1R2/3q2pp/4p3/2B5/4Q3/PPP2B2/2K5 b - - 0 1"));
 assert(q.push("go movetime 15000"));
 std::string command;
 assert(q.pop(command)&&command=="ucinewgame");
 assert(q.pop(command)&&command.rfind("position fen ",0)==0);
 assert(q.pop(command)&&command=="go movetime 15000");
 assert(!q.pop(command));
 for(std::size_t i=0;i<q.MAX_QUEUED_COMMANDS;++i)assert(q.push("isready"));
 assert(!q.push("go"));
 q.clear();assert(q.empty());
}
