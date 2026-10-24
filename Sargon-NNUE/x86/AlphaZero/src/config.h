#pragma once
// Akkad AlphaZero-X86: configuration defaults (overridden by CLI, then UCI).
// Paths may be absolute or relative to the process working directory.
namespace az_config {
inline constexpr const char* kUciName = "AlphaZero-X86 0.1.2";
inline constexpr const char* kUciAuthor = "Dr. Pedro E. Colla";
inline constexpr const char* kWeightsFile = ""; // required unless supplied externally
inline constexpr const char* kBackend = "onnx-dml"; // "eigen" for CPU
inline constexpr const char* kBackendOptions = "gpu=0";
inline constexpr int kSimulations = 1000; // MCTS simulation budget
inline constexpr int kMaxTreeNodes = 0; // 0 = unlimited; includes root expansion
inline constexpr int kTMaxMs = 10000; // search time budget
inline constexpr int kTimeoutMs = 60000; // absolute per-search ceiling; 0 = disabled
inline constexpr double kCpuct = 1.5;
inline constexpr int kVerbose = 1;
} // namespace az_config
