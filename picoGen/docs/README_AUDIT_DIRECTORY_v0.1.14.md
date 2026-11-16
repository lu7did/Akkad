# picoGenus v0.1.14 — audit and audit output directory

Source: exactly the user's uploaded `run_genesis(4).ps1`.

Only two edits to the PowerShell script:
1. Update the version marker to v0.1.14.
2. At MON=4, create the parent directory of the existing configured `AuditOut` if missing, before the existing assertion. All path defaults, CLI parsing, MON behavior, and training calls are preserved byte-for-byte otherwise.

The user observed `AuditOut parent directory does not exist ...\picoGenus\data` **after NNUE had already completed successfully**. The change makes this normal missing-output-directory case recoverable without rerunning PST or NNUE.

Run: `./run_genesis.ps1 --mon 4` to start only the audit stage after applying the patch.

## PST audit of the logged 10 generations

Population 100; dataset 100 positions; generations 10.
Error min 77 -> 76 means best correct count 23 -> 24; mean error 81.36 -> 80.65.
The implementation `genPST.py` uses fitness = hits**2 (as in the provided example), elitism 1, uniform crossover probability 0.75, bit mutation probability 0.005 and a seeded PRNG. Expected flips per 224-bit offspring: 224*0.005=1.12; probability no mutation in a given offspring ~(1-0.005)**224 ~= 0.326. This is not evidence of a defective operator.
The reference `gen_pst_core.py` declares 34 evolved coefficients but its evaluation does not use 11 of them (66 neutral bits). This faithfully reflects the original supplied Python example but is not a complete use of all article terms. Do not silently change those terms or genetic operators.
The train set contains only 100 positions and there is no train/validation split in the current trainer; these data alone cannot distinguish plateau, limited model expressiveness, local optimum or small-sample saturation. Run more generations and held-out evaluation before adjusting genetic parameters; preserve reference behavior unless explicitly authorized.

No algorithmic change is included in this patch.
