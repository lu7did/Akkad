#include "grumpy.hpp"
#include <fstream>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <cstring>
#include <cstdlib>
namespace picoSargon {
void Grumpy::load(const std::string& path){std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("cannot load grumpy model "+path);std::vector<uint8_t> blob((std::istreambuf_iterator<char>(f)),{});load_blob(blob.data(),blob.size());}
void Grumpy::load_blob(const uint8_t* blob,size_t len){if(len!=1304||std::memcmp(blob,"GRMP0001",8)!=0||blob[8]!=105||blob[9]!=0||blob[10]!=0||blob[11]!=0)throw std::runtime_error("Grumpy header invalid");const uint8_t* payload=blob+44;int k=0;for(int start=0;start<1260;start+=12){const uint8_t* part=payload+start;for(int j=0;j<16;++j){int bit=j*6,idx=bit>>3,off=bit&7;int two=part[idx]|(idx+1<12?(part[idx+1]<<8):0);raw_[k++]=static_cast<uint8_t>((two>>off)&63);}}}
int Grumpy::evaluate(const Board& b)const{int a[8],c[8];for(int j=0;j<8;++j)a[j]=c[j]=int(raw_[1536+j])-31;int mat=0,count=0;constexpr uint64_t packed=0x3847D12C4B064ULL;for(int color:{1,-1}){for(int sq=0;sq<64;++sq){int piece=b.piece(sq);if(piece*color<=0)continue;int kind=std::abs(piece)-1;++count;mat+=int((packed>>(10*kind))&1023);int f0=(color==1?0:384)+kind*64+sq;int f1=((color==1?384:0)+kind*64+sq)^56;for(int j=0;j<8;++j){int idx=f0*8+j,pc=(idx/512)*128+(idx%8),square=(idx/8)%64;a[j]+=int(raw_[pc+(square/8)*8])-31+int(raw_[pc+64+(square%8)*8])-31;idx=f1*8+j;pc=(idx/512)*128+(idx%8);square=(idx/8)%64;c[j]+=int(raw_[pc+(square/8)*8])-31+int(raw_[pc+64+(square%8)*8])-31;}}mat=-mat;}int bucket=(count-2)/4;if(count<2||bucket<0||bucket>7)throw std::runtime_error("unsupported Grumpy bucket");int total=8*(int(raw_[1672+bucket])-31);int* first=b.turn==1?a:c;int* second=b.turn==1?c:a;for(int i=0;i<16;++i){int x=i<8?first[i]:second[i-8];total+=std::min(32,std::max(0,x))*(int(raw_[1544+16*bucket+i])-31);}int scaled=std::abs(total*400)/1024;int neural=total>=0?scaled:-scaled;int side_score=neural+(b.turn==1?mat:-mat);return side_score*b.turn;}
}
