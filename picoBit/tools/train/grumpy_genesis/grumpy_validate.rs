//! Validates both GRMP0001-quantised and FP32 models against the SAME T77 positions.
use bullet_lib::{
    game::formats::bulletformat::ChessBoard,
    value::loader::sfbinpack::{SfBinpackLoader, TrainingDataEntry, MoveType, PieceType},
};
use bullet_trainer::reader::DataReader;
use std::{env, fs, io::Write, path::Path};

const M: u64=0x3847D12C4B064;
fn material(p:&ChessBoard)->i32 { (*p).into_iter().map(|(pc,_)| {
    let v=((M>>(10*usize::from(pc&7)))&1023) as i32;
    if pc&8==0 {v} else {-v}
}).sum() }
fn bucket(p:&ChessBoard)->usize { ((p.occ.count_ones()-2)/4) as usize }
fn sigmoid(x:f64)->f64 { if x>=0.0 {1.0/(1.0+(-x).exp())} else {let e=x.exp();e/(1.0+e)} }
fn filter(e:&TrainingDataEntry)->bool {
    e.ply>=16 && !e.pos.is_checked(e.pos.side_to_move()) && e.score.unsigned_abs()<=10000
    && e.mv.mtype()==MoveType::Normal && e.pos.piece_at(e.mv.to()).piece_type()==PieceType::None
}
fn features(p:&ChessBoard)->([usize;64],usize) {
    let mut features=[0usize;64];let mut len=0;
    for (pc,square) in (*p).into_iter() {
        let group=6*usize::from(pc&8!=0)+usize::from(pc&7);
        let sq=usize::from(square);
        features[len]=group*16+sq/8;
        features[len+1]=group*16+8+sq%8;
        len+=2;
    }
    (features,len)
}
fn fp32_score(p:&ChessBoard,w:&[f32])->f64 {
    let mut a=[[0.0f64;8];2];
    for j in 0..8 {a[0][j]=f64::from(w[1536+j]);a[1][j]=a[0][j]}
    for (pc,square) in (*p).into_iter() {
        let c=usize::from(pc&8!=0);let kind=usize::from(pc&7);let sq=usize::from(square);
        for (side,f) in [(0,384*c+64*kind+sq),(1,384*(1-c)+64*kind+(sq^56))] {
            let g=f/64;let s=f%64;
            let x=g*16+s/8;let y=g*16+8+s%8;
            for j in 0..8 {a[side][j]+=f64::from(w[x*8+j])+f64::from(w[y*8+j]);}
        }
    }
    let k=bucket(p);let mut result=f64::from(w[1672+k]);
    for i in 0..16 {let v=a[i/8][i%8].clamp(0.0,1.0);result+=v*f64::from(w[1544+i*8+k]);}
    result*400.0+f64::from(material(p))
}
fn quant_score(p:&ChessBoard,w:&[i16])->f64 {
    let mut a=[[0i32;8];2];
    for j in 0..8 {a[0][j]=i32::from(w[1536+j]);a[1][j]=a[0][j]}
    for (pc,square) in (*p).into_iter() {
        let c=usize::from(pc&8!=0);let kind=usize::from(pc&7);let sq=usize::from(square);
        for (side,f) in [(0,384*c+64*kind+sq),(1,384*(1-c)+64*kind+(sq^56))] {
            let g=f/64;let s=f%64;
            let x=g*16+s/8;let y=g*16+8+s%8;
            for j in 0..8 {a[side][j]+=i32::from(w[x*8+j])+i32::from(w[y*8+j]);}
        }
    }
    let k=bucket(p);let mut total=8*i32::from(w[1672+k]);
    for i in 0..16 {total+=a[i/8][i%8].clamp(0,32)*i32::from(w[1544+k*16+i]);}
    (total*400/1024+material(p)) as f64
}
fn quantize(w:&[f32])->Vec<i16> {
    let mut q=vec![0i16;1680];
    for i in 0..1544 {q[i]=(w[i]*32.0).round().clamp(-31.0,32.0) as i16;}
    for b in 0..8 {for i in 0..16 {
        q[1544+b*16+i]=(w[1544+i*8+b]*32.0).round().clamp(-31.0,32.0) as i16;
    }}
    for b in 0..8 {q[1672+b]=(w[1672+b]*128.0).round().clamp(-31.0,32.0) as i16;}
    q
}
fn load_raw(path:&Path)->Vec<f32> {
    let b=fs::read(path).unwrap_or_else(|_|panic!("Unable to read {}",path.display()));
    assert_eq!(b.len(),1680*4,"Expected raw.bin FP32[1680], got {}",b.len());
    b.chunks_exact(4).map(|v|f32::from_le_bytes(v.try_into().unwrap())).collect()
}
fn load_grmp(path:&Path)->Vec<i16> {
    let b=fs::read(path).unwrap();
    assert_eq!(b.len(),1304,"GRMP0001 must be 1304 bytes");
    assert_eq!(&b[0..8],b"GRMP0001");
    assert_eq!(u32::from_le_bytes(b[8..12].try_into().unwrap()),105);
    // SHA256 verification delegated to Python export and final verification.
    let mut q=Vec::with_capacity(1680);
    for part in b[44..].chunks_exact(12) {
        let mut v=0u128;
        for (i,&x) in part.iter().enumerate() {v|=(x as u128)<<(8*i);}
        for i in 0..16 {q.push(((v>>(6*i))&63) as i16-31);}
    }
    q
}
struct Row {name:String, fp:Option<Vec<f32>>, quant:Vec<i16>, mse_fp:f64,mse_int:f64, mae_fp:f64,mae_int:f64}
impl Row {
    fn accumulate(&mut self,p:&ChessBoard,t:f64) {
        if let Some(ref w)=self.fp {let cp=fp32_score(p,w);let d=sigmoid(cp/400.0)-t;self.mse_fp+=d*d;self.mae_fp+=d.abs();}
        let cp=quant_score(p,&self.quant);let d=sigmoid(cp/400.0)-t;
        self.mse_int+=d*d;self.mae_int+=d.abs();
    }
}
fn main() {
    let run=env::var("GR_CHECKPOINTS").unwrap();
    let id=env::var("GR_RUN_ID").unwrap();
    let data=env::var("GR_VALID").unwrap();
    let csv=env::var("GR_VALID_CSV").unwrap();
    let count=env::var("GR_VALID_COUNT").unwrap().parse::<usize>().unwrap();
    let end=env::var("GR_SUPERBATCHES").unwrap().parse::<usize>().unwrap();
    let every=env::var("GR_SAVE_EVERY").unwrap().parse::<usize>().unwrap();
    let mut rows=Vec::new();
    for sb in 1..=end {
        if sb%every!=0 && sb!=end {continue}
        let p=Path::new(&run).join(format!("{id}-{sb}")).join("raw.bin");
        let w=load_raw(&p);
        rows.push(Row{name:format!("{sb}"),quant:quantize(&w),fp:Some(w),
            mse_fp:0.0,mse_int:0.0,mae_fp:0.0,mae_int:0.0});
    }
    if let Ok(reference)=env::var("GR_REFERENCE") {if Path::new(&reference).is_file() {
        rows.push(Row{name:"reference-grumpy".into(),quant:load_grmp(Path::new(&reference)),fp:None,
            mse_fp:0.0,mse_int:0.0,mae_fp:0.0,mae_int:0.0});
    }}
    if let Ok(final_path)=env::var("GR_FINAL_FILE") {if Path::new(&final_path).is_file() {
        rows.push(Row{name:"final-grmp".into(),quant:load_grmp(Path::new(&final_path)),fp:None,
            mse_fp:0.0,mse_int:0.0,mae_fp:0.0,mae_int:0.0});
    }}
    let mut n=0usize;
    let loader=SfBinpackLoader::new(&data,32,2,filter);
    loader.read_chunks(0, |chunk| {
        for p in chunk {
            let t=sigmoid(f64::from(p.score)/400.0);
            for r in &mut rows {r.accumulate(p,t);}
            n+=1;
            if n%100_000==0 {eprintln!("VALID {n}/{count}");}
            if n>=count {return true}
        }
        false
    });
    if n!=count {panic!("validation ended at {n}/{count}");}
    let mut file=fs::File::create(&csv).unwrap();
    writeln!(file,"model,positions,mse_fp32,mse_int6,mae_fp32,mae_int6").unwrap();
    for r in rows {
        let mse=r.mse_int/n as f64;
        let fp=if r.fp.is_some(){format!("{:.10}",r.mse_fp/n as f64)}else{String::new()};
        let fa=if r.fp.is_some(){format!("{:.10}",r.mae_fp/n as f64)}else{String::new()};
        writeln!(file,"{},{},{},{:.10},{},{:.10}",r.name,n,fp,mse,fa,r.mae_int/n as f64).unwrap();
        println!("VALID model={} positions={} mse_fp32={} mse_int6={:.10}",r.name,n,fp,mse);
    }
    println!("Saved {}",csv);
}
