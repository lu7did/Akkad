#pragma once
#include <string>

namespace picoLichess {
// Append an optional URL-encoded API key to an HTTP request target.
// Empty keys are a no-op, and the first query parameter uses '?'.
inline std::string with_api_key(std::string target, const char* key) {
    if (!key || !*key) return target;
    const char* hex = "0123456789ABCDEF";
    std::string encoded;
    for (unsigned char ch : std::string(key)) {
        if ((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
            (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' ||
            ch == '.' || ch == '~') encoded += static_cast<char>(ch);
        else { encoded += '%'; encoded += hex[ch >> 4]; encoded += hex[ch & 15]; }
    }
    target += (target.find('?') == std::string::npos ? "?key=" : "&key=");
    target += encoded;
    return target;
}
}
