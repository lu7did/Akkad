#pragma once
#include "tensorflow/lite/micro/micro_common.h"
namespace pico_int8 {
TFLMRegistration RegisterGelu();
TFLMRegistration RegisterReduceProd();
}
