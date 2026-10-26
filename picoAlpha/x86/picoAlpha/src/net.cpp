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
 const int K=l.in*l.k*l.k,pad=l.k/2;
 thread_local std::vector<float> patch;
 if(patch.size()<size_t(K))patch.resize(K);
 std::vector<float> y(size_t(l.out)*64);
 for(int sq=0;sq<64;++sq){
  int row=sq/8,col=sq%8;std::fill_n(patch.data(),K,0.f);
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){
   int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){int cc=col+kc-pad;
    if(cc>=0&&cc<8)patch[(ch*l.k+kr)*l.k+kc]=x[ch*64+rr*8+cc];
   }
  }
  for(int out=0;out<l.out;++out){const float* w=l.w.data()+size_t(out)*K;
   float sum=l.b[out];for(int t=0;t<K;++t)sum+=patch[t]*w[t];
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
// Portable INT8: bounded reusable work buffers. One patch per square, reused by all output filters.
// Unlike the previous 64*K im2col this uses O(K) scratch (maximum K=112*9).
struct Int8Scratch {
 std::vector<int8_t> input, patch;
 void prepare(size_t n,size_t k){if(input.size()<n)input.resize(n);if(patch.size()<k)patch.resize(k);}
};
thread_local Int8Scratch int8_scratch;
std::vector<float> conv_int8(const std::vector<float>& x,const Layer& l,bool relu){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 if(l.qweights.size()!=l.w.size()||K<=0)throw std::runtime_error("INT8 weights missing");
 float maxval=0.f;for(float v:x)maxval=std::max(maxval,std::abs(v));
 const float xs=maxval>0?maxval/127.f:1.f;
 auto& scratch=int8_scratch;scratch.prepare(x.size(),size_t(K));
 auto* input=scratch.input.data();auto* patch=scratch.patch.data();
 for(size_t i=0;i<x.size();++i)input[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[i]/xs)))));
 std::vector<float> y(size_t(l.out)*64);
 for(int sq=0;sq<64;++sq){
  const int row=sq/8,col=sq%8;
  std::fill_n(patch,K,int8_t(0));
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){
   int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){int cc=col+kc-pad;
    if(cc>=0&&cc<8)patch[(ch*l.k+kr)*l.k+kc]=input[ch*64+rr*8+cc];
   }
  }
  for(int o=0;o<l.out;++o){
   const int8_t* w=l.qweights.data()+size_t(o)*K;
   int32_t a0=0,a1=0,a2=0,a3=0;int j=0;
   for(;j+3<K;j+=4){a0+=int32_t(patch[j])*w[j];a1+=int32_t(patch[j+1])*w[j+1];a2+=int32_t(patch[j+2])*w[j+2];a3+=int32_t(patch[j+3])*w[j+3];}
   int32_t acc=(a0+a1)+(a2+a3);for(;j<K;++j)acc+=int32_t(patch[j])*w[j];
   float v=(xs*l.qscale[o])*float(acc)+l.b[o];
   y[size_t(o)*64+sq]=relu?std::max(0.f,v):v;
  }
 }
 return y;
}
std::vector<float> linear_layer(const std::vector<float>& x,const std::vector<float>& w,const std::vector<float>& b,int out,bool relu){int in=int(x.size());if(int(w.size())!=in*out||int(b.size())!=out)throw std::runtime_error("Fully connected size");std::vector<float> y(out);for(int o=0;o<out;++o){const float* row=w.data()+size_t(o)*in;
  float a0=0.f,a1=0.f,a2=0.f,a3=0.f;int i=0;
  for(;i+3<in;i+=4){a0+=row[i]*x[i];a1+=row[i+1]*x[i+1];a2+=row[i+2]*x[i+2];a3+=row[i+3]*x[i+3];}
  float sum=b[o]+((a0+a1)+(a2+a3));for(;i<in;++i)sum+=row[i]*x[i];
  y[o]=relu?std::max(0.f,sum):sum;}return y;}
