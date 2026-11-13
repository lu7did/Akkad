# picoGenus — Genetic training v0.1.1

## Scope and provenance

`picoGenus/tools/train/` contains `genSample.py`, `genPST.py`, `genNNUE.py`,
`genAudit.py` and their shared model/data utilities. No code is copied from
`picoAlpha/Crypt`; no external repositories or services were accessed.

The .pb contract is **SQLite with a .pb extension**, not protobuf/PyBase. It
follows picoAlpha's `games` and `positions` tables, including the Stockfish
`teacher_*` labels. Inputs open **read-only**; outputs are replaced atomically.

## Usage

```powershell
python -m pip install -r picoGenus/tools/train/requirements.txt
cd picoGenus/tools/train
python genSample.py --in C:\Data\sample_history.pb --out C:\Data\genus.pb --sample 1000 --seed 17
# alternatively: --pct 10  (if both are given, --sample wins)
python genPST.py --in C:\Data\genus.pb --out ..\..\assets\genus_pst.json --poblacion 100 --generaciones 500
python genNNUE.py --in C:\Data\genus.pb --out ..\..\assets\genus_nnue.npy --poblacion 100 --generaciones 500
python genAudit.py --pst ..\..\assets\genus_pst.json --nnue ..\..\assets\genus_nnue.npy --bk C:\Data\bratko_kopec.epd --out ..\..\assets\audit.json
```

`--población` (with accent) and `--poblacion` are accepted. Both training
programs require `--in` and `--out`, default to population 100 and 500
generations, and offer `--max-positions N` (0=all). Help: `--help`.

## Training semantics

* `genSample` samples **individual labeled positions** uniformly without
  replacement, copying their parent game metadata and all teacher labels.
  It does not copy entire games and does not guarantee continuity of plies.
* PST: 4 material coefficients with 11 bits and 30 positional coefficients
  with 6 bits: **224 Gray-encoded bits**. Pawn value is fixed at 100 cp.
  All 30 positional genes have working chess-derived features. The features
  are approximations inspired by the paper and supplied Python reference,
  **not** an exact reproduction of David et al.'s engine. Training compares
  one-ply best moves against `teacher_uci` and uses a Stockfish value RMSE
  regularizer; population selection uses squared correct guesses moderated
  by RMSE. Mutation 0.005, crossover 0.75, elitism 1.
* NNUE: exactly 768 input features, 16 clipped-ReLU neurons, and one
  value output: **12,321 signed INT8 genes** (`.npy`, dtype=int8). White
  perspective; square indexing a1=0; output uses fixed divisor 256 for
  centipawns. Evolution uses elitism 4, uniform crossover, mutation rate
  0.02 with steps in [-4,4]. Teacher cp are converted to white POV.
  Mate values are clipped to +/-2000 cp for supervision.
* Training metrics display every ~10% of generations and include generation,
  population, correct/total, minimum and mean error (cp). For NNUE,
  `correct_100cp` is explicitly defined as absolute error <=100 cp,
  not a chess-move prediction (value-only NNUE has no policy head).
* Large training sets are expensive. Use `genSample.py` to size your data.
  The GA optimizes against the selected full dataset by default and never
  quietly substitutes hardcoded positions or synthetic Stockfish labels.

## Bratko-Kopec audit

The **Bratko-Kopec EPD data itself is not among the supplied attachments**.
No positions or reference solutions have been invented. Supply a genuine
EPD dataset with `--bk path.epd`; each valid line needs a `bm` EPD operation.
`genAudit.py` reports exact-best-move hit rate (1-ply) and mean evaluation
and move-selection milliseconds for each predictor. If EPD rows additionally
supply `ce` in **white-perspective centipawns**, it also computes MAE/RMSE.
Without `ce`, there is no defensible numeric evaluation error against the
Bratko-Kopec answers, so these metrics are `null` (not faked).

## Scientific limitations

The evolved PST is a compact, partial approximate positional evaluator, not
an implementation of all dependencies in the original paper. A deterministic
1-ply best move is not equivalent to deep search. A value-only NNUE cannot
predict a best move without a search; the audit uses 1-ply evaluation. Both
training processes optimize agreement with teacher scores and/or moves;
playing strength and generalization need independent benchmark tests.
No arm firmware, genetic search controller, UCI engine or trained parameters
are included. Actual loading and chess suite tests require python-chess,
which was not installed in the authoring environment.
