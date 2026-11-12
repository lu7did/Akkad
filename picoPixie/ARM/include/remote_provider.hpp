#pragma once
#include <string>
namespace picoLichess {
enum class RemoteProvider { CHESS_API, LICHESS, STOCKFISH };
inline const char* provider_name(RemoteProvider p){
    switch(p){case RemoteProvider::CHESS_API:return "chess-api";
              case RemoteProvider::LICHESS:return "lichess";
              case RemoteProvider::STOCKFISH:return "stockfish";}
    return "unknown";
}
// Parsing is intentionally limited to full HTTPS endpoints; reject non-HTTPS.
inline bool split_https_url(const std::string& url,std::string& host,std::string& path){
    if(url.compare(0,8,"https://")!=0)return false;
    const auto at=url.find('/',8);
    host=url.substr(8,at==std::string::npos?std::string::npos:at-8);
    path=at==std::string::npos?"/":url.substr(at);
    return !host.empty()&&host.find(':')==std::string::npos&&
           host.find('?')==std::string::npos&&path.find('#')==std::string::npos;
}
}