// Portable Pico FC1: per-row INT8 weights and a dynamically quantized activation vector.
std::vector<float> dense_int8(const std::vector<float>& x,const std::vector<int8_t>& w,
 const std::vector<float>& scales,const std::vector<float>& bias,int out){
 const int in=int(x.size());
 if(w.size()!=size_t(in)*out||scales.size()!=size_t(out))throw std::runtime_error("FC1 INT8 size mismatch");
 float maxval=0.f;for(float z:x)maxval=std::max(maxval,std::abs(z));
 const float xs=maxval>0?maxval/127.f:1.f;
 thread_local std::vector<int8_t> activations;
 activations.resize(x.size());
 for(int i=0;i<in;++i)activations[i]=int8_t(std::clamp(int(std::nearbyint(x[i]/xs)),-127,127));
 std::vector<float> result(out);
 for(int o=0;o<out;++o){
  const int8_t* row=w.data()+size_t(o)*in;
  int32_t s0=0,s1=0,s2=0,s3=0;int i=0;
  for(;i+3<in;i+=4){s0+=int(activations[i])*row[i];s1+=int(activations[i+1])*row[i+1];
   s2+=int(activations[i+2])*row[i+2];s3+=int(activations[i+3])*row[i+3];}
  int32_t sum=(s0+s1)+(s2+s3);
  for(;i<in;++i)sum+=int(activations[i])*row[i];
  result[o]=std::max(0.f,bias[o]+float(sum)*(xs*scales[o]));
 }
 return result;
}
Bytes gzread(const std::string& path){gzFile f=gzopen(path.c_str(),"rb");if(!f)throw std::runtime_error("No se puede abrir pesos: "+path);Bytes buf;unsigned char tmp[65536];int n;while((n=gzread(f,tmp,sizeof(tmp)))>0)buf.insert(buf.end(),tmp,tmp+n);int code=0;const char* err=gzerror(f,&code);if(n<0){std::string detail=err?err:"gzip";gzclose(f);throw std::runtime_error(detail);}gzclose(f);return buf;}
}
Network::Network(const std::string& path,bool int8,const std::string& model):int8_(int8){
 // Inspect the actual protobuf tensors, never the filename. Parse gzip only once.
 auto root=fields(gzread(path));
 const auto w=fields(get(root,10).data);
 const auto conv0=fields(get(w,1).data);
 const auto conv0_weights=fields(get(conv0,1).data);
 const auto& quantized=get(conv0_weights,3).data;
 // 112 input planes, 3x3 convolution, LINEAR16 (2 bytes per weight).
 constexpr size_t bytes_per_filter=112u*3u*3u*2u;
 if(quantized.size()%bytes_per_filter!=0)
  throw std::runtime_error("LC0: primera convolucion incompatible con 112 planos / LINEAR16");
 const size_t detected_filters=quantized.size()/bytes_per_filter;
 int detected_blocks=0;
 for(const auto& f:w)if(f.id==2)++detected_blocks;
 std::string detected;
 if(detected_filters==8 && detected_blocks==1)detected="picogyal";
 else if(detected_filters==16 && detected_blocks==2)detected="tinygyal";
 else throw std::runtime_error("LC0: arquitectura no soportada (filters="+
      std::to_string(detected_filters)+", blocks="+std::to_string(detected_blocks)+
      "); admitidas: picogyal 1x8 y tinygyal 2x16");
 if(model!="auto" && model!=detected)
  throw std::runtime_error("--model "+model+" no coincide con la red detectada: "+detected);
 filters_=int(detected_filters);blocks_=detected_blocks;model_=detected;
 auto fmt=fields(get(fields(get(root,4).data),2).data);
 for(int k=1;k<=5;++k){const int expect[]={0,1,1,4,2,1};if(int(get(fmt,k).value)!=expect[k])throw std::runtime_error("LC0: formato incompatible LINEAR16/classical conv/value");}
 input_=layer(get(w,1),112,filters_,3);
 std::vector<Field> res;for(auto& f:w)if(f.id==2)res.push_back(f);
 if(int(res.size())!=blocks_)throw std::runtime_error("LC0: cantidad de bloques residuales no coincide con --model");
 for(int j=0;j<blocks_;++j){auto f=fields(res[j].data);
  residual_[j*2]=layer(get(f,1),filters_,filters_,3);residual_[j*2+1]=layer(get(f,2),filters_,filters_,3);
  auto a=fields(get(f,3).data);se_[j]={linear(get(a,1)),linear(get(a,2)),linear(get(a,3)),linear(get(a,4))};
  if(se_[j].w1.size()!=size_t(filters_*filters_)||se_[j].b1.size()!=size_t(filters_)||
     se_[j].w2.size()!=size_t(2*filters_*filters_)||se_[j].b2.size()!=size_t(2*filters_))
    throw std::runtime_error("LC0: dimensiones de squeeze-excitation incorrectas");
 }
 p1_=layer(get(w,11),filters_,filters_,3);pol_=layer(get(w,3),filters_,80,3);
 vconv_=layer(get(w,6),filters_,32,1);
 v1w_=linear(get(w,7));v1b_=linear(get(w,8));v2w_=linear(get(w,9));v2b_=linear(get(w,10));
 if(v1w_.size()!=128u*2048u||v1b_.size()!=128u||v2w_.size()!=128u||v2b_.size()!=1u)
   throw std::runtime_error("LC0: dimensiones de la cabeza de valor incorrectas");
 if(int8_){prepare_quant(input_);for(int j=0;j<blocks_*2;++j)prepare_quant(residual_[j]);
  prepare_quant(p1_);prepare_quant(pol_);prepare_quant(vconv_);
  constexpr size_t n=2048;v1q_.resize(v1w_.size());v1qs_.resize(128);
  for(int o=0;o<128;++o){float peak=0.f;for(size_t i=0;i<n;++i)peak=std::max(peak,std::abs(v1w_[size_t(o)*n+i]));
   float scale=peak>0?peak/127.f:1.f;v1qs_[o]=scale;
   for(size_t i=0;i<n;++i)v1q_[size_t(o)*n+i]=int8_t(std::clamp(int(std::nearbyint(v1w_[size_t(o)*n+i]/scale)),-127,127));
  }
 }
}
Result Network::evaluate(const std::array<float,112*64>& input)const{
 std::vector<float> x(input.begin(),input.end());
 auto convolution=[this](const std::vector<float>& a,const Layer& l,bool relu){return int8_?conv_int8(a,l,relu):conv(a,l,relu);};
 auto z=convolution(x,input_,true);
 for(int j=0;j<blocks_;++j){
  auto y=convolution(convolution(z,residual_[j*2],true),residual_[j*2+1],false);
  std::vector<float> pooled(filters_);
  for(int c=0;c<filters_;++c)for(int i=0;i<64;++i)pooled[c]+=y[c*64+i]/64;
  auto a=linear_layer(pooled,se_[j].w1,se_[j].b1,filters_,true);
  auto shift=linear_layer(a,se_[j].w2,se_[j].b2,2*filters_,false);
  for(int c=0;c<filters_;++c){float scale=1.f/(1.f+std::exp(-shift[c]));
   for(int i=0;i<64;++i){int k=c*64+i;z[k]=std::max(0.f,z[k]+scale*y[k]+shift[c+filters_]);}}
 }
 auto logits=convolution(convolution(z,p1_,true),pol_,false);
 auto v=convolution(z,vconv_,true);
 auto h=int8_?dense_int8(v,v1q_,v1qs_,v1b_,128):linear_layer(v,v1w_,v1b_,128,true);
 auto q=linear_layer(h,v2w_,v2b_,1,false);
 return {std::move(logits),std::tanh(q[0])};
}
std::array<float,112*64> picoalpha::encode(const std::vector<picoSargon::Board>& states,bool fen_only){if(states.empty())throw std::runtime_error("history vacio");std::array<float,112*64> x{};const auto& curr=states.back();int count=std::min(int(states.size()),8);for(int j=0;j<8;++j){if(j>=count&&!fen_only)break;const auto& b=states[j<count?int(states.size())-1-j:0];for(int sq=0;sq<64;++sq){int p=b.piece(sq);if(!p)continue;int color=p*curr.turn>0?0:6;int kind=std::abs(p)-1;int rr=curr.turn==1?sq/8:7-sq/8;int idx=(j*13+color+kind)*64+rr*8+sq%8;x[idx]=1.f;}if(b.repetitions()>=2)for(int i=0;i<64;++i)x[(j*13+12)*64+i]=1;}
 auto fill=[&](int plane,bool yes){if(yes)for(int i=0;i<64;++i)x[plane*64+i]=1;};int own=curr.turn==1?0:2,opp=curr.turn==1?2:0;fill(104,bool(curr.castling&(own==0?2:8)));fill(105,bool(curr.castling&(own==0?1:4)));fill(106,bool(curr.castling&(opp==0?2:8)));fill(107,bool(curr.castling&(opp==0?1:4)));fill(108,curr.turn==-1);for(int i=0;i<64;++i)x[109*64+i]=float(curr.halfmove);fill(111,true);return x;}
