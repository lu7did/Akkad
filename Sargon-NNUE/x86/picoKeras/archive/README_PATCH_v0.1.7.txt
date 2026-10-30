picoKeras x86 v0.1.7 - TFLM installer repository root

Install at Akkad/; this patch updates only sargon-NNUE/x86/picoKeras/scripts/install_TFLM.ps1.

Fix: Upstream create_tflm_tree.py invokes `make -f tensorflow/lite/micro/tools/make/Makefile` relative to its working directory. PowerShell formerly invoked it from picoKeras/scripts, which lacks that relative Makefile. The installer now runs it from third_party/tflite-micro with try/finally restoring the prior working directory, validates the Makefile and output header, and reuses the existing repository.

Run independently:
  cd Akkad/sargon-NNUE/x86/picoKeras/scripts
  ./install_TFLM.ps1

Network conversion and picoKeras.exe build are still separate.

Note: Fix verified by inspection against upstream generator; complete TFLM MSVC build was not executed here.
