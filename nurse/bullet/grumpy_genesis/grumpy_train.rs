//! GRMP0001-compatible factorised 192x8, dual perspective, 8 output buckets.
//! Training target is the neural residual: teacher_cp(STM)-fixed_material(STM).
use bullet_lib::{
    game::{
        formats::bulletformat::ChessBoard,
        inputs::SparseInputType,
        outputs::OutputBuckets,
    },
    nn::optimiser::AdamW,
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr, wdl},
        settings::LocalSettings,
    },
    value::{
        ValueTrainerBuilder,
        loader::{LoadableDataType, GameResult, sfbinpack::{SfBinpackLoader, TrainingDataEntry, MoveType, PieceType}},
    },
};
use bullet_trainer::reader::DataReader;
use std::env;

const MATERIAL_PACKED: u64 = 0x3847D12C4B064;
fn material(pos: &ChessBoard) -> i32 {
    (*pos).into_iter().map(|(piece, _)| {
        let kind = (piece & 7) as usize;
        let value = ((MATERIAL_PACKED >> (10 * kind)) & 1023) as i32;
        if piece & 8 == 0 { value } else { -value }
    }).sum()
}
#[derive(Clone, Copy)]
struct GrumpyPosition { board: ChessBoard, residual: i16 }
impl LoadableDataType for GrumpyPosition {
    fn score(&self) -> i16 { self.residual }
    fn result(&self) -> GameResult {
        match self.board.result { 0=>GameResult::Loss, 1=>GameResult::Draw, _=>GameResult::Win }
    }
}
#[derive(Clone, Copy, Default)]
struct Grumpy192;
impl SparseInputType for Grumpy192 {
    type RequiredDataType = GrumpyPosition;
    fn num_inputs(&self) -> usize { 192 }
    fn max_active(&self) -> usize { 64 }
    fn map_features<F: FnMut(usize, usize)>(&self, pos: &GrumpyPosition, mut f: F) {
        for (piece, square) in pos.board.into_iter() {
            let c = usize::from(piece & 8 != 0);
            let pc = usize::from(piece & 7);
            let sq = usize::from(square);
            let stm = 384*c + 64*pc + sq;
            let ntm = 384*(1-c) + 64*pc + (sq ^ 56);
            let factor = |feature: usize| {
                let group = feature / 64;
                let square = feature % 64;
                (group * 16 + square / 8, group * 16 + 8 + square % 8)
            };
            let (sr, sc) = factor(stm);
            let (nr, nc) = factor(ntm);
            f(sr, nr);
            f(sc, nc);
        }
    }
    fn shorthand(&self) -> String { "grmp192".to_owned() }
    fn description(&self) -> String { "GRMP0001 rank/file factorisation".to_owned() }
}
#[derive(Clone, Copy, Default)]
struct GrumpyBuckets;
impl OutputBuckets<GrumpyPosition> for GrumpyBuckets {
    const BUCKETS: usize = 8;
    fn bucket(&self, p: &GrumpyPosition) -> u8 {
        let n = p.board.occ.count_ones();
        assert!((2..=32).contains(&n));
        ((n - 2)/4) as u8
    }
}
#[derive(Clone)]
struct ResidualLoader<T: Fn(&TrainingDataEntry)->bool + Clone + Send + Sync + 'static> {
    inner: SfBinpackLoader<T>
}
impl<T: Fn(&TrainingDataEntry)->bool + Clone + Send + Sync + 'static> DataReader<GrumpyPosition> for ResidualLoader<T> {
    fn read_chunks<F: FnMut(&[GrumpyPosition])->bool>(&self, skip_count: usize, mut f: F) {
        self.inner.read_chunks(skip_count, |chunk| {
            let transformed: Vec<_> = chunk.iter().map(|board| {
                let residual = (i32::from(board.score) - material(board))
                    .clamp(i16::MIN as i32, i16::MAX as i32) as i16;
                GrumpyPosition { board: *board, residual }
            }).collect();
            f(&transformed)
        });
    }
}
fn required(name: &str) -> String { env::var(name).unwrap_or_else(|_|panic!("Missing {name}")) }
fn opt<T: std::str::FromStr>(name: &str, default: T) -> T { env::var(name).ok().and_then(|s|s.parse().ok()).unwrap_or(default) }
fn filter(e: &TrainingDataEntry) -> bool {
    e.ply >= 16
        && !e.pos.is_checked(e.pos.side_to_move())
        && e.score.unsigned_abs() <= 10000
        && e.mv.mtype() == MoveType::Normal
        && e.pos.piece_at(e.mv.to()).piece_type() == PieceType::None
}
fn main() {
    let id=required("GR_RUN_ID");
    let data=required("GR_TRAIN");
    let out=required("GR_CHECKPOINTS");
    let end=opt("GR_SUPERBATCHES",100usize);
    let save=opt("GR_SAVE_EVERY",10usize);
    let batch=opt("GR_BATCH",4096usize);
    let bps=opt("GR_BATCHES_PER_SUPERBATCH",256usize);
    let lr0=opt("GR_LR_START",0.001f32);
    let lr1=opt("GR_LR_FINAL",0.0001f32);
    let mut trainer=ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(Grumpy192)
        .output_buckets(GrumpyBuckets)
        .save_format(&[
            SavedFormat::id("l0w"), SavedFormat::id("l0b"),
            SavedFormat::id("l1w"), SavedFormat::id("l1b"),
        ])
        .loss_fn(|output,target| output.sigmoid().squared_error(target))
        .build(|builder,stm,ntm,buckets| {
            let l0=builder.new_affine("l0",192,8);
            let l1=builder.new_affine("l1",16,8);
            let a=l0.forward(stm).crelu();
            let b=l0.forward(ntm).crelu();
            l1.forward(a.concat(b)).select(buckets)
        });
    let start=opt("GR_START_SB",1usize);
    if start>1 {
        let source=required("GR_RESUME_FROM");
        println!("RESUME checkpoint={} start_superbatch={}",source,start);
        trainer.load_from_checkpoint(&source);
    }
    let schedule=TrainingSchedule {
        net_id:id,
        eval_scale:400.0,
        steps:TrainingSteps {batch_size:batch,batches_per_superbatch:bps,start_superbatch:start,end_superbatch:end},
        wdl_scheduler:wdl::ConstantWDL {value:0.0},
        lr_scheduler:lr::CosineDecayLR {initial_lr:lr0,final_lr:lr1,final_superbatch:end},
        save_rate:save,
    };
    let settings=LocalSettings {threads:2,test_set:None,output_directory:Box::leak(out.into_boxed_str()),batch_queue_size:8};
    let loader=ResidualLoader {inner:SfBinpackLoader::new(&data,32,2,filter)};
    println!("GRMP-FP32 | 192x8 dual, 8 buckets, residual teacher, no quantization in training");
    trainer.run(&schedule,&settings,&loader);
}