int picoalpha::policy_index(const picoSargon::Board& b,picoSargon::Move m){int fr=m.from,to=m.to;if(std::abs(b.piece(fr))==6&&std::abs(to-fr)==2)to=fr/8*8+(to>fr?7:0);int f0=fr%8,r0=b.turn==1?fr/8:7-fr/8;int f1=to%8,r1=b.turn==1?to/8:7-to/8;int dx=f1-f0,dy=r1-r0;int plane=-1;
 if(m.promo==5||m.promo==4||m.promo==3){if(dy!=1||std::abs(dx)>1)throw std::runtime_error("promotion invalid");plane=64+(dx+1)*3+(m.promo==4?0:m.promo==3?1:2);}
 else{static const int kn[8][2]={{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};for(int j=0;j<8;++j)if(kn[j][0]==dx&&kn[j][1]==dy)plane=56+j;if(plane<0){static const int rays[8][2]={{0,1},{1,1},{1,0},{1,-1},{0,-1},{-1,-1},{-1,0},{-1,1}};int steps=std::max(std::abs(dx),std::abs(dy));if(steps<1||steps>7)throw std::runtime_error("invalid ray");int sx=(dx>0)-(dx<0),sy=(dy>0)-(dy<0);for(int j=0;j<8;++j)if(sx==rays[j][0]&&sy==rays[j][1])plane=j*7+steps-1;}}
 if(plane<0)throw std::runtime_error("no policy slot");return plane*64+r0*8+f0;
}
