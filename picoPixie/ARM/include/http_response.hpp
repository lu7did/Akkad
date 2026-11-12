#pragma once
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <string>

namespace picoLichess {
// HTTP response framing: never expose bytes from another frame or a truncated body.
struct HttpFrame {
    enum class State { Incomplete, Complete, Invalid };
    State state = State::Incomplete;
    int status = 0;
    std::string body;
};
namespace http_detail {
inline std::string trim(std::string s) {
    auto isspace_ascii=[](unsigned char c){return c==' '||c=='\t';};
    size_t a=0,b=s.size();
    while(a<b && isspace_ascii(static_cast<unsigned char>(s[a])))++a;
    while(b>a && isspace_ascii(static_cast<unsigned char>(s[b-1])))--b;
    return s.substr(a,b-a);
}
inline std::string lower(std::string s){
    for(char& c:s)if(c>='A'&&c<='Z')c=char(c-'A'+'a');
    return s;
}
inline bool decimal(const std::string& s,size_t& value){
    if(s.empty())return false;
    size_t v=0;
    for(unsigned char c:s){
        if(c<'0'||c>'9'||v>(std::numeric_limits<size_t>::max()-(c-'0'))/10)return false;
        v=v*10+c-'0';
    }
    value=v;return true;
}
inline bool hex(const std::string& s,size_t& value){
    if(s.empty())return false;
    size_t v=0;
    for(unsigned char c:s){
        int x=(c>='0'&&c<='9')?c-'0':(c>='a'&&c<='f')?c-'a'+10:(c>='A'&&c<='F')?c-'A'+10:-1;
        if(x<0||v>(std::numeric_limits<size_t>::max()-static_cast<unsigned>(x))/16)return false;
        v=v*16+static_cast<unsigned>(x);
    }
    value=v;return true;
}
}
inline HttpFrame frame_http(const std::string& data,bool eof,size_t max_body=12288){
    HttpFrame result;
    auto invalid=[&](){result.state=HttpFrame::State::Invalid;result.body.clear();return result;};
    const size_t hdr=data.find("\r\n\r\n");
    if(hdr==std::string::npos){
        if(eof||data.size()>2048)return invalid();
        return result;
    }
    if(hdr>2048)return invalid();
    size_t line_end=data.find("\r\n");
    if(line_end==std::string::npos||line_end>hdr)return invalid();
    const std::string first=data.substr(0,line_end);
    if(first.compare(0,5,"HTTP/")!=0)return invalid();
    const size_t code_pos=first.find(' ');
    if(code_pos==std::string::npos||code_pos+4>first.size())return invalid();
    const std::string code=first.substr(code_pos+1,3);
    size_t parsed_code=0;
    if(!http_detail::decimal(code,parsed_code)||parsed_code<100||parsed_code>599)return invalid();
    result.status=int(parsed_code);
    bool chunked=false,have_length=false;
    size_t content_length=0;
    for(size_t p=line_end+2;p<hdr;){
        const size_t e=data.find("\r\n",p);
        if(e==std::string::npos||e>hdr)return invalid();
        const size_t colon=data.find(':',p);
        if(colon==std::string::npos||colon>=e)return invalid();
        const std::string key=http_detail::lower(http_detail::trim(data.substr(p,colon-p)));
        const std::string value=http_detail::lower(http_detail::trim(data.substr(colon+1,e-colon-1)));
        if(key=="transfer-encoding"){
            if(value!="chunked")return invalid();
            chunked=true;
        }else if(key=="content-length"){
            size_t length=0;
            if(!http_detail::decimal(value,length)||length>max_body)return invalid();
            if(have_length&&content_length!=length)return invalid();
            have_length=true;content_length=length;
        }
        p=e+2;
    }
    if(chunked&&have_length)return invalid();
    const size_t start=hdr+4;
    if(chunked){
        size_t p=start;
        std::string body;
        for(;;){
            const size_t e=data.find("\r\n",p);
            if(e==std::string::npos){if(eof)return invalid();return result;}
            if(e-p>64)return invalid();
            const std::string line=data.substr(p,e-p);
            const size_t semi=line.find(';');
            size_t n=0;
            if(!http_detail::hex(http_detail::trim(line.substr(0,semi)),n))return invalid();
            p=e+2;
            if(n==0){
                // Empty trailers are normal; reject unsupported trailers rather than
                // mistaking them for bytes from the next response.
                if(data.size()<p+2){if(eof)return invalid();return result;}
                if(data.compare(p,2,"\r\n")!=0)return invalid();
                if(data.size()!=p+2)return invalid();
                result.body=std::move(body);
                result.state=HttpFrame::State::Complete;
                return result;
            }
            if(n>max_body-body.size())return invalid();
            if(n>data.size()-p){if(eof)return invalid();return result;}
            if(data.size()-p-n<2){if(eof)return invalid();return result;}
            if(data.compare(p+n,2,"\r\n")!=0)return invalid();
            body.append(data,p,n);
            p+=n+2;
        }
    }
    if(have_length){
        if(data.size()-start<content_length){if(eof)return invalid();return result;}
        if(data.size()-start>content_length)return invalid();
        result.body=data.substr(start,content_length);
        result.state=HttpFrame::State::Complete;
        return result;
    }
    if(data.size()-start>max_body)return invalid();
    if(!eof)return result;
    result.body=data.substr(start);
    result.state=HttpFrame::State::Complete;
    return result;
}
}
