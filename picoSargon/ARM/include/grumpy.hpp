//================================================================================================================*
//* Proyecto sargon-nnue
//* Chess player using different Neural Networks as the game evaluation engine
//*
//* A new mind for the old buddy
//* Created as a learning experience
//*
//* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
//* License: CC AS BY 4.0
//*================================================================================================================*
//* grumpy.hpp
//* Interfaces de intercambio con evaluación de red NNUE 
//*=================================================================================================================*
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
