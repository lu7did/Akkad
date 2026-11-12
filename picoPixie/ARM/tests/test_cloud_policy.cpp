#include "cloud_policy.hpp"
#include <cassert>
using picoLichess::CloudPolicy;
int main(){
    CloudPolicy p;
    assert(p.eligible(0,2000));
    p.start(1000);
    assert(!p.eligible(2500,2000));
    p.finish(200,2800);
    assert(!p.eligible(2999,2000));
    assert(p.eligible(3000,2000));
    p.start(3000);p.finish(404,5500);
    assert(p.eligible(5500,2000)); // no 404 global block
    p.start(5500);p.finish(429,5600);
    assert(p.eligible(7500,2000)); // Lichess-only guard is elsewhere
    p.start(7500);p.cancel();
    assert(p.eligible(9500,2000));
}
