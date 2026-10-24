#include "board.hpp"
#include "net.hpp"
#include "mcts.hpp"
#include <cstdio>
#include <cstring>
int main(){static picoSargon::Board b;static picoalpha::Network net;static picoalpha::SearchHistory h;h.emplace_back(b);static std::array<float,112*64> x;picoalpha::encode_into(h,false,x);
 picoSargon::MoveList m;b.legal(m);FixedVector<int,256> legal;for(auto a:m)legal.push_back(picoalpha::policy_index(b,a));
 auto r=net.evaluate_legal(x,legal);float v=r.q;auto c=net.evaluate_legal(x,legal);
 printf("cache_hits=%u cache_misses=%u value_equal=%u count=%zu\n",net.cache_hits(),net.cache_misses(),unsigned(v==c.q),c.count);
 return !(net.cache_hits()==1&&net.cache_misses()==1&&v==c.q);
}
