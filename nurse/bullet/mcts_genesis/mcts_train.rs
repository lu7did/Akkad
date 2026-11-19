//! Standalone two-head policy+value trainer on Bullet compiler/trainer/Metal.
//! Architecturally exact picoAlpha: 780x16 ReLU; 64 FROM, 64 TO and 1 VALUE.
#[path = "mcts_picoalpha_bullet/mcts_data.rs"]
mod mcts_data;
use mcts_data::{MctsBinpackReader,Sample,INPUTS,HIDDEN,NNZ};
use bullet_trainer::{
 model::{InitSettings,ModelDefinition,ModelInputs,ModelInputsMapper,ModelWeights,SavedFormat},
 optimiser::{Optimiser,adam::{AdamW,AdamWParams}},
 reader::ReadMapLoader,
 run::{TrainingSchedule,TrainingSteps,train},
};
use bullet_lib::{nn::ExecutionContext, trainer::schedule::lr::{self,LrScheduler}, value::save::save_to_checkpoint};
use bullet_gpu::runtime::Device;
use std::env;
fn req(k:&str)->String{env::var(k).unwrap_or_else(|_|panic!("Missing {k}"))}
fn opt<T:std::str::FromStr>(k:&str,d:T)->T{env::var(k).ok().and_then(|s|s.parse().ok()).unwrap_or(d)}
fn main(){
 let id=req("MCTS_ID");let file=req("MCTS_TRAIN");let out=req("MCTS_CHECKPOINTS");
 let end=opt("MCTS_SUPERBATCHES",100usize);let save=opt("MCTS_SAVE_EVERY",10usize);
 let batch=opt("MCTS_BATCH",4096usize);let bps=opt("MCTS_BATCHES_PER_SB",128usize);
 let start=opt("MCTS_START_SB",1usize);let policy_weight=opt("MCTS_POLICY_WEIGHT",0.01f32);
 let blend=opt("MCTS_CP_BLEND",1.0f32);let initial=opt("MCTS_LR_START",0.001f32);let final_lr=opt("MCTS_LR_FINAL",0.0001f32);
 assert!(policy_weight>0.0&&policy_weight.is_finite()&&(0.0..=1.0).contains(&blend));
 let inputs=ModelInputs::default().add_sparse("features",(INPUTS,1),NNZ)
     .add_dense("value_target",(1,1)).add_dense("from_target",(64,1)).add_dense("to_target",(64,1));
 let definition=ModelDefinition::build(&inputs,|builder,(((features,value_target),from_target),to_target)|{
     let embed=builder.new_weights("embed",(HIDDEN,INPUTS),InitSettings::Normal{mean:0.0,stdev:0.02});
     let value=builder.new_weights("value",(1,HIDDEN),InitSettings::Normal{mean:0.0,stdev:0.02});
     let from=builder.new_weights("from",(64,HIDDEN),InitSettings::Normal{mean:0.0,stdev:0.02});
     let to=builder.new_weights("to",(64,HIDDEN),InitSettings::Normal{mean:0.0,stdev:0.02});
     let h=embed.matmul(features).relu();
     let raw_value=value.matmul(h);
     let from_logits=from.matmul(h);let to_logits=to.matmul(h);
     // Training sigmoid(2*x) is (tanh(x)+1)/2, so deployment uses exact tanh(raw_value).
     let lv=(raw_value*2.0).sigmoid().squared_error(value_target);
     let lf=from_logits.softmax_crossentropy_loss(from_target).reduce_sum_rows();
     let lt=to_logits.softmax_crossentropy_loss(to_target).reduce_sum_rows();
     let loss=(lv+policy_weight*(lf+lt)).reduce_sum_batch();
     (Some(loss),vec![("value".into(),raw_value),("from".into(),from_logits),("to".into(),to_logits)])
 });
 let weights=ModelWeights::new(&definition,198273612);
 let dev=Device::<ExecutionContext>::new(0).expect("Cannot initialize Bullet execution device");
 let mut optim=Optimiser::<_,AdamW<_>>::new(definition,weights,dev,AdamWParams::default()).expect("Cannot initialize optimizer");
 if start>1 {let ck=req("MCTS_RESUME_FROM");optim.load_from_checkpoint(&format!("{ck}/optimiser_state")).expect("Cannot resume optimizer+weights");println!("RESUME from {ck} at SB={start}");}
 let mapper=ModelInputsMapper::build(&inputs,|row:&Sample,_,(((idx,val),from),to)|{
     idx.copy_from_slice(&row.indices);
     val[0]=row.value;
     from[usize::from(row.src)]=1.0;
     to[usize::from(row.dst)]=1.0;
 });
 let format=[SavedFormat::id("embed"),SavedFormat::id("value"),SavedFormat::id("from"),SavedFormat::id("to")];
 println!("MCTS BULLET | 780x16 -> from[64],to[64],value[1] | value mse + policy_weight={policy_weight} * (CEfrom+CEto), blend={blend}");
 train(&mut optim,TrainingSchedule{
     steps:TrainingSteps{batch_size:batch,batches_per_superbatch:bps,start_superbatch:start,end_superbatch:end},
     lr_schedule:lr::CosineDecayLR{initial_lr:initial,final_lr,final_superbatch:end}.boxed(),
     log_rate:32,track_grad_norms:false,
 },ReadMapLoader::new(MctsBinpackReader{path:file,blend,chunk_samples:batch*4},mapper,2),|_,_,_|{},|optim,step|{
     let sb=step.superbatch();
     if sb%save==0||sb==step.final_superbatch(){
         let target=format!("{out}/{id}-{sb}");
         save_to_checkpoint(optim,&format,&target);
         println!("CHECKPOINT {target}");
     }
 }).expect("Bullet multi-head training failed");
}
