#include "board.hpp"
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "lwip/tcp.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <functional>
#include <sstream>
#include <string>
#include <vector>

#ifndef PICOKERAS_WIFI_SSID
#define PICOKERAS_WIFI_SSID ""
#endif
#ifndef PICOKERAS_WIFI_PASSWORD
#define PICOKERAS_WIFI_PASSWORD ""
#endif
#ifndef PICOKERAS_UCI_PORT
#define PICOKERAS_UCI_PORT 6110
#endif
extern bool pico_model_init();
extern bool pico_model_eval(const picoSargon::Board&,double&);

using picoSargon::Board;
using picoSargon::Move;
struct Session {Board board;std::function<void(const std::string&)> send;};
static Session serial_session;
static Session tcp_session;
static tcp_pcb* listener=nullptr;
static tcp_pcb* client=nullptr;
static std::string serial_line,tcp_line;
static std::vector<std::string> pending;
static bool model_ready=false;
static void tcp_send(const std::string& msg) {
  if(!client)return;
  std::string line=msg+"\n";
  if(line.size()>tcp_sndbuf(client)) {std::printf("TCP send buffer full\n");return;}
  if(tcp_write(client,line.data(),static_cast<u16_t>(line.size()),TCP_WRITE_FLAG_COPY)!=ERR_OK)
    std::printf("TCP write failed\n");
  tcp_output(client);
}
static void close_client() {
  if(!client)return;
  auto* pcb=client;client=nullptr;tcp_arg(pcb,nullptr);tcp_recv(pcb,nullptr);
  tcp_err(pcb,nullptr); if(tcp_close(pcb)!=ERR_OK)tcp_abort(pcb);
  tcp_line.clear();tcp_session.board.reset();
}
static void error_cb(void*,err_t) {client=nullptr;tcp_line.clear();}
static err_t received(void*,tcp_pcb* pcb,pbuf* data,err_t error) {
  if(error!=ERR_OK)return error;
  if(!data){close_client();return ERR_OK;}
  tcp_recved(pcb,data->tot_len);
  for(pbuf* p=data;p;p=p->next) {
    const char* ch=static_cast<const char*>(p->payload);
    for(u16_t i=0;i<p->len;i++) {
      if(ch[i]=='\n') {if(!tcp_line.empty()&&tcp_line.back()=='\r')tcp_line.pop_back();
        if(pending.size()<16)pending.push_back("T"+tcp_line);tcp_line.clear();}
      else if(tcp_line.size()<2048)tcp_line.push_back(ch[i]);
      else tcp_line.clear();
    }
  }
  pbuf_free(data);return ERR_OK;
}
static err_t accepted(void*,tcp_pcb* pcb,err_t error) {
  if(error!=ERR_OK)return error;
  if(client){tcp_abort(pcb);return ERR_ABRT;}
  client=pcb;tcp_session.board.reset();tcp_arg(pcb,nullptr);
  tcp_recv(pcb,received);tcp_err(pcb,error_cb);std::printf("TCP connected\n");return ERR_OK;
}
static void command(Session& s,const std::string& cmd) {
  if(cmd=="uci") {s.send("id name picoKeras ARM v0.1.20");s.send("id author Dr. Pedro E. Colla");s.send("uciok");}
  else if(cmd=="isready")s.send(model_ready?"readyok":"info string ERROR model initialization failed");
  else if(cmd=="ucinewgame")s.board.reset();
  else if(cmd.rfind("position ",0)==0) {
    auto split=cmd.find(" moves ");
    std::string base=cmd.substr(9,split==std::string::npos?std::string::npos:split-9);
    if(base=="startpos")s.board.reset();
    else if(base.rfind("fen ",0)==0)s.board.set_fen(base.substr(4));
    else {s.send("info string ERROR unsupported position");return;}
    if(split!=std::string::npos) {std::istringstream in(cmd.substr(split+7));std::string mv;
      while(in>>mv)s.board.push(s.board.parse(mv));}
  } else if(cmd.rfind("go",0)==0) {
    if(!model_ready){s.send("info string ERROR model not ready");s.send("bestmove (none)");return;}
    auto start=time_us_64();std::vector<Move> moves;s.board.legal(moves);
    Move best{};bool found=false;double bestval=0;int inspected=0;
    if(!s.board.draw())for(const auto& m:moves){
      s.board.push(m);double v=0;std::vector<Move> rivals;s.board.legal(rivals);
      bool ok=true;
      if(rivals.empty())v=s.board.in_check()?-1.0:0.0;
      else if(s.board.draw())v=0.0;
      else ok=pico_model_eval(s.board,v);
      s.board.pop();
      if(!ok){s.send("info string ERROR network inference failed");break;}
      inspected++;if(!found||v<bestval){found=true;best=m;bestval=v;}
    }
    const auto ms=(time_us_64()-start)/1000;
    const double q=std::clamp(-bestval,-0.999,0.999);
    const int score=static_cast<int>(std::lround(400*std::atanh(q)))*(s.board.turn==1?1:-1);
    const int ply=2*(s.board.fullmove-1)+(s.board.turn==-1?1:0);
    char buf[180];std::snprintf(buf,sizeof(buf),"info ply %d depth 1 score cp %d nodes %d time %llu nps %llu",
      ply,score,inspected,static_cast<unsigned long long>(ms),
      static_cast<unsigned long long>(ms?inspected*1000ULL/ms:0));
    s.send(buf);s.send(std::string("bestmove ")+(found?Board::notation(best):"(none)"));
  }
}
int main() {
  stdio_init_all();sleep_ms(1400);
  std::printf("picoKeras ARM v0.1.20 BOOT board=%s\n",PICO_BOARD);
  model_ready=pico_model_init();
  serial_session.send=[](const std::string& msg){std::printf("%s\n",msg.c_str());};
  tcp_session.send=[](const std::string& msg){tcp_send(msg);};
  const bool wifi_enabled=PICOKERAS_WIFI_SSID[0]!='\0';
  bool wifi_ok=false;
  if(wifi_enabled) {
    if(cyw43_arch_init()==0){cyw43_arch_enable_sta_mode();
      int err=cyw43_arch_wifi_connect_timeout_ms(PICOKERAS_WIFI_SSID,PICOKERAS_WIFI_PASSWORD,
         CYW43_AUTH_WPA2_AES_PSK,30000);
      if(err==0){wifi_ok=true;
        listener=tcp_new_ip_type(IPADDR_TYPE_ANY);
        if(listener&&tcp_bind(listener,IP_ANY_TYPE,PICOKERAS_UCI_PORT)==ERR_OK){
          listener=tcp_listen(listener);if(listener)tcp_accept(listener,accepted);
          std::printf("TCP/UCI listening port %d\n",PICOKERAS_UCI_PORT);
        } else std::printf("TCP bind failed\n");
      }else std::printf("WiFi connect failed=%d\n",err);
    }else std::printf("WiFi init failed\n");
  } else std::printf("WiFi disabled; USB UCI available\n");
  for(;;) {
    if(wifi_ok)cyw43_arch_poll();
    int c=getchar_timeout_us(0);
    if(c>=0){if(c=='\n'){if(!serial_line.empty()&&serial_line.back()=='\r')serial_line.pop_back();
        if(pending.size()<16)pending.push_back("S"+serial_line);serial_line.clear();}
      else if(serial_line.size()<2048)serial_line.push_back(static_cast<char>(c));
      else serial_line.clear();}
    if(!pending.empty()) {
      std::string next=pending.front();pending.erase(pending.begin());
      try{command(next[0]=='T'?tcp_session:serial_session,next.substr(1));}
      catch(const std::exception& e){(next[0]=='T'?tcp_session:serial_session).send(std::string("info string ERROR ")+e.what());}
    }
    sleep_ms(1);
  }
}
