picoKeras v0.1.6 - TFLM installer repair

Extract at Akkad root. This patch replaces scripts/install_TFLM.ps1, which v0.1.5 did NOT update.

From sargon-NNUE/x86/picoKeras/scripts execute: .\install_TFLM.ps1
This script installs/checks GNU Make and Unix shell tools before calling upstream create_tflm_tree.py, and reuses existing TFLM checkout.
The build and network-conversion scripts remain independent and untouched.
Windows TFLM library compilation is not validated in this environment.
