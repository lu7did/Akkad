#include "slot_timing.hpp"
#include <cassert>
using picoLichess::SlotTiming;
int main(){
    SlotTiming p;
    assert(p.eligible_at(0,1000,2000)==1000);
    p.start(0,1000);
    assert(p.eligible_at(0,1999,2000)==3000);
    assert(p.eligible_at(0,3100,2000)==3100);
    assert(p.eligible_at(1,1001,2000)==1001); // independent slot
    p.start(1,1200);
    assert(p.eligible_at(1,1700,4000)==5200);
    p.fail(0,3000,60000);
    assert(p.guarded(0,32999));
    assert(!p.guarded(1,32999));
    assert(p.guard_remaining(0,32999)==30001);
    assert(!p.guarded(0,63000));
    p.success(0);
    assert(!p.guarded(0,3001));
    p.fail(2,4400,-1);
    assert(!p.guarded(2,4400));
    p.start(3,200);
    assert(p.eligible_at(3,200,-1)==200);
    p.fail(3,200,-1);
    assert(!p.guarded(3,200));
    p.fail(1,1000,0);
    assert(!p.guarded(1,1000));
}
