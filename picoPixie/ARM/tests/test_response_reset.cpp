#include "cloud_pv.hpp"
#include <cassert>
#include <string>

// Regression scenario: two separate HTTPS responses have distinct PVs.
// Previous implementation forgot to clear received_ between exchanges.
static std::string body(const std::string& r) {
    auto at = r.find("\r\n\r\n");
    return at == std::string::npos ? std::string() : r.substr(at + 4);
}
int main() {
    std::string received;
    const std::string first = "HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n"
        "{\"depth\":65,\"pvs\":[{\"moves\":\"e2e4 e7e5\",\"cp\":20}]}";
    const std::string second = "HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n"
        "{\"depth\":30,\"pvs\":[{\"moves\":\"b1c3 b8c6\",\"cp\":12}]}";
    received += first;
    auto p1=picoLichess::parse_cloud_pvs(body(received));
    assert(p1.size()==1 && p1[0].move=="e2e4");
    // Required production behavior at the beginning of the next request:
    received.clear();
    received += second;
    auto p2=picoLichess::parse_cloud_pvs(body(received));
    assert(p2.size()==1 && p2[0].move=="b1c3");
}
