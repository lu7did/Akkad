//! Independent host-side inference for exact exported BNN1 format; T77 evaluation.
use bullet_lib::{
    game::{formats::bulletformat::ChessBoard,inputs::{Chess768,SparseInputType}},
    value::loader::sfbinpack::{SfBinpackLoader,TrainingDataEntry,MoveType,PieceType},
};
use bullet_trainer::reader::DataReader;
use std::{env,fs,io::Write,path::Path};
const H:usize=32;
const N:usize=768*H+H+2*H+1;
const SCALE:f64=16.0;
const BIN_BYTES:usize=768*H/8;
fn filter(e:&TrainingDataEntry)->bool {
    e.ply>=16 && !e.pos.is_checked(e.pos.side_to_move()) && e.score.unsigned_abs()<=10000
      && e.mv.mtype()==MoveType::Normal && e.pos.piece_at(e.mv.to()).piece_type()==PieceType::None
}
fn sigmoid(x:f64)->f64 {if x>=0.0 {1.0/(1.0+(-x).exp())}else{let q=x.exp();q/(1.0+q)}}
fn raw(path:&Path)->Vec<f32>{
    let b=fs::read(path).unwrap_or_else(|e|panic!("{}: {}",path.display(),e));
    assert_eq!(b.len(),N*4,"unexpected raw FP32 weight count");
    b.chunks_exact(4).map(|x|f32::from_le_bytes(x.try_into().unwrap())).collect()
}
fn exact_file(path:&Path)->Vec<f32>{
    let b=fs::read(path).expect("missing final BNN1");
    assert_eq!(b.len(),64+BIN_BYTES+97*4,"BNN1 byte count");
    assert_eq!(&b[..8],b"BULBNN01");
    assert_eq!(u32::from_le_bytes(b[8..12].try_into().unwrap()),768);
    assert_eq!(u32::from_le_bytes(b[12..16].try_into().unwrap()),32);
    assert_eq!(f32::from_le_bytes(b[16..20].try_into().unwrap()),16.0);
    assert_eq!(u32::from_le_bytes(b[20..24].try_into().unwrap()),97);
    let mut weights=Vec::with_capacity(N);
    for i in 0..768*H {weights.push(if b[64+i/8]&(1<<(i%8))!=0 {1.0} else {-1.0});}
    let trailer=&b[64+BIN_BYTES..];
    weights.extend(trailer.chunks_exact(4).map(|x|f32::from_le_bytes(x.try_into().unwrap())));
    assert_eq!(weights.len(),N);
    weights
}
// Matrix l0w layout: 768 features x H channel (as Bullet raw.bin).
fn inference(board:&ChessBoard,w:&[f32],already_binary:bool)->f64{
    let mut a=[[0f64;H];2];
    for i in 0..H {a[0][i]=f64::from(w[768*H+i]);a[1][i]=a[0][i]}
    Chess768.map_features(board,|stm,ntm|{
        for (pers,feat) in [(0,stm),(1,ntm)] {
            for j in 0..H {
                let weight=w[feat*H+j];
                let s=if already_binary {f64::from(weight)} else if weight>=0.0 {1.0} else {-1.0};
                a[pers][j]+=s/SCALE;
            }
        }
    });
    let mut out=f64::from(w[768*H+H+H*2]);
    for i in 0..2*H {
        let v=a[i/H][i%H].clamp(0.0,1.0);
        out+=v*f64::from(w[768*H+H+i]);
    }
    out*400.0
}
struct Row {id:String,w:Vec<f32>,exact:bool,sum:f64,mae:f64}
fn main(){
    let ckpts=env::var("BNN_CHECKPOINTS").unwrap();
    let id=env::var("BNN_RUN_ID").unwrap();
    let data=env::var("BNN_VALID").unwrap();
    let csv=env::var("BNN_VALID_CSV").unwrap();
    let count=env::var("BNN_VALID_COUNT").unwrap().parse::<usize>().unwrap();
    let end=env::var("BNN_SUPERBATCHES").unwrap().parse::<usize>().unwrap();
    let every=env::var("BNN_SAVE_EVERY").unwrap().parse::<usize>().unwrap();
    let mut rows=Vec::new();
    for sb in 1..=end {if sb%every!=0 && sb!=end {continue}
        let p=Path::new(&ckpts).join(format!("{id}-{sb}")).join("raw.bin");
        rows.push(Row{id:format!("{sb}"),w:raw(&p),exact:false,sum:0.0,mae:0.0});
    }
    if let Ok(file)=env::var("BNN_FINAL_FILE") {rows.push(Row{id:"final-bnn".into(),w:exact_file(Path::new(&file)),exact:true,sum:0.0,mae:0.0});}
    let loader=SfBinpackLoader::new(&data,32,2,filter);
    let mut n=0usize;
    loader.read_chunks(0,|chunk|{
        for board in chunk {
            let target=sigmoid(f64::from(board.score)/400.0);
            for row in &mut rows {
                let score=inference(board,&row.w,row.exact);
                let d=sigmoid(score/400.0)-target;
                row.sum+=d*d;row.mae+=d.abs();
            }
            n+=1;
            if n%100000==0 {eprintln!("VALID {n}/{count}");}
            if n>=count {return true}
        }
        false
    });
    assert_eq!(n,count,"validation dataset shorter than requested");
    let mut f=fs::File::create(csv).unwrap();
    writeln!(f,"model,positions,mse_bnn,mae_bnn").unwrap();
    for row in rows {
        let mse=row.sum/n as f64;
        writeln!(f,"{},{},{:.10},{:.10}",row.id,n,mse,row.mae/n as f64).unwrap();
        println!("VALID model={} n={} mse_bnn={:.10}",row.id,n,mse);
    }
}
