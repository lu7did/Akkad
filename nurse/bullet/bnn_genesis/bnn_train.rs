//! Bullet Metal: real binary forward weights, FP32 master parameters, STE gradient.
//! Architecture Chess768 -> 32 shared units x 2 perspectives -> 1, CReLU.
//! v0.1.0 -- independent of GRMP/Bashful.
use bullet_lib::{
    game::inputs::Chess768,
    nn::optimiser::AdamW,
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule,TrainingSteps,lr,wdl},
        settings::LocalSettings,
    },
    value::{ValueTrainerBuilder,loader::sfbinpack::{SfBinpackLoader,TrainingDataEntry,MoveType,PieceType}},
};
use std::env;

const H:usize=32;
const SCALE:f32=16.0;
fn req(k:&str)->String { env::var(k).unwrap_or_else(|_|panic!("missing {k}")) }
fn opt<T:std::str::FromStr>(k:&str,d:T)->T {env::var(k).ok().and_then(|v|v.parse().ok()).unwrap_or(d)}
fn filter(e:&TrainingDataEntry)->bool {
    e.ply>=16 && !e.pos.is_checked(e.pos.side_to_move())
      && e.score.unsigned_abs()<=10000 && e.mv.mtype()==MoveType::Normal
      && e.pos.piece_at(e.mv.to()).piece_type()==PieceType::None
}
fn main(){
    let id=req("BNN_RUN_ID");
    let dataset=req("BNN_TRAIN");
    let out=req("BNN_CHECKPOINTS");
    let end=opt("BNN_SUPERBATCHES",100usize);
    let save=opt("BNN_SAVE_EVERY",10usize);
    let batch=opt("BNN_BATCH",4096usize);
    let batches=opt("BNN_BATCHES_PER_SB",256usize);
    let lr_start=opt("BNN_LR_START",0.001f32);
    let lr_final=opt("BNN_LR_FINAL",0.0001f32);
    let mut trainer=ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(Chess768)
        .save_format(&[
            SavedFormat::id("l0w"), SavedFormat::id("l0b"),
            SavedFormat::id("l1w"), SavedFormat::id("l1b"),
        ])
        .loss_fn(|out,target|out.sigmoid().squared_error(target))
        .build(|builder,stm,ntm| {
            let l0=builder.new_affine("l0",768,H);
            let l1=builder.new_affine("l1",2*H,1);
            // Binary forward: 2*round((clamp(w,-1,1)+1)/2)-1.
            // FauxQuantise backward is identity STE; FP32 master weights remain trainable.
            // Negative weights produce -1; zero and positive produce +1.
            let bounded=l0.weights.clip_pass_through_grad(-1.0,1.0);
            let binary=((bounded+1.0)*0.5).faux_quantise(1.0,true)*2.0-1.0;
            let effective=binary*(1.0/SCALE);
            let a=(effective.matmul(stm)+l0.bias).crelu();
            let b=(effective.matmul(ntm)+l0.bias).crelu();
            l1.forward(a.concat(b))
        });
    let start=opt("BNN_START_SB",1usize);
    if start>1 {
        let checkpoint=req("BNN_RESUME_FROM");
        println!("RESUME {} at superbatch {}",checkpoint,start);
        trainer.load_from_checkpoint(&checkpoint);
    }
    let schedule=TrainingSchedule{
        net_id:id,eval_scale:400.0,
        steps:TrainingSteps{batch_size:batch,batches_per_superbatch:batches,start_superbatch:start,end_superbatch:end},
        wdl_scheduler:wdl::ConstantWDL{value:0.75},
        lr_scheduler:lr::CosineDecayLR{initial_lr:lr_start,final_lr:lr_final,final_superbatch:end},
        save_rate:save,
    };
    let settings=LocalSettings{threads:2,test_set:None,output_directory:Box::leak(out.into_boxed_str()),batch_queue_size:8};
    let loader=SfBinpackLoader::new(&dataset,32,2,filter);
    println!("BNN1 hybrid: Chess768, {} binary units per perspective, FP32 output, +/-1 via STE, weight scale=1/{}",H,SCALE);
    trainer.run(&schedule,&settings,&loader);
}
