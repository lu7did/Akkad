#include "api_key_url.hpp"
#include <cassert>
#include <string>
int main() {
    using picoLichess::with_api_key;
    const std::string post="/v1";
    assert(with_api_key(post,"")==post);
    assert(with_api_key(post,nullptr)==post);
    assert(with_api_key(post,"abc") == "/v1?key=abc");
    assert(with_api_key("/api/s/v2.php?fen=abc&depth=15","abc") == "/api/s/v2.php?fen=abc&depth=15&key=abc");
    assert(with_api_key("/api/cloud-eval?fen=abc&multiPv=5","abc") == "/api/cloud-eval?fen=abc&multiPv=5&key=abc");
    assert(with_api_key("/v1?existing=yes","a b&c") == "/v1?existing=yes&key=a%20b%26c");
}
