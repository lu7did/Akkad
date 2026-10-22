#include "net.hpp"
#include <zlib.h>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <algorithm>
#include <numeric>
#include <fstream>
#include <sstream>
using namespace picoalpha;
namespace {
using Bytes=std::vector<unsigned char>;
struct Field {int id,wire;Bytes data;uint64_t value=0;};
uint64_t vi(const Bytes& b,size_t& p){uint64_t n=0;int shift=0;for(;;){if(p>=b.size()||shift>63)throw std::runtime_error("protobuf varint invalido");unsigned char v=b[p++];n|=uint64_t(v&127)<<shift;if(!(v&128))return n;shift+=7;}}
std::vector<Field> fields(const Bytes& b){size_t p=0;std::vector<Field> a;while(p<b.size()){uint64_t tag=vi(b,p);Field f;f.id=int(tag>>3);f.wire=int(tag&7);if(f.wire==0)f.value=vi(b,p);else if(f.wire==2){auto len=vi(b,p);if(len>b.size()-p)throw std::runtime_error("protobuf longitud truncada");f.data.assign(b.begin()+p,b.begin()+p+len);p+=len;}else if(f.wire==5||f.wire==1){size_t n=f.wire==5?4:8;if(n>b.size()-p)throw std::runtime_error("protobuf campo truncado");f.data.assign(b.begin()+p,b.begin()+p+n);p+=n;}else throw std::runtime_error("protobuf wire no compatible");a.push_back(std::move(f));}return a;}
const Field& get(const std::vector<Field>& a,int id){for(auto& f:a)if(f.id==id)return f;throw std::runtime_error("TinyGyal campo faltante: "+std::to_string(id));}
float f32(const Bytes& b){if(b.size()!=4)throw std::runtime_error("float protobuf invalido");float v;std::memcpy(&v,b.data(),4);return v;}
std::vector<float> linear(const Field& f){auto a=fields(f.data);float lo=f32(get(a,1).data),hi=f32(get(a,2).data);auto& d=get(a,3).data;if(d.size()%2)throw std::runtime_error("LINEAR16 invalido");std::vector<float> r(d.size()/2);float scale=(hi-lo)/65535.f;for(size_t i=0;i<r.size();++i){uint16_t x=uint16_t(d[2*i])|(uint16_t(d[2*i+1])<<8);r[i]=float(x)*scale+lo;}return r;}
std::vector<float> maybe(const std::vector<Field>& a,int id,int n,float fallback=0){for(const auto& f:a)if(f.id==id){auto v=linear(f);if(int(v.size())!=n)throw std::runtime_error("TinyGyal tensor size");return v;}return std::vector<float>(n,fallback);}
Layer layer(const Field& f,int in,int out,int k){auto a=fields(f.data);Layer l;l.in=in;l.out=out;l.k=k;l.w=linear(get(a,1));if(int(l.w.size())!=in*out*k*k)throw std::runtime_error("TinyGyal conv shape invalido");auto bias=maybe(a,2,out);bool has_bn=false;for(auto& t:a)if(t.id==3)has_bn=true;if(has_bn){auto mean=maybe(a,3,out),var=maybe(a,4,out),gamma=maybe(a,5,out),beta=maybe(a,6,out);for(int o=0;o<out;++o){float mul=gamma[o]/std::sqrt(var[o]+1e-5f);for(int j=0;j<in*k*k;++j)l.w[o*in*k*k+j]*=mul;bias[o]=(bias[o]-mean[o])*mul+beta[o];}}l.b=std::move(bias);return l;}
std::vector<float> conv(const std::vector<float>& x,const Layer& l,bool relu){
 // im2col: each output square has a contiguous receptive field. The dot product
 // has no coordinate tests or weight-index multiplication in its inner loop.
 const int K=l.in*l.k*l.k, pad=l.k/2;
 std::vector<float> patch(size_t(64)*K,0.f),y(size_t(l.out)*64);
 for(int row=0;row<8;++row)for(int col=0;col<8;++col){
  float* dst=patch.data()+size_t(row*8+col)*K;
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){
   const int rr=row+kr-pad;
   if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){
    const int cc=col+kc-pad;
    if(cc>=0&&cc<8)dst[(ch*l.k+kr)*l.k+kc]=x[ch*64+rr*8+cc];
   }
  }
 }
 for(int out=0;out<l.out;++out){
  const float* w=l.w.data()+size_t(out)*K;
  for(int sq=0;sq<64;++sq){
   const float* input=patch.data()+size_t(sq)*K;
   float sum=l.b[out];
   for(int t=0;t<K;++t)sum+=input[t]*w[t];
   y[out*64+sq]=relu?std::max(0.f,sum):sum;
  }
 }
 return y;
}
// Symmetric per-output-channel weights; dynamically calibrated per-tensor activations.
// int8 * int8 accumulated in int32; bias/residual/SE and final nonlinearities stay FP32.
void prepare_quant(Layer& l){
 const int K=l.in*l.k*l.k;
 l.qweights.resize(l.w.size());l.qscale.resize(l.out);
 for(int o=0;o<l.out;++o){
  float mx=0;for(int j=0;j<K;++j)mx=std::max(mx,std::abs(l.w[size_t(o)*K+j]));
  float scale=mx>0?mx/127.f:1.f;l.qscale[o]=scale;
  for(int j=0;j<K;++j){float z=l.w[size_t(o)*K+j]/scale;
   l.qweights[size_t(o)*K+j]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(z)))));
  }
 }
}
std::vector<float> conv_int8(const std::vector<float>& x,const Layer& l,bool relu){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 if(l.qweights.size()!=l.w.size())throw std::runtime_error("INT8 weights missing");
 float maxval=0.f;for(float v:x)maxval=std::max(maxval,std::abs(v));
 const float xs=maxval>0?maxval/127.f:1.f;
 std::vector<int8_t> input(x.size());
 for(size_t i=0;i<x.size();++i)input[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[i]/xs)))));
 std::vector<int8_t> patch(size_t(64)*K,0);
 for(int row=0;row<8;++row)for(int col=0;col<8;++col){
  int8_t* dst=patch.data()+size_t(row*8+col)*K;
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){
   int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){int cc=col+kc-pad;
    if(cc>=0&&cc<8)dst[(ch*l.k+kr)*l.k+kc]=input[ch*64+rr*8+cc];
   }
  }
 }
 std::vector<float> y(size_t(l.out)*64);
 for(int o=0;o<l.out;++o){
  const int8_t* w=l.qweights.data()+size_t(o)*K;
  const float outscale=xs*l.qscale[o];
  for(int sq=0;sq<64;++sq){
   const int8_t* xx=patch.data()+size_t(sq)*K;
   int32_t acc=0;
   for(int j=0;j<K;++j)acc+=int32_t(xx[j])*int32_t(w[j]);
   float v=outscale*float(acc)+l.b[o];
   y[o*64+sq]=relu?std::max(0.f,v):v;
  }
 }
 return y;
}
std::vector<float> linear_layer(const std::vector<float>& x,const std::vector<float>& w,const std::vector<float>& b,int out,bool relu){int in=int(x.size());if(int(w.size())!=in*out||int(b.size())!=out)throw std::runtime_error("Fully connected size");std::vector<float> y(out);for(int o=0;o<out;++o){float s=b[o];for(int i=0;i<in;++i)s+=w[o*in+i]*x[i];y[o]=relu?std::max(0.f,s):s;}return y;}
Bytes gzread(const std::string& path){gzFile f=gzopen(path.c_str(),"rb");if(!f)throw std::runtime_error("No se puede abrir pesos: "+path);Bytes buf;unsigned char tmp[65536];int n;while((n=gzread(f,tmp,sizeof(tmp)))>0)buf.insert(buf.end(),tmp,tmp+n);int code=0;const char* err=gzerror(f,&code);if(n<0){std::string detail=err?err:"gzip";gzclose(f);throw std::runtime_error(detail);}gzclose(f);return buf;}
}
Network::Network(const std::string& path,bool int8):int8_(int8){auto root=fields(gzread(path));auto fmt=fields(get(fields(get(root,4).data),2).data);for(int k=1;k<=5;++k){const int expect[]={0,1,1,4,2,1};if(int(get(fmt,k).value)!=expect[k])throw std::runtime_error("Formato no TinyGyal-8 LINEAR16/classical conv/value");}auto w=fields(get(root,10).data);input_=layer(get(w,1),112,16,3);std::vector<Field> blocks;for(auto& f:w)if(f.id==2)blocks.push_back(f);if(blocks.size()!=2)throw std::runtime_error("TinyGyal requires 2 residual blocks");for(int j=0;j<2;++j){auto f=fields(blocks[j].data);residual_[j*2]=layer(get(f,1),16,16,3);residual_[j*2+1]=layer(get(f,2),16,16,3);auto a=fields(get(f,3).data);se_[j]={linear(get(a,1)),linear(get(a,2)),linear(get(a,3)),linear(get(a,4))};if(se_[j].w1.size()!=256||se_[j].b1.size()!=16||se_[j].w2.size()!=512||se_[j].b2.size()!=32)throw std::runtime_error("TinyGyal SE shape");}p1_=layer(get(w,11),16,16,3);pol_=layer(get(w,3),16,80,3);vconv_=layer(get(w,6),16,32,1);v1w_=linear(get(w,7));v1b_=linear(get(w,8));v2w_=linear(get(w,9));v2b_=linear(get(w,10));if(int8_){prepare_quant(input_);for(auto& l:residual_)prepare_quant(l);prepare_quant(p1_);prepare_quant(pol_);prepare_quant(vconv_);}}
Result Network::evaluate(const std::array<float,112*64>& input)const{std::vector<float> x(input.begin(),input.end());auto convolution=[this](const std::vector<float>& a,const Layer& l,bool relu){return int8_?conv_int8(a,l,relu):conv(a,l,relu);};auto z=convolution(x,input_,true);for(int j=0;j<2;++j){auto y=convolution(convolution(z,residual_[j*2],true),residual_[j*2+1],false);std::vector<float> pooled(16);for(int c=0;c<16;++c)for(int i=0;i<64;++i)pooled[c]+=y[c*64+i]/64;auto a=linear_layer(pooled,se_[j].w1,se_[j].b1,16,true);auto shift=linear_layer(a,se_[j].w2,se_[j].b2,32,false);for(int c=0;c<16;++c){float scale=1.f/(1.f+std::exp(-shift[c]));for(int i=0;i<64;++i){int k=c*64+i;z[k]=std::max(0.f,z[k]+scale*y[k]+shift[c+16]);}}}auto logits=convolution(convolution(z,p1_,true),pol_,false);auto v=convolution(z,vconv_,true);auto h=linear_layer(v,v1w_,v1b_,128,true);auto q=linear_layer(h,v2w_,v2b_,1,false);return {std::move(logits),std::tanh(q[0])};}
std::array<float,112*64> picoalpha::encode(const std::vector<picoSargon::Board>& states,bool fen_only){if(states.empty())throw std::runtime_error("history vacio");std::array<float,112*64> x{};const auto& curr=states.back();int count=std::min(int(states.size()),8);for(int j=0;j<8;++j){if(j>=count&&!fen_only)break;const auto& b=states[j<count?int(states.size())-1-j:0];for(int sq=0;sq<64;++sq){int p=b.piece(sq);if(!p)continue;int color=p*curr.turn>0?0:6;int kind=std::abs(p)-1;int rr=curr.turn==1?sq/8:7-sq/8;int idx=(j*13+color+kind)*64+rr*8+sq%8;x[idx]=1.f;}if(b.repetitions()>=2)for(int i=0;i<64;++i)x[(j*13+12)*64+i]=1;}
 auto fill=[&](int plane,bool yes){if(yes)for(int i=0;i<64;++i)x[plane*64+i]=1;};int own=curr.turn==1?0:2,opp=curr.turn==1?2:0;fill(104,bool(curr.castling&(own==0?2:8)));fill(105,bool(curr.castling&(own==0?1:4)));fill(106,bool(curr.castling&(opp==0?2:8)));fill(107,bool(curr.castling&(opp==0?1:4)));fill(108,curr.turn==-1);for(int i=0;i<64;++i)x[109*64+i]=float(curr.halfmove);fill(111,true);return x;}
