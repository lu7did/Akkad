#pragma once
#include <cctype>
#include <cstdint>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <string>
#include <vector>
#include "json_document.hpp"

namespace picoLichess {
// The Lichess cloud API uses white's perspective for cp/mate.
struct CloudPV { std::string move; int cp=0; int mate=0; bool is_mate=false; };
namespace pv_detail {
inline size_t skip(const std::string& s,size_t p){while(p<s.size()&&std::isspace(static_cast<unsigned char>(s[p])))++p;return p;}
inline bool integer_field(const std::string& s,const char* name,int& out){
    const std::string key=std::string("\"")+name+"\"";
    size_t p=s.find(key);if(p==std::string::npos)return false;
    p=skip(s,s.find(':',p)+1);if(p>=s.size())return false;
    size_t e=p;if(s[e]=='-')++e;
    while(e<s.size()&&std::isdigit(static_cast<unsigned char>(s[e])))++e;
    if(e==p||(e==p+1&&s[p]=='-'))return false;
    const long long n=std::strtoll(s.substr(p,e-p).c_str(),nullptr,10);
    if(n<std::numeric_limits<int>::min()||n>std::numeric_limits<int>::max())return false;
    out=static_cast<int>(n);return true;
}
inline bool string_field(const std::string& s,const char* name,std::string& out){
    const std::string key=std::string("\"")+name+"\"";
    auto p=s.find(key);if(p==std::string::npos)return false;
    p=s.find(':',p);if(p==std::string::npos)return false;
    p=skip(s,p+1);if(p>=s.size()||s[p]!='"')return false;
    const auto e=s.find('"',p+1);if(e==std::string::npos)return false;
    out=s.substr(p+1,e-p-1);return true;
}
inline bool bool_field(const std::string& s,const char* name,bool& out){
    const std::string key=std::string("\"")+name+"\"";
    auto p=s.find(key);if(p==std::string::npos)return false;
    p=s.find(':',p+key.size());if(p==std::string::npos)return false;
    p=skip(s,p+1);
    if(s.compare(p,4,"true")==0){out=true;return true;}
    if(s.compare(p,5,"false")==0){out=false;return true;}
    return false;
}
inline bool float_field(const std::string& s,const char* name,double& out){
    const std::string key=std::string("\"")+name+"\"";
    auto p=s.find(key);if(p==std::string::npos)return false;
    p=s.find(':',p+key.size());if(p==std::string::npos)return false;
    p=skip(s,p+1);
    if(p>=s.size())return false;
    char* end=nullptr;
    const double value=std::strtod(s.c_str()+p,&end);
    if(end==s.c_str()+p||!std::isfinite(value)||value < -10000 || value > 10000)return false;
    out=value;return true;
}
inline bool uci_move(const std::string& m){
    return (m.size()==4||m.size()==5)&&m[0]>='a'&&m[0]<='h'&&
        m[2]>='a'&&m[2]<='h'&&m[1]>='1'&&m[1]<='8'&&
        m[3]>='1'&&m[3]<='8'&&
        (m.size()==4||m[4]=='q'||m[4]=='r'||m[4]=='b'||m[4]=='n');
}
inline int64_t score(const CloudPV& pv){
    if(!pv.is_mate)return pv.cp;
    // A forced win outranks all normal cp; faster mates rank higher.
    // A forced loss ranks below all cp; delaying mate ranks higher.
    return pv.mate>0?1000000000LL-pv.mate:-1000000000LL-pv.mate;
}
}
// Stockfish UCI diagnostics delivered by Chess-API as a JSON "debug" string.
// Keep the last complete info record when the provider includes several lines.
struct RemoteUciStats {
    int depth=0;
    uint64_t nodes=0;
    uint64_t nps=0;
    bool complete=false;
};
inline bool parse_positive_u64(const std::string& token,uint64_t& output){
    if(token.empty())return false;
    uint64_t n=0;
    for(unsigned char c:token){
        if(c<'0'||c>'9')return false;
        const unsigned digit=c-'0';
        if(n>(std::numeric_limits<uint64_t>::max()-digit)/10)return false;
        n=n*10+digit;
    }
    output=n;
    return true;
}
inline RemoteUciStats parse_stockfish_debug(const std::string& debug){
    RemoteUciStats final_stats;
    RemoteUciStats candidate;
    bool in_info=false,got_depth=false,got_nodes=false,got_nps=false;
    std::string pending;
    // The JSON debug string may have literal or JSON-escaped newlines.
    auto finish_record=[&](){
        if(in_info&&got_depth&&got_nodes&&got_nps){
            candidate.complete=true;
            final_stats=candidate;
        }
    };
    std::string key;
    for(size_t p=0;p<=debug.size();){
        while(p<debug.size() && (std::isspace(static_cast<unsigned char>(debug[p])) ||
              (debug[p]=='\\' && p+1<debug.size() && debug[p+1]=='n'))){
            if(debug[p]=='\\')p+=2;else ++p;
        }
        if(p>=debug.size())break;
        const size_t start=p;
        while(p<debug.size()&&!std::isspace(static_cast<unsigned char>(debug[p]))&&
              !(debug[p]=='\\'&&p+1<debug.size()&&debug[p+1]=='n'))++p;
        const std::string token=debug.substr(start,p-start);
        if(token=="info"){
            finish_record();
            candidate={};in_info=true;got_depth=got_nodes=got_nps=false;key.clear();
            continue;
        }
        if(!in_info)continue;
        if(!key.empty()){
            uint64_t number=0;
            if(parse_positive_u64(token,number)){
                if(key=="depth" && number<=256){candidate.depth=static_cast<int>(number);got_depth=true;}
                if(key=="nodes"){candidate.nodes=number;got_nodes=true;}
                if(key=="nps"){candidate.nps=number;got_nps=true;}
            }
            key.clear();
            continue;
        }
        if(token=="depth"||token=="nodes"||token=="nps")key=token;
    }
    finish_record();
    return final_stats;
}
// Chess-API responses must be a single JSON document with the same FEN.
// Reject concatenation, truncation and leading garbage such as `}{`.
inline bool single_json_object(const std::string& s){return valid_json_object(s);}
// stockfish.online v2: strict success + bestmove, evaluation in pawns,
// mate (if present) in full moves from White's perspective. Never assume
// nodes/nps: the service does not report them in this response format.
inline bool parse_stockfish_online_response(const std::string& json,CloudPV& pv){
    if(!single_json_object(json))return false;
    bool success=false;
    if(!pv_detail::bool_field(json,"success",success)||!success)return false;
    std::string best;
    if(!pv_detail::string_field(json,"bestmove",best)||best.compare(0,8,"bestmove")!=0)
        return false;
    const auto begin=best.find_first_not_of(' ',8);
    if(begin==std::string::npos)return false;
    const auto end=best.find(' ',begin);
    const auto move=best.substr(begin,end==std::string::npos?std::string::npos:end-begin);
    if(!pv_detail::uci_move(move))return false;
    CloudPV parsed;parsed.move=move;
    int mate=0;
    // stockfish.online may encode mate as a JSON string (e.g. "mate":"2")
    // even when evaluation is null. Parse both documented wire shapes.
    bool has_mate=pv_detail::integer_field(json,"mate",mate);
    if(!has_mate){
        std::string text_mate;
        if(pv_detail::string_field(json,"mate",text_mate) && !text_mate.empty()){
            char* end=nullptr;
            const long value=std::strtol(text_mate.c_str(),&end,10);
            if(end!=text_mate.c_str() && *end=='\0' && value>=-1000 && value<=1000){
                mate=static_cast<int>(value);
                has_mate=true;
            }
        }
    }
    if(has_mate){
        parsed.is_mate=true;parsed.mate=mate;
    } else {
        double evaluation=0;
        if(!pv_detail::float_field(json,"evaluation",evaluation))return false;
        parsed.cp=static_cast<int>(std::round(evaluation*100.0));
    }
    pv=parsed;return true;
}
inline bool chess_response_matches_fen(const std::string& json,const std::string& requested_fen){
    if(!single_json_object(json))return false;
    std::string actual_fen;
    return pv_detail::string_field(json,"fen",actual_fen)&&actual_fen==requested_fen;
}
// Read only the pvs array: prevents accidentally matching fields outside it.
inline std::vector<CloudPV> parse_cloud_pvs(const std::string& json){
    std::vector<CloudPV> out;
    auto a=json.find("\"pvs\"");if(a==std::string::npos)return out;
    a=json.find('[',a);if(a==std::string::npos)return out;
    for(size_t p=a+1;p<json.size()&&out.size()<32;){
        p=pv_detail::skip(json,p);
        if(p>=json.size()||json[p]==']')break;
        if(json[p]!= '{')return {};
        const auto e=json.find('}',p+1);if(e==std::string::npos)return {};
        const std::string object=json.substr(p,e-p+1);
        std::string pvline;CloudPV pv;
        const bool has_cp=pv_detail::integer_field(object,"cp",pv.cp);
        pv.is_mate=pv_detail::integer_field(object,"mate",pv.mate);
        if((has_cp!=pv.is_mate)&&pv_detail::string_field(object,"moves",pvline)){
            pv.move=pvline.substr(0,pvline.find(' '));
            if(pv_detail::uci_move(pv.move))out.push_back(pv);
        }
        p=pv_detail::skip(json,e+1);
        if(p<json.size()&&json[p]==',')++p;
        else if(p<json.size()&&json[p]!=']')return {};
    }
    return out;
}
// Pass only legal PVs. random_value is supplied by platform RNG.
inline bool choose_best_tie(const std::vector<CloudPV>& legal,int turn,
                            uint32_t random_value,CloudPV& chosen,size_t& ties){
    ties=0;
    if(legal.empty()||(turn!=1&&turn!=-1))return false;
    int64_t best=turn==1?std::numeric_limits<int64_t>::min():std::numeric_limits<int64_t>::max();
    for(const auto& p:legal){const auto s=pv_detail::score(p);if((turn==1&&s>best)||(turn==-1&&s<best))best=s;}
    for(const auto& p:legal)if(pv_detail::score(p)==best)++ties;
    if(!ties)return false;
    size_t pick=random_value%ties;
    for(const auto& p:legal)if(pv_detail::score(p)==best){if(pick--==0){chosen=p;return true;}}
    return false;
}
}
