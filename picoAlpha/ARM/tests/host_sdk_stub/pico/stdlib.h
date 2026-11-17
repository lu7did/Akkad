#pragma once
#include <chrono>
#include <cstdint>
inline uint32_t get_absolute_time(){
 using namespace std::chrono;
 return uint32_t(duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
}
inline uint32_t to_ms_since_boot(uint32_t t){return t;}
inline void tight_loop_contents(){}
inline void stdio_init_all(){}
inline void sleep_ms(unsigned){}
