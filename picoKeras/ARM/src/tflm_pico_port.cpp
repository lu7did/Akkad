#include "tensorflow/lite/micro/debug_log.h"
#include "tensorflow/lite/micro/micro_time.h"
#include "pico/time.h"
#include <cstdio>
#include <cstdarg>

extern "C" void DebugLog(const char* format, va_list args) {
  std::vprintf(format, args);
}
extern "C" int DebugVsnprintf(char* buffer, size_t capacity,
                               const char* format, va_list args) {
  return std::vsnprintf(buffer, capacity, format, args);
}
namespace tflite { namespace micro {
uint32_t ticks_per_second() { return 1000000U; }
uint32_t GetCurrentTimeTicks() { return static_cast<uint32_t>(time_us_64()); }
} }
