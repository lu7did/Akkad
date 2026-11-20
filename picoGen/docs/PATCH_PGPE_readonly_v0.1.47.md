# picoGen PGPE v0.1.47 — EvoTorch ReadOnlyTensor

Base: Akkad commit `24b107e9d689438dbbb1a47c386bf4a12443052a`, plus patches v0.1.44, v0.1.45 and v0.1.46.

## Observed failure
`TypeError: The contents of a ReadOnlyTensor cannot be modified` during `population_fitness()` called from EvoTorch 0.6.1 on Intel XPU. The `+=` accumulator is an in-place operation and can receive the read-only tensor subclass.

## Fix
- Cast EvoTorch's read-only *subclass* to base PyTorch Tensor using `.as_subclass(torch.Tensor)` without changing storage or mutating the original tensor.
- Use `total = total + ...` rather than `total += ...` for loss accumulation.
- Maintain identical FP32 genome, objective sigmoid MSE, [0,1] Clipped ReLU, samples, device, and Nurse output.
- Include regression tests emulating ReadOnlyTensor's in-place protection. Full EvoTorch/XPU integration was not available locally.

## Execution after extracting at Akkad root

The failed explicit MON 7 run may have archived prior NNUE artifacts. To replay MON 7:

```powershell
.\run_genesis_binpack.ps1 --mon 7
```

Execute from `picoGen/tools/train`; MON 7 uses the existing T79/T77 CSVs and preserves PST. The first PGPE step begins a fresh run when MON 7 is explicitly requested.
