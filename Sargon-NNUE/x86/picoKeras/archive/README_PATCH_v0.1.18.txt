picoKeras v0.1.18 - warnings in project code
Changes: src/main.cpp only.
* send()/recv(): use auto to retain platform return type (ssize_t / int).
* send() limits chunk length to INT_MAX; uses size_t conversion for cursor/buffer.
* recv(): casts buffer length to int and received byte count to size_t.
* UCI version/banner v0.1.18.
* No third-party TFLM/FlatBuffers source changed, no suppression of external warnings.
Checks: g++ C++17 -Wall -Wextra -Wpedantic -Wconversion compiled main.cpp and board.cpp without warnings; board tests BOARD TESTS OK. MSVC full TFLM build not verified.
