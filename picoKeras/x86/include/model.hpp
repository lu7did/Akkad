#pragma once
#include <cstddef>
#include <memory>
#include <string>
#include <vector>
#include "board.hpp"
class Evaluator {
 struct Impl;std::unique_ptr<Impl> impl_;
public:
 Evaluator(const std::string&,size_t arena=0);
 ~Evaluator();
 void configure(const std::string& input_op,const std::string& output_op);
 double eval(const picoSargon::Board&);
 std::vector<double> eval_batch(const std::vector<picoSargon::Board>&);
};
