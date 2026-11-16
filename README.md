# picoAlpha/MCTSP perspective audit, v0.1.39

Diagnostic plus a single UCI score-sign fix; **no changes to engine search, checkpoint format, teacher labels, or trainer**.

- `teacher.py` stores `info['score'].pov(board.turn)` and `teacher_value=tanh(teacher_cp/400)`; both are side-to-move.
- `train.py` trains value head directly on `teacher_value`, and feature encoding is side-to-move relative.
- `mcts_nnue.py` returns a tanh in side-to-move POV, backs up value with sign reversal per ply, and selects children with negative child mean.
- `worker.py` encodes `score_cp` as side-to-move. UCI also requires engine/side-to-move POV, so `uci.py` MUST NOT flip the score for black. v0.1.39 corrects this reporting defect.
- The alternating 63-/45-ply games appear deterministic; use varied openings to rule out identical replays.

Run `python picoAlpha/tools/train/audit_perspective.py --db "C:/path/to/database.pb"` to verify all numeric labels in-place **without writing**. This validates internal formula consistency, not provenance of a third-party dataset. A checkpoint trained before a semantic change cannot be reinterpreted safely.

Run `python -m unittest discover -s nurse/tests -p test_mctsp_perspective_contract_v0139.py -v` to test symmetric relative encoding and winning decisions from both colors.
