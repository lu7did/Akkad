//! Stockfish binpack -> exact picoAlpha 780 sparse features + recorded from/to labels.
//! `mv` is a recorded move, NOT a Stockfish MultiPV/MCTS policy distribution.
use std::{fs::File,io::BufReader};
use bullet_trainer::reader::DataReader;
use sfbinpack::{ChunkReader,read_chunk_into,TrainingDataEntry};

pub const INPUTS:usize=780;
pub const NNZ:usize=37;
pub const HIDDEN:usize=16;
#[derive(Clone)]
pub struct Sample {pub indices:[i32;NNZ],pub src:u8,pub dst:u8,pub value:f32}

pub fn orient(sq:usize,white:bool)->usize {
    let a8=(7-sq/8)*8+sq%8;
    if white {a8} else {63-a8}
}
fn coord(file:u8,rank:u8)->Option<usize>{
    if !(b'a'..=b'h').contains(&file)||!(b'1'..=b'8').contains(&rank){return None}
    Some(usize::from(rank-b'1')*8+usize::from(file-b'a'))
}

pub fn from_fen_move(fen:&str,uci:&str,score:i16,result:i16,blend:f32)->Option<Sample>{
    let p:Vec<_>=fen.split_whitespace().collect();
    if p.len()<4||!(p[1]=="w"||p[1]=="b")||uci.len()<4{return None}
    let white=p[1]=="w";
    let b=uci.as_bytes();
    let from=coord(b[0],b[1])?;
    let mut to=coord(b[2],b[3])?;
    // Stockfish binpack encodes castling as king captures rook (e1h1 -> e1g1).
    // Detect only when the source square holds the king and target is home rook.
    let mut f=[-1i32;NNZ];let mut n=0usize;
    let mut king_from=false;
    let ranks:Vec<_>=p[0].split('/').collect();if ranks.len()!=8{return None}
    for (r,rankstr) in ranks.iter().enumerate(){
        let mut file=0usize;
        for c in rankstr.chars(){
            if let Some(d)=c.to_digit(10){file+=d as usize;continue}
            if file>=8{return None}
            let pt=match c.to_ascii_lowercase(){'p'=>0,'n'=>1,'b'=>2,'r'=>3,'q'=>4,'k'=>5,_=>return None};
            let sq=(7-r)*8+file;
            if sq==from&&pt==5 {king_from=true;}
            let own=c.is_ascii_uppercase()==white;
            let kind=pt+if own{0}else{6};
            if n>=NNZ{return None}
            f[n]=(kind*64+orient(sq,white)) as i32;n+=1;file+=1;
        }
        if file!=8{return None}
    }
    if king_from&&from/8==to/8&&((from%8) as i32-(to%8) as i32).unsigned_abs()>1 {
        to=from/8*8+if to%8>from%8{6}else{2};
    }
    let our_rights=if white{['K','Q']}else{['k','q']};
    let opp_rights=if white{['k','q']}else{['K','Q']};
    for (k,right) in our_rights.into_iter().chain(opp_rights).enumerate(){
        if p[2].contains(right){if n>=NNZ{return None}f[n]=(768+k) as i32;n+=1;}
    }
    if p[3]!="-"{
        let ep=p[3].as_bytes();if ep.len()!=2{return None}
        let ep_file=usize::from(ep[0].checked_sub(b'a')?);
        if ep_file>=8||n>=NNZ{return None}
        f[n]=(772+if white{ep_file}else{7-ep_file}) as i32;
    }
    let cp=(f32::from(score)/400.0).tanh();
    let outcome=f32::from(result).clamp(-1.0,1.0);
    let v=blend.clamp(0.0,1.0)*cp+(1.0-blend.clamp(0.0,1.0))*outcome;
    Some(Sample{indices:f,src:orient(from,white) as u8,dst:orient(to,white) as u8,value:0.5*(v+1.0)})
}

pub fn from_entry(e:&TrainingDataEntry,blend:f32)->Option<Sample>{
    if e.ply<16||e.score.unsigned_abs()>10000{return None}
    let fen=e.pos.fen().ok()?;
    from_fen_move(&fen,&e.mv.as_uci(),e.score,e.result,blend)
}

#[derive(Clone)]
pub struct MctsBinpackReader{pub path:String,pub blend:f32,pub chunk_samples:usize}
impl DataReader<Sample> for MctsBinpackReader {
    fn read_chunks<F:FnMut(&[Sample])->bool>(&self,skip_count:usize,mut callback:F){
        let mut skipped=0usize;
        let mut block_index=0u64;
        let mut deliver=|data:&mut Vec<Sample>|->bool{
            // Deterministic in-memory shuffle: nearby plies aren't kept in order.
            // Entire blocks are shuffled BEFORE skip_count to make resume repeatable.
            block_index+=1;
            let mut rng=0x9e3779b97f4a7c15u64^block_index;
            for i in (1..data.len()).rev(){
                rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;
                let j=(rng%((i+1) as u64)) as usize;
                data.swap(i,j);
            }
            let skip=skip_count.saturating_sub(skipped).min(data.len());
            skipped+=skip;
            let stop=skip<data.len()&&callback(&data[skip..]);
            data.clear();stop
        };
        loop {
            let f=File::open(&self.path).unwrap_or_else(|e|panic!("Cannot open {}: {e}",self.path));
            let mut reader=BufReader::new(f);
            let mut decoded=Vec::with_capacity(self.chunk_samples);
            let mut chunks=0usize;let mut accepted=0usize;
            loop {
                let mut bytes=Vec::new();
                if !read_chunk_into(&mut reader,&mut bytes).expect("Corrupt SF binpack") {break}
                chunks+=1;
                let mut cr=ChunkReader::default();
                while cr.has_next(&bytes){
                    let entry=cr.next(&bytes);
                    if let Some(row)=from_entry(&entry,self.blend){
                        accepted+=1;decoded.push(row);
                        if decoded.len()>=self.chunk_samples&&deliver(&mut decoded){return}
                    }
                }
            }
            if !decoded.is_empty()&&deliver(&mut decoded){return}
            if chunks==0||accepted==0 {panic!("No valid samples in {}",self.path)}
        }
    }
}

#[cfg(test)]
mod tests {
 use super::*;
 #[test]fn starting_features(){let s=from_fen_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","e2e4",0,0,1.0).unwrap();assert_eq!(s.src,52);assert_eq!(s.dst,36);assert_eq!(s.indices.iter().filter(|x|**x>=0).count(),36);}
 #[test]fn reversed_move(){let s=from_fen_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1","e7e5",0,0,1.0).unwrap();assert_eq!(s.src,51);assert_eq!(s.dst,35);}
}
