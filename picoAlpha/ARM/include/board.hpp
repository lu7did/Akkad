#pragma once
#include <array>
#include <cstdint>
#include <string>
#include <vector>
#include "fixed_vector.hpp"

namespace picoSargon {
struct Move { uint8_t from=0,to=0,promo=0; bool operator==(const Move& x)const{return from==x.from&&to==x.to&&promo==x.promo;} };
struct PositionKey { std::array<uint8_t,64> cells{}; int8_t turn=1; uint8_t castling=15; int8_t ep=-1; bool operator==(const PositionKey& o) const {return cells==o.cells&&turn==o.turn&&castling==o.castling&&ep==o.ep;} };
using MoveList=FixedVector<Move,256>;
class Board {
public:
 std::array<uint8_t,120> cells{};
 int turn=1,ep=-1,halfmove=0,fullmove=1;
 uint8_t castling=15;
 Board(); explicit Board(const std::string& fen);
 void reset(); void set_fen(const std::string& fen);
 int piece(int sq) const; bool attacked(int sq120,int by) const; bool in_check(int color=0) const;
 void pseudo(MoveList& out) const;
 void pseudo(std::vector<Move>& out) const;
 void legal(MoveList& out);
 void legal(std::vector<Move>& out);
 void push(Move m); void pop();
 Move parse(const std::string& uci);
 static std::string notation(Move m);
 bool is_capture(Move m)const;
 PositionKey position_key() const;
 int repetitions()const;
 bool insufficient_material()const;
 bool draw()const;
 size_t history_length() const {return history_.size();}
 private:
 struct Undo {Move move;int turn,ep,halfmove,fullmove;uint8_t castle;int count=0;std::array<uint8_t,4> indices{};std::array<uint8_t,4> values{};};
 FixedVector<Undo,256> undos_;
 FixedVector<PositionKey,256> history_;
 void save(Undo& u,int index);
};
constexpr int at120(int sq) {return 21+(sq/8)*10+sq%8;}
constexpr int from120(int sq){return ((sq/10)-2)*8+(sq%10)-1;}
}
