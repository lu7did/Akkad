#include "net.hpp"
#include "generated_tinygyal.hpp"
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <algorithm>
using namespace picoalpha;
namespace {
// Model resides in FLASH. Access weights and FC matrices without RAM copies.
const uint8_t* cur=PICOALPHA_MODEL_DATA;
const uint8_t* const end=PICOALPHA_MODEL_DATA+PICOALPHA_MODEL_SIZE;
void need(size_t n){if(n>size_t(end-cur))throw std::runtime_error("embedded model truncated");}
unsigned read32(){need(4);unsigned x=unsigned(cur[0])|(unsigned(cur[1])<<8)|(unsigned(cur[2])<<16)|(unsigned(cur[3])<<24);cur+=4;return x;}
const float* floatarray(size_t n){need(n*4);auto* p=reinterpret_cast<const float*>(cur);cur+=n*4;return p;}
Layer layer(){Layer l;l.in=int(read32());l.out=int(read32());l.k=int(read32());size_t n=size_t(l.in)*l.out*l.k*l.k;need(n);l.weights=reinterpret_cast<const int8_t*>(cur);cur+=n;cur+=(-size_t(cur-PICOALPHA_MODEL_DATA))%4;l.scale=floatarray(l.out);l.bias=floatarray(l.out);return l;}
std::vector<float> conv(const std::vector<float>& x,const Layer& l,bool relu){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 float mx=0;for(float v:x)mx=std::max(mx,std::abs(v));const float xs=mx>0?mx/127.f:1.f;
 std::vector<int8_t> input(x.size());for(size_t i=0;i<x.size();++i)input[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[i]/xs)))));
 // Allocate patch for one square, not 64-square im2col (lower SRAM peak).
 std::vector<int8_t> patch(K);std::vector<float> y(size_t(l.out)*64);
 for(int sq=0;sq<64;++sq){int row=sq/8,col=sq%8;
  std::fill(patch.begin(),patch.end(),0);
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){int cc=col+kc-pad;if(cc>=0&&cc<8)patch[(ch*l.k+kr)*l.k+kc]=input[ch*64+rr*8+cc];}}
  for(int o=0;o<l.out;++o){const int8_t* w=l.weights+size_t(o)*K;int32_t acc=0;
   for(int j=0;j<K;++j)acc+=int32_t(patch[j])*int32_t(w[j]);
   float value=xs*l.scale[o]*float(acc)+l.bias[o];y[o*64+sq]=relu?std::max(0.f,value):value;
  }
 }
 return y;
}
std::vector<float> fc(const std::vector<float>& x,const float* w,const float* b,int out,bool relu){
 std::vector<float> y(out);for(int o=0;o<out;++o){float v=b[o];for(size_t j=0;j<x.size();++j)v+=w[size_t(o)*x.size()+j]*x[j];y[o]=relu?std::max(0.f,v):v;}return y;
}
}
Network::Network(){cur=PICOALPHA_MODEL_DATA;
 input_=layer();for(auto& l:residual_)l=layer();p1_=layer();pol_=layer();vconv_=layer();
 for(auto& se:se_){se.w1=floatarray(256);se.b1=floatarray(16);se.w2=floatarray(512);se.b2=floatarray(32);}
 v1w_=floatarray(32*64*128);v1b_=floatarray(128);v2w_=floatarray(128);v2b_=floatarray(1);
 if(cur!=end)throw std::runtime_error("unexpected embedded model byte count");
}
Result Network::evaluate(const std::array<float,112*64>& input) const {
 std::vector<float> x(input.begin(),input.end());auto z=conv(x,input_,true);x.clear();x.shrink_to_fit();
 for(int j=0;j<2;++j){auto y=conv(conv(z,residual_[j*2],true),residual_[j*2+1],false);
  std::vector<float> pooled(16);for(int c=0;c<16;++c)for(int i=0;i<64;++i)pooled[c]+=y[c*64+i]/64;
  auto a=fc(pooled,se_[j].w1,se_[j].b1,16,true);auto shift=fc(a,se_[j].w2,se_[j].b2,32,false);
  for(int c=0;c<16;++c){float scale=1.f/(1.f+std::exp(-shift[c]));for(int i=0;i<64;++i){int k=c*64+i;z[k]=std::max(0.f,z[k]+scale*y[k]+shift[c+16]);}}
 }
 auto logits=conv(conv(z,p1_,true),pol_,false);auto v=conv(z,vconv_,true);auto h=fc(v,v1w_,v1b_,128,true);auto q=fc(h,v2w_,v2b_,1,false);
 return {std::move(logits),std::tanh(q[0])};
}
std::array<float,112*64> picoalpha::encode(const std::vector<picoSargon::Board>& states,bool fen_only){if(states.empty())throw std::runtime_error("history vacio");std::array<float,112*64> x{};const auto& curr=states.back();int count=std::min(int(states.size()),8);for(int j=0;j<8;++j){if(j>=count&&!fen_only)break;const auto& b=states[j<count?int(states.size())-1-j:0];for(int sq=0;sq<64;++sq){int p=b.piece(sq);if(!p)continue;int color=p*curr.turn>0?0:6;int kind=std::abs(p)-1;int rr=curr.turn==1?sq/8:7-sq/8;int idx=(j*13+color+kind)*64+rr*8+sq%8;x[idx]=1.f;}if(b.repetitions()>=2)for(int i=0;i<64;++i)x[(j*13+12)*64+i]=1;}
 auto fill=[&](int plane,bool yes){if(yes)for(int i=0;i<64;++i)x[plane*64+i]=1;};int own=curr.turn==1?0:2,opp=curr.turn==1?2:0;fill(104,bool(curr.castling&(own==0?2:8)));fill(105,bool(curr.castling&(own==0?1:4)));fill(106,bool(curr.castling&(opp==0?2:8)));fill(107,bool(curr.castling&(opp==0?1:4)));fill(108,curr.turn==-1);for(int i=0;i<64;++i)x[109*64+i]=float(curr.halfmove);fill(111,true);return x;}
int picoalpha::policy_index(const picoSargon::Board& b,picoSargon::Move m){int fr=m.from,to=m.to;if(std::abs(b.piece(fr))==6&&std::abs(to-fr)==2)to=fr/8*8+(to>fr?7:0);int f0=fr%8,r0=b.turn==1?fr/8:7-fr/8;int f1=to%8,r1=b.turn==1?to/8:7-to/8;int dx=f1-f0,dy=r1-r0;int plane=-1;
 if(m.promo==5||m.promo==4||m.promo==3){if(dy!=1||std::abs(dx)>1)throw std::runtime_error("promotion invalid");plane=64+(dx+1)*3+(m.promo==4?0:m.promo==3?1:2);}
 else{static const int kn[8][2]={{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};for(int j=0;j<8;++j)if(kn[j][0]==dx&&kn[j][1]==dy)plane=56+j;if(plane<0){static const int rays[8][2]={{0,1},{1,1},{1,0},{1,-1},{0,-1},{-1,-1},{-1,0},{-1,1}};int steps=std::max(std::abs(dx),std::abs(dy));if(steps<1||steps>7)throw std::runtime_error("invalid ray");int sx=(dx>0)-(dx<0),sy=(dy>0)-(dy<0);for(int j=0;j<8;++j)if(sx==rays[j][0]&&sy==rays[j][1])plane=j*7+steps-1;}}
 if(plane<0)throw std::runtime_error("no policy slot");return plane*64+r0*8+f0;
}
