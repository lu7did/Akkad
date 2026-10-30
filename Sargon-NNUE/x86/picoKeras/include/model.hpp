#pragma once
#include <cstddef>
#include <memory>
#include <string>
#include <vector>
#include "board.hpp"
class Evaluator {
 struct Impl;std::unique_ptr<Impl> impl_;
public:
 Evaluator(const std::string&,size_t arena);
 ~Evaluator();
 double eval(const picoSargon::Board&);
};
