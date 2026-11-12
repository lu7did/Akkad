#include "cloud_https.hpp"
#include "cloud_roots.hpp"
#include "cloud_pv.hpp"
#include "config.hpp"
#include "api_key_url.hpp"
#include "http_response.hpp"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include "lwip/altcp.h"
#include "lwip/altcp_tls.h"
#include "lwip/dns.h"
#include "lwip/pbuf.h"
#include "mbedtls/ssl.h"
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>

namespace picoLichess {
namespace {
constexpr size_t MAX_RESPONSE=12288;
std::string encode(const std::string& value){
    const char hex[]="0123456789ABCDEF";
    std::string result;
    for(unsigned char ch:value){
        if(std::isalnum(ch)||ch=='-'||ch=='_'||ch=='.'||ch=='~')result+=char(ch);
        else {result+='%';result+=hex[ch>>4];result+=hex[ch&15];}
    }
    return result;
}
uint32_t retry_after(const std::string& response){
    // Support integer seconds only; HTTP-date may be added after SNTP time sync.
    std::string headers=response.substr(0,response.find("\r\n\r\n"));
    std::transform(headers.begin(),headers.end(),headers.begin(),[](unsigned char c){return char(std::tolower(c));});
    auto p=headers.find("retry-after:");if(p==std::string::npos)return 0;
    p+=12;while(p<headers.size()&&headers[p]==' ')++p;
    if(p>=headers.size()||!std::isdigit(static_cast<unsigned char>(headers[p])))return 0;
    long seconds=std::strtol(headers.c_str()+p,nullptr,10);
    if(seconds<0)return 0;
    return static_cast<uint32_t>(std::min(seconds,86400L))*1000;
}
}
bool CloudHttps::init(){
    if(tls_config_)return true;
    tls_config_=altcp_tls_create_config_client(reinterpret_cast<const uint8_t*>(CLOUD_TRUST_ROOTS),sizeof(CLOUD_TRUST_ROOTS));
    return tls_config_!=nullptr;
}
bool CloudHttps::start(RemoteProvider provider,const config::EngineSettings& settings,const std::string& fen,uint64_t now,uint32_t interval_ms){
    if(busy_ || !policy_.eligible(now,interval_ms) || !init())return false;
    // Each request owns fresh buffers, never retaining bytes from a prior one.
    clear_exchange();
    ++generation_;
    expected_fen_=fen;
    provider_=provider;
    active_depth_=settings.depth;
    std::string path;
    const char* url=settings.url;
    if(!split_https_url(url,host_,path))return false;
    done_=false;busy_=true;started_ms_=now;
    if(provider==RemoteProvider::CHESS_API) {
        // FEN is generated locally, but escape it as JSON rather than relying on
        // its present character repertoire. searchmoves is intentionally empty.
        std::string escaped; escaped.reserve(fen.size());
        for(char c:fen){if(c=='"'||c=='\\')escaped+='\\';escaped+=c;}
        const std::string payload="{\"fen\":\""+escaped+"\",\"variants\":"+
            std::to_string(settings.variants)+",\"depth\":"+
            std::to_string(settings.depth)+",\"maxThinkingTime\":"+
            std::to_string(settings.thinking_time)+",\"searchmoves\":\""+settings.searchmoves+"\"}";
        request_="POST "+with_api_key(path,settings.key)+" HTTP/1.1\r\nHost: "+host_+"\r\nUser-Agent: picoPixie/0.1.28\r\nContent-Type: application/json\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\nContent-Length: "+
            std::to_string(payload.size())+"\r\n\r\n"+payload;
    } else {
        const std::string query=provider==RemoteProvider::LICHESS
            ? "fen="+encode(fen)+"&multiPv="+std::to_string(settings.variants)
            : "fen="+encode(fen)+"&depth="+std::to_string(settings.depth);
        const std::string target=with_api_key(
            path+(path.find('?')==std::string::npos?"?":"&")+query,settings.key);
        request_="GET "+target+
           " HTTP/1.1\r\nHost: "+host_+"\r\nUser-Agent: picoPixie/0.1.28\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n";
    }
    policy_.start(now);
    pcb_=altcp_tls_new(tls_config_,IPADDR_TYPE_ANY);
    if(!pcb_){finish(0);return false;}
    for(auto& context:tcp_contexts_){if(!context.in_use){active_tcp_=&context;break;}}
    if(!active_tcp_){finish(0);return false;}
    active_tcp_->owner=this;
    active_tcp_->generation=generation_;
    active_tcp_->in_use=true;
    altcp_arg(pcb_,active_tcp_);
    altcp_recv(pcb_,&CloudHttps::recv_callback);
    altcp_err(pcb_,&CloudHttps::error_callback);
    auto* ssl=altcp_tls_context(pcb_);
    if(!ssl||mbedtls_ssl_set_hostname(static_cast<mbedtls_ssl_context*>(ssl),host_.c_str())!=0){finish(0);return false;}
    ip_addr_t address;
    // DNS is asynchronous and cannot be cancelled. Its callback must never
    // attach a late address to a subsequent request on this shared transport.
    DnsContext* dns=nullptr;
    for(auto& context:dns_contexts_){if(!context.in_use){dns=&context;break;}}
    if(!dns){finish(0);return false;}
    dns->owner=this;dns->generation=generation_;dns->in_use=true;
    err_t e=dns_gethostbyname(host_.c_str(),&address,&CloudHttps::dns_callback,dns);
    if(e==ERR_OK){dns->in_use=false;on_dns(&address,generation_);}
    else if(e!=ERR_INPROGRESS){dns->in_use=false;finish(0);return false;}
    return true;
}
void CloudHttps::dns_callback(const char*,const ip_addr_t* addr,void* arg){
    DnsContext* ctx=static_cast<DnsContext*>(arg);
    auto* owner=ctx->owner;
    const uint64_t generation=ctx->generation;
    ctx->in_use=false;
    owner->on_dns(addr,generation);
}
void CloudHttps::on_dns(const ip_addr_t* addr,uint64_t generation){
    if(!busy_||generation!=generation_||!pcb_)return;
    if(!addr||altcp_connect(pcb_,addr,443,&CloudHttps::connected_callback)!=ERR_OK)finish(0);
}
err_t CloudHttps::connected_callback(void* arg,altcp_pcb* pcb,err_t error){
    auto* ctx=static_cast<TcpContext*>(arg);
    if(!ctx)return ERR_OK;
    auto* self=ctx->owner;
    if(!self||!self->busy_||self->active_tcp_!=ctx||
       self->generation_!=ctx->generation||self->pcb_!=pcb)return ERR_OK;
    self->in_tcp_callback_=true;
    if(error!=ERR_OK){self->finish(0);self->in_tcp_callback_=false;return ERR_OK;}
    if(self->request_.size()>altcp_sndbuf(pcb)||altcp_write(pcb,self->request_.data(),self->request_.size(),TCP_WRITE_FLAG_COPY)!=ERR_OK){
        self->finish(0);self->in_tcp_callback_=false;return ERR_OK;
    }
    altcp_output(pcb);
    self->in_tcp_callback_=false;
    return ERR_OK;
}
err_t CloudHttps::recv_callback(void* arg,altcp_pcb* pcb,pbuf* p,err_t error){
    auto* ctx=static_cast<TcpContext*>(arg);
    if(!ctx){if(p)pbuf_free(p);return ERR_OK;}
    auto* self=ctx->owner;
    if(!self||!self->busy_||self->active_tcp_!=ctx||
       self->generation_!=ctx->generation||self->pcb_!=pcb){
        if(p)pbuf_free(p);
        return ERR_OK;
    }
    self->in_tcp_callback_=true;
    if(!p){
        const auto frame=frame_http(self->received_,true);
        self->finish(frame.state==HttpFrame::State::Complete?frame.status:0);
        self->in_tcp_callback_=false;
        return ERR_OK;
    }
    if(error!=ERR_OK){pbuf_free(p);self->finish(0);self->in_tcp_callback_=false;return ERR_OK;}
    if(self->received_.size()+p->tot_len>MAX_RESPONSE){
        pbuf_free(p);self->finish(0);self->in_tcp_callback_=false;return ERR_OK;
    }
    altcp_recved(pcb,p->tot_len);
    for(pbuf* q=p;q;q=q->next)self->received_.append(static_cast<const char*>(q->payload),q->len);
    pbuf_free(p);
    const auto frame=frame_http(self->received_,false);
    if(frame.state==HttpFrame::State::Complete)self->finish(frame.status);
    else if(frame.state==HttpFrame::State::Invalid)self->finish(0);
    self->in_tcp_callback_=false;
    return ERR_OK;
}
void CloudHttps::error_callback(void* arg,err_t){
    auto* ctx=static_cast<TcpContext*>(arg);
    if(!ctx)return;
    auto* self=ctx->owner;
    if(!self||!self->busy_||self->active_tcp_!=ctx||
       self->generation_!=ctx->generation)return;
    self->pcb_=nullptr; // lwIP has already freed the transport
    self->finish(0);
}
void CloudHttps::release(){
    if(pcb_){
        altcp_arg(pcb_,nullptr);
        altcp_recv(pcb_,nullptr);
        altcp_err(pcb_,nullptr);
        if(altcp_close(pcb_)!=ERR_OK)altcp_abort(pcb_);
        pcb_=nullptr;
    }
    if(active_tcp_){active_tcp_->in_use=false;active_tcp_=nullptr;}
}
void CloudHttps::finish(int status){
    if(!busy_)return;
    const auto frame=frame_http(received_,true);
    // HTTP 200 with truncated, malformed or extra payload is NOT a success.
    if(status && (frame.state!=HttpFrame::State::Complete || frame.status!=status))status=0;
    result_.http_status=status;
    if(frame.state==HttpFrame::State::Complete)result_.body=frame.body;
    if(status==200 && !valid_json_object(result_.body)){
        // 200 with invalid JSON is a failed exchange, never a legal move.
        status=0;
        result_.http_status=0;
    }
    if(status==200){
        const std::string& body=result_.body;
        if(provider_==RemoteProvider::LICHESS) {
            result_.pvs=parse_cloud_pvs(body);
        } else if(provider_==RemoteProvider::STOCKFISH) {
            CloudPV pv;
            if(parse_stockfish_online_response(body,pv))result_.pvs.push_back(pv);
            result_.depth=active_depth_;
        } else {
            // Only the final bestmove response can drive a UCI move.
            std::string type, move;
            if(chess_response_matches_fen(body,expected_fen_) &&
               pv_detail::string_field(body,"type",type) && type=="bestmove" &&
               pv_detail::string_field(body,"move",move) && pv_detail::uci_move(move)) {
                CloudPV pv; pv.move=move;
                // chess-api.com evaluations are from White's perspective.
                // centipawns can be a JSON number or a decimal string.
                std::string cents;
                int cp=0;
                if(pv_detail::integer_field(body,"centipawns",cp)) pv.cp=cp;
                else if(pv_detail::string_field(body,"centipawns",cents)) {
                    char* end=nullptr;const long x=std::strtol(cents.c_str(),&end,10);
                    if(end!=cents.c_str() && *end=='\0' && x>=-1000000 && x<=1000000)
                        pv.cp=static_cast<int>(x);
                } else {
                    const auto key=body.find("\"eval\"");
                    if(key!=std::string::npos){
                        const auto colon=body.find(':',key+6);
                        if(colon!=std::string::npos){
                            char* end=nullptr;
                            const double value=std::strtod(body.c_str()+colon+1,&end);
                            if(end!=body.c_str()+colon+1 && value>=-10000.0 && value<=10000.0)
                                pv.cp=static_cast<int>(value*100.0);
                        }
                    }
                }
                int mate=0;
                if(pv_detail::integer_field(body,"mate",mate)){
                    pv.is_mate=true;pv.mate=mate;
                } else if(pv_detail::string_field(body,"mate",cents)){
                    char* end=nullptr;const long x=std::strtol(cents.c_str(),&end,10);
                    if(end!=cents.c_str() && *end=='\0' && x>=-1000 && x<=1000){pv.is_mate=true;pv.mate=int(x);}
                }
                result_.pvs.push_back(pv);
            }
        }
        if(provider_!=RemoteProvider::STOCKFISH)pv_detail::integer_field(body,"depth",result_.depth);
        if(provider_==RemoteProvider::CHESS_API) {
            std::string debug;
            if(pv_detail::string_field(body,"debug",debug)) {
                const auto stats=parse_stockfish_debug(debug);
                if(stats.complete) {
                    result_.depth=stats.depth;
                    result_.nodes=stats.nodes;
                    result_.nps=stats.nps;
                }
            }
        }
    }
    policy_.finish(status,to_ms_since_boot(get_absolute_time()));
    busy_=false;done_=true;
    // Never abort/close lwIP's PCB from inside its own recv callback;
    // the adapter drains the result, then clear_exchange() releases it.
    if(!in_tcp_callback_)release();
}
void CloudHttps::tick(uint64_t now,uint32_t timeout_ms){if(busy_&&timeout_ms>0&&now-started_ms_>=timeout_ms)finish(0);}
void CloudHttps::cancel(){
    if(busy_){policy_.cancel();busy_=false;done_=false;++generation_;release();}
}
}

namespace picoLichess {
// Only called when the previous response has been consumed by the adapter.
void CloudHttps::clear_exchange(){
    if(busy_)return;
    release();
    std::string().swap(request_);
    std::string().swap(received_);
    std::string().swap(expected_fen_);
    std::string().swap(host_);
    result_=CloudResult{};
    done_=false;
    started_ms_=0;
    active_depth_=-1;
}
}
