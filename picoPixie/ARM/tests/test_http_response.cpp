#include "http_response.hpp"
#include "json_document.hpp"
#include <cassert>
#include <string>
using picoLichess::frame_http;
using picoLichess::HttpFrame;
int main(){
    auto ok=[](const std::string& s,bool eof){return frame_http(s,eof);};
    const std::string a="HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\n{\"a\":1}";
    auto r=ok(a,false);assert(r.state==HttpFrame::State::Complete&&r.status==200&&r.body=="{\"a\":1}");
    assert(ok(a.substr(0,a.size()-2),false).state==HttpFrame::State::Incomplete);
    assert(ok(a.substr(0,a.size()-2),true).state==HttpFrame::State::Invalid);
    assert(ok(a+"{}",true).state==HttpFrame::State::Invalid);
    assert(ok("HTTP/1.1 200 OK\r\nContent-Length: 99\r\n\r\n{}",true).state==HttpFrame::State::Invalid);
    assert(ok("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\n{}",true).state==HttpFrame::State::Invalid);
    assert(ok("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n7\r\n{\"a\":1}\r\n0\r\n\r\n",false).body=="{\"a\":1}");
    assert(ok("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n7\r\n{\"a\":1}\r\n0\r\n",true).state==HttpFrame::State::Invalid);
    assert(ok("HTTP/1.1 404 Not Found\r\n\r\nnot found",true).status==404);
    assert(ok("HTTP/1.1 200 OK\r\n\r\n{}",false).state==HttpFrame::State::Incomplete);
    assert(ok("HTTP/1.1 200 OK\r\n\r\n{}",true).state==HttpFrame::State::Complete);
    assert(picoLichess::valid_json_object(" {\"fen\":\"x\",\"continuation\":[{\"from\":\"e2\"}],\"debug\":\"a\\\"b\"} \n"));
    assert(!picoLichess::valid_json_object("}{\"type\":\"bestmove\"}"));
    assert(!picoLichess::valid_json_object("{\"move\":\"e2e4\"}{\"move\":\"d2d4\"}"));
    assert(!picoLichess::valid_json_object("{\"x\": [1, 2,]}"));
    assert(!picoLichess::valid_json_object("{\"x\": 01}"));
}
