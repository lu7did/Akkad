//! T77 validation in host Rust, same sparse+head math as exported PANNI8 INT8.
#[path = "mcts_picoalpha_bullet/mcts_data.rs"]
mod mcts_data;
use mcts_data::{MctsBinpackReader,Sample,INPUTS,HIDDEN};
use bullet_trainer::reader::DataReader;
use std::{env,fs,io::Write,path::Path};
const N:usize=INPUTS*HIDDEN+HIDDEN+64*HIDDEN*2;
fn req(k:&str)->String{env::var(k).unwrap_or_else(|_|panic!("Missing {k}"))}
fn num(k:&str,d:usize)->usize{env::var(k).ok().and_then(|s|s.parse().ok()).unwrap_or(d)}
fn get_raw(p:&Path)->Vec<f32>{
 let data=fs::read(p).unwrap_or_else(|e|panic!("Cannot read {}: {e}",p.display()));
 assert_eq!(data.len(),N*4,"Wrong raw weight size");
 data.chunks_exact(4).map(|v|f32::from_le_bytes(v.try_into().unwrap())).collect()
}
fn quant(w:&[f32])->(Vec<i8>,[f64;4]){
 let lengths=[INPUTS*HIDDEN,HIDDEN,64*HIDDEN,64*HIDDEN];
 let mut q=Vec::with_capacity(N);let mut scales=[0.0;4];let mut at=0;
 for (k,&len) in lengths.iter().enumerate(){
     let a=&w[at..at+len];
     let scale=(a.iter().fold(0.0f32,|acc,&v|acc.max(v.abs()))/127.0).max(1e-12);
     scales[k]=f64::from(scale);
     for &x in a {q.push((x/scale).round().clamp(-127.0,127.0) as i8);}
     at+=len;
 }
 (q,scales)
}
fn sigmoid(x:f64)->f64{if x>=0.0{1.0/(1.0+(-x).exp())}else{let z=x.exp();z/(1.0+z)}}
fn predict(s:&Sample,w:&[i8],sc:&[f64;4])->(f64,usize,usize,f64){
 let mut h=[0i32;HIDDEN];
 for &f in &s.indices{if f<0{continue}let base=f as usize*HIDDEN;
   for j in 0..HIDDEN {h[j]+=i32::from(w[base+j]);}}
 for x in &mut h {*x=(*x).max(0)}
 let mut pos=INPUTS*HIDDEN;
 let raw=(0..HIDDEN).map(|j|i32::from(w[pos+j])*h[j]).sum::<i32>() as f64*sc[0]*sc[1];
 pos+=HIDDEN;
 let mut logits_from=[0.0f64;64];let mut logits_to=[0.0f64;64];
 for i in 0..64{for j in 0..HIDDEN{logits_from[i]+=f64::from(i32::from(w[pos+j*64+i])*h[j]);}}
 pos+=64*HIDDEN;
 for i in 0..64{for j in 0..HIDDEN{logits_to[i]+=f64::from(i32::from(w[pos+j*64+i])*h[j]);}}
 for i in 0..64{logits_from[i]*=sc[0]*sc[2];logits_to[i]*=sc[0]*sc[3];}
 let best_from=logits_from.iter().enumerate().max_by(|a,b|a.1.total_cmp(b.1)).unwrap().0;
 let best_to=logits_to.iter().enumerate().max_by(|a,b|a.1.total_cmp(b.1)).unwrap().0;
 let ce=|logits:&[f64;64],index:usize|{
   let top=logits.iter().fold(f64::NEG_INFINITY,|a,&b|a.max(b));
   top+(logits.iter().map(|v|(v-top).exp()).sum::<f64>()).ln()-logits[index]
 };
 (raw.tanh(),best_from,best_to,ce(&logits_from,usize::from(s.src))+ce(&logits_to,usize::from(s.dst)))
}
struct Row{name:String,w:Vec<i8>,sc:[f64;4],v:f64,ce:f64,from:usize,to:usize}
fn main(){
 let id=req("MCTS_ID");let root=req("MCTS_CHECKPOINTS");let dest=req("MCTS_VALID_CSV");let count=num("MCTS_VALID_COUNT",100000);
 let end=num("MCTS_SUPERBATCHES",100);let rate=num("MCTS_SAVE_EVERY",10);
 let mut rows=Vec::new();for sb in 1..=end {if sb%rate!=0&&sb!=end{continue}
   let raw=get_raw(&Path::new(&root).join(format!("{id}-{sb}/raw.bin")));
   let (w,sc)=quant(&raw);rows.push(Row{name:sb.to_string(),w,sc,v:0.0,ce:0.0,from:0,to:0});
 }
 let blend=env::var("MCTS_CP_BLEND").unwrap_or("1.0".into()).parse::<f32>().unwrap();
 let reader=MctsBinpackReader{path:req("MCTS_VALID"),blend,chunk_samples:8192};
 let mut n=0usize;
 reader.read_chunks(0,|chunk|{for sample in chunk{
   let t=2.0*f64::from(sample.value)-1.0;
   for row in &mut rows {
     let (v,f,to,ce)=predict(sample,&row.w,&row.sc);
     row.v+=(v-t)*(v-t);row.ce+=ce;
     row.from+=usize::from(f==usize::from(sample.src));
     row.to+=usize::from(to==usize::from(sample.dst));
   }
   n+=1;if n%100000==0{eprintln!("VALID {n}/{count}");}
   if n>=count{return true}
 }false});
 assert_eq!(n,count);
 let mut csv=fs::File::create(dest).expect("Cannot create CSV");
 writeln!(csv,"model,positions,value_mse,policy_ce,from_acc,to_acc,objective").unwrap();
 let pw=env::var("MCTS_POLICY_WEIGHT").unwrap_or("0.01".into()).parse::<f64>().unwrap();
 for row in rows {
   let vm=row.v/n as f64;let ce=row.ce/n as f64;
   writeln!(csv,"{},{},{:.12},{:.12},{:.12},{:.12},{:.12}",row.name,n,vm,ce,row.from as f64/n as f64,row.to as f64/n as f64,vm/4.0+pw*ce).unwrap();
   println!("VALID model={} value_mse={vm:.8} policy_ce={ce:.8} from_accuracy={:.4} to_accuracy={:.4}",row.name,row.from as f64/n as f64,row.to as f64/n as f64);
 }
}
