#pragma once
#include "board.hpp"
#include <string>
namespace picoLichess {
// Some chess-api FEN validators reject positions with a legally available
// en-passant capture. Removing the EP square would change the legal moves.
// Such positions must use a provider that accepts the complete position.
inline bool chess_api_ep_unsupported(const picoSargon::Board& b) {
    return b.position_key().ep >= 0;
}
inline std::string board_fen(const picoSargon::Board& b, bool capturable_ep_only=false){
    std::string result;
    const char* symbols=" pnbrqk";
    for(int rank=7;rank>=0;--rank){
        int blanks=0;
        for(int file=0;file<8;++file){
            int p=b.piece(rank*8+file);
            if(!p){++blanks;continue;}
            if(blanks){result+=char('0'+blanks);blanks=0;}
            char c=symbols[p>0?p:-p];
            if(p>0)c=char(c-'a'+'A');
            result+=c;
        }
        if(blanks)result+=char('0'+blanks);
        if(rank)result+='/';
    }
    result+=b.turn>0?" w ":" b ";
    if(!b.castling)result+='-';
    else {
        if(b.castling&1)result+='K';
        if(b.castling&2)result+='Q';
        if(b.castling&4)result+='k';
        if(b.castling&8)result+='q';
    }
    result+=' ';
    // The local Board records the EP target after every double pawn push.
    // Chess-API's FEN validation may reject an uncapturable EP target.
    // Use the board's existing legal-position key to canonicalize EP only
    // for the Chess-API transport; preserve Lichess's original FEN.
    const int ep = capturable_ep_only ? b.position_key().ep : b.ep;
    if(ep<0)result+='-';
    else {result+=char('a'+ep%8);result+=char('1'+ep/8);}
    result+=' ';
    result+=std::to_string(b.halfmove);result+=' ';
    result+=std::to_string(b.fullmove);
    return result;
}
}