int picoalpha::policy_index(const picoSargon::Board& b,picoSargon::Move m){int fr=m.from,to=m.to;if(std::abs(b.piece(fr))==6&&std::abs(to-fr)==2)to=fr/8*8+(to>fr?7:0);int f0=fr%8,r0=b.turn==1?fr/8:7-fr/8;int f1=to%8,r1=b.turn==1?to/8:7-to/8;int dx=f1-f0,dy=r1-r0;int plane=-1;
 if(m.promo==5||m.promo==4||m.promo==3){if(dy!=1||std::abs(dx)>1)throw std::runtime_error("promotion invalid");plane=64+(dx+1)*3+(m.promo==4?0:m.promo==3?1:2);}
 else{static const int kn[8][2]={{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};for(int j=0;j<8;++j)if(kn[j][0]==dx&&kn[j][1]==dy)plane=56+j;if(plane<0){static const int rays[8][2]={{0,1},{1,1},{1,0},{1,-1},{0,-1},{-1,-1},{-1,0},{-1,1}};int steps=std::max(std::abs(dx),std::abs(dy));if(steps<1||steps>7)throw std::runtime_error("invalid ray");int sx=(dx>0)-(dx<0),sy=(dy>0)-(dy<0);for(int j=0;j<8;++j)if(sx==rays[j][0]&&sy==rays[j][1])plane=j*7+steps-1;}}
 if(plane<0)throw std::runtime_error("no policy slot");return plane*64+r0*8+f0;
}
