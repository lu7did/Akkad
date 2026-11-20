//! Stockfish .binpack -> CSV (Windows/CPU). No Bullet, Metal or PyTorch.
//! Uses the sfbinpack 0.6.4 reader API verified against the Bullet MCTS data reader.
use sfbinpack::{read_chunk_into,ChunkReader};
use std::{env,error::Error,fs::{self,File},io::{BufReader,BufWriter,Write},path::Path};

#[derive(Clone)]
struct Row { id:u64, group:u64, fen:String, ply:u32, uci:String, score:i32, result:i32 }
fn usage() {
    eprintln!("picogen-binpack --in FILE.binpack --out FILE.csv --count 1000000 [--scan-limit 10000000] [--seed 42] [--max-cp 2000] [--min-ply 16]");
    eprintln!("Reads up to scan-limit accepted records and reservoir-samples count. The chunk group is NOT a verified game ID.");
}
fn escape_csv(s:&str)->String {
    if s.chars().any(|c| c==',' || c=='\"' || c=='\n' || c=='\r') {format!("\"{}\"",s.replace('\"',"\"\""))}else{s.to_owned()}
}
fn rand64(state:&mut u64)->u64 {
    // SplitMix64; explicit generator for identical output between platforms.
    *state=state.wrapping_add(0x9e3779b97f4a7c15);
    let mut z=*state;
    z=(z^(z>>30)).wrapping_mul(0xbf58476d1ce4e5b9);
    z=(z^(z>>27)).wrapping_mul(0x94d049bb133111eb);
    z^(z>>31)
}
fn arg(args:&[String],name:&str)->Result<String,Box<dyn Error>> {
    let i=args.iter().position(|a|a==name).ok_or(format!("Missing {name}"))?;
    Ok(args.get(i+1).ok_or(format!("Missing value for {name}"))?.to_string())
}
fn optional<T:std::str::FromStr>(args:&[String],key:&str,default:T)->Result<T,Box<dyn Error>> where <T as std::str::FromStr>::Err:Error+'static {
    if args.iter().any(|a|a==key){Ok(arg(args,key)?.parse::<T>()?)}else{Ok(default)}
}
fn run()->Result<(),Box<dyn Error>> {
    let args:Vec<String>=env::args().collect();
    if args.iter().any(|s|s=="--help"||s=="-h") {usage();return Ok(())}
    let input=arg(&args,"--in")?;let output=arg(&args,"--out")?;
    let want:usize=optional(&args,"--count",1_000_000usize)?;
    let scan:usize=optional(&args,"--scan-limit",want.saturating_mul(10))?;
    let mut rng:u64=optional(&args,"--seed",42u64)?;
    let maxcp:i32=optional(&args,"--max-cp",2000i32)?;
    let minply:u32=optional(&args,"--min-ply",16u32)?;
    if want==0||scan<want||maxcp<1 {return Err("invalid --count, --scan-limit or --max-cp".into())}
    if Path::new(&input)==Path::new(&output){return Err("input and output must differ".into())}
    let file=File::open(&input)?;let mut rd=BufReader::new(file);
    let mut reservoir:Vec<Row>=Vec::with_capacity(want);
    let mut accepted:usize=0;
    let mut chunks:u64=0;
    'chunks:loop{
        let mut bytes=Vec::new();
        if !read_chunk_into(&mut rd,&mut bytes)? {break}
        chunks+=1;
        let mut reader=ChunkReader::default();
        while reader.has_next(&bytes) {
            let entry=reader.next(&bytes);
            if u32::from(entry.ply)<minply||i32::from(entry.score).abs()>10000 {continue}
            let fen=match entry.pos.fen(){Ok(s)=>s,Err(_)=>continue};
            let side=fen.split_whitespace().nth(1).unwrap_or("?");
            if side!="w" && side!="b"{continue}
            accepted+=1;
            let row=Row{id:accepted as u64,group:chunks,fen,ply:u32::from(entry.ply),uci:entry.mv.as_uci(),score:i32::from(entry.score),result:i32::from(entry.result)};
            if reservoir.len()<want {reservoir.push(row)}else{
                let j=(rand64(&mut rng)%(accepted as u64)) as usize;
                if j<want {reservoir[j]=row}
            }
            if accepted>=scan {break 'chunks}
        }
        if chunks%5000==0 {eprintln!("binpack chunks={chunks} eligible={accepted} sampled={}",reservoir.len())}
    }
    if reservoir.len()<want {return Err(format!("Only {} eligible records (requested {want}); no partial CSV published",reservoir.len()).into())}
    reservoir.sort_unstable_by_key(|r|r.id);
    if let Some(parent)=Path::new(&output).parent(){fs::create_dir_all(parent)?}
    let tmp=format!("{output}.partial");
    let mut out=BufWriter::new(File::create(&tmp)?);
    writeln!(out,"record_id,source_chunk,fen,ply,played_uci,score_stm_cp,score_white_cp,result_stm,result_white")?;
    for r in &reservoir {
        let white=r.fen.split_whitespace().nth(1)==Some("w");
        let score=r.score.clamp(-maxcp,maxcp);
        let score_white=if white{score}else{-score};
        let result_white=if white{r.result}else{-r.result};
        writeln!(out,"{},{},{},{},{},{},{},{},{}",r.id,r.group,escape_csv(&r.fen),r.ply,escape_csv(&r.uci),r.score,score_white,r.result,result_white)?;
    }
    out.flush()?;drop(out);
    fs::rename(&tmp,&output)?;
    println!("OK CSV={output} rows={} scanned_eligible={} chunks={} seed={} max_cp={}",reservoir.len(),accepted,chunks,optional(&args,"--seed",42u64)?,maxcp);
    Ok(())
}
fn main(){if let Err(e)=run(){eprintln!("ERROR: {e}");usage();std::process::exit(2)}}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn csv_escape(){assert_eq!(escape_csv("a,b"),"\"a,b\"");assert_eq!(escape_csv("plain"),"plain");}
    #[test] fn random_deterministic(){let mut a=42u64;let mut b=42u64;for _ in 0..1000{assert_eq!(rand64(&mut a),rand64(&mut b));}}
}
