#pragma once
#include "board.hpp"
#include <array>
#include <cstdint>
#include <string>
namespace picoSargon {
class Grumpy {
 std::array<uint8_t,1680> raw_{};
public:
 void load(const std::string& path);
 void load_blob(const uint8_t* data,size_t len);
 int evaluate(const Board& board)const;
};
}
