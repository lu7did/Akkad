#pragma once
#include <thread>
#include <cstddef>
#include <cstdint>
inline void multicore_launch_core1_with_stack(void(*fn)(), uint32_t*,size_t){std::thread(fn).detach();}
