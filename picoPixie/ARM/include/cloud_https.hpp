#pragma once
#include <cstdint>
#include <string>
#include "cloud_policy.hpp"
#include "config.hpp"
#include "remote_provider.hpp"
#include "cloud_pv.hpp"
#include "lwip/altcp.h"
#include "lwip/ip_addr.h"
#include "lwip/pbuf.h"
struct altcp_tls_config;
namespace picoLichess {
struct CloudResult {int http_status=0,depth=0; uint64_t nodes=0,nps=0; std::string body; std::vector<CloudPV> pvs;};
class CloudHttps {
public:
    explicit CloudHttps(CloudPolicy& policy):policy_(policy){}
    bool init();
    bool start(RemoteProvider provider,const config::EngineSettings& settings,const std::string& fen,uint64_t now,uint32_t interval_ms);
    void tick(uint64_t now,uint32_t timeout_ms);
    void cancel();
    void clear_exchange();
    bool done()const{return done_;}
    bool busy()const{return busy_;}
    const CloudResult& result()const{return result_;}
    const std::string& raw_response()const{return received_;}
private:
    static void dns_callback(const char*,const ip_addr_t*,void*);
    static err_t connected_callback(void*,altcp_pcb*,err_t);
    static err_t recv_callback(void*,altcp_pcb*,struct pbuf*,err_t);
    static void error_callback(void*,err_t);
    void on_dns(const ip_addr_t*,uint64_t generation);
    struct DnsContext { CloudHttps* owner=nullptr; uint64_t generation=0; bool in_use=false; };
    // DNS callbacks cannot be cancelled by lwIP. Bounded persistent contexts
    // prevent both callback reuse and unbounded allocations on timeouts.
    DnsContext dns_contexts_[16]{};
    struct TcpContext { CloudHttps* owner=nullptr; uint64_t generation=0; bool in_use=false; };
    TcpContext tcp_contexts_[16]{};
    TcpContext* active_tcp_=nullptr;
    void finish(int status);
    void release();
    CloudPolicy& policy_;
    altcp_pcb* pcb_=nullptr;
    altcp_tls_config* tls_config_=nullptr;
    bool busy_=false,done_=false;
    bool in_tcp_callback_=false;
    uint64_t started_ms_=0;
    uint64_t generation_=0; // per-request DNS correlation; never reused
    std::string request_,received_,expected_fen_,host_;
    RemoteProvider provider_=RemoteProvider::CHESS_API;
    int active_depth_=-1;
    CloudResult result_{};
};
}
