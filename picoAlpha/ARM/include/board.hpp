#pragma once
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace picoSargon {
// Mailbox 10x12 board indices: a1=21, h1=28, a8=91, h8=98.
// NNUE features and UCI notation use explicit 0..63 conversions at the boundary.
// Moves use 10x12 mailbox indices (21..98); UCI and NNUE convert only at their boundaries.
struct Move { uint8_t from=0,to=0,promo=0; bool operator==(const Move& x)const{return from==x.from&&to==x.to&&promo==x.promo;} };
struct PositionKey { std::array<uint8_t,64> cells{}; int8_t turn=1; uint8_t castling=15; int8_t ep=-1; bool operator==(const PositionKey& o) const {return cells==o.cells&&turn==o.turn&&castling==o.castling&&ep==o.ep;} };
class Board {
public:
 std::array<uint8_t,120> cells{};
 int turn=1,ep=-1,halfmove=0,fullmove=1;
 uint8_t castling=15;
 Board(); explicit Board(const std::string& fen);
 void reset(); void set_fen(const std::string& fen);
 int piece(int sq) const; bool attacked(int sq120,int by) const; bool in_check(int color=0) const;
 void pseudo(std::vector<Move>& out) const;
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
 // Reserve once per search. Clears logical state without relinquishing capacities.
 void reserve_search(size_t max_plies) {
   undos_.reserve(undos_.size()+max_plies+32);
   history_.reserve(history_.size()+max_plies+32);
   scratch_pseudo_.reserve(256);
 }
 void clear_scratch() {scratch_pseudo_.clear();}
 private:
 struct Undo {Move move;int turn,ep,halfmove,fullmove;uint8_t castle;int count=0;std::array<uint8_t,4> indices{};std::array<uint8_t,4> values{};};
 std::vector<Undo> undos_;
 std::vector<PositionKey> history_;
 std::vector<Move> scratch_pseudo_;
 void save(Undo& u,int index);
};
constexpr int at120(int sq) {return 21+(sq/8)*10+sq%8;}
constexpr int from120(int sq){return ((sq/10)-2)*8+(sq%10)-1;}
}
