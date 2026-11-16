#include "board.hpp"
#include <cassert>
#include <iostream>
#include <vector>
using namespace picoSargon;
int main(){
 Board b;
 auto e4=b.parse("e2e4");
 assert(e4.from==at120(12) && e4.to==at120(28));
 assert(e4.from==35 && e4.to==55);
 assert(Board::notation(e4)=="e2e4");
 b.push(e4);auto e5=b.parse("e7e5");
 assert(e5.from==at120(52) && e5.to==at120(36));
 b.push(e5);b.pop();b.pop();
 assert(b.parse("e2e4")==e4);
 Board c("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
 auto castle=c.parse("e1g1");
 assert(castle.from==at120(4) && castle.to==at120(6));
 c.push(castle);assert(c.piece(6)==6&&c.piece(5)==4);c.pop();
 Board ep("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1");
 auto capture=ep.parse("e5d6");assert(capture.from==at120(36)&&capture.to==at120(43));
 ep.push(capture);assert(ep.piece(43)==1 && ep.piece(35)==0);ep.pop();
 Board promo("4k3/P7/8/8/8/8/8/4K3 w - - 0 1");
 auto promote=promo.parse("a7a8q");assert(promote.from==at120(48)&&promote.to==at120(56));
 promo.push(promote);assert(promo.piece(56)==5);promo.pop();
 std::cout<<"mailbox 120 move/UCI/undo/castle/ep/promotion OK\n";
}
