cmake_minimum_required(VERSION 3.20)
project(picoKeras VERSION 0.1.17 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(TFLM_INCLUDE "" CACHE PATH "Root containing tensorflow/lite/micro/micro_interpreter.h")
set(TFLM_LIBRARY "" CACHE FILEPATH "Prebuilt TFLM static library (.lib or .a)")
if(NOT TFLM_INCLUDE OR NOT EXISTS "${TFLM_INCLUDE}/tensorflow/lite/micro/micro_interpreter.h")
 message(FATAL_ERROR "Set -DTFLM_INCLUDE to TFLM source/include root (tensorflow/lite/micro/micro_interpreter.h)")
endif()
if(NOT TFLM_LIBRARY OR NOT EXISTS "${TFLM_LIBRARY}")
 message(FATAL_ERROR "Set -DTFLM_LIBRARY to a built TFLM static library (.lib or .a)")
endif()
add_executable(picoKeras src/main.cpp src/model.cpp src/board.cpp src/int8_extra_ops.cpp)
# The installed TFLM revision stores the generated schema under micro/schema.
# Resolve the matching header from the exported tree or the exact local clone.
set(_tflm_include_dirs "${TFLM_INCLUDE}")
set(_upstream_tflm_root "${CMAKE_CURRENT_SOURCE_DIR}/third_party/tflite-micro")
set(_schema_relative "tensorflow/lite/micro/schema/schema_generated.h")
if(EXISTS "${TFLM_INCLUDE}/${_schema_relative}")
  message(STATUS "TFLM schema: exported tree")
elseif(EXISTS "${_upstream_tflm_root}/${_schema_relative}")
  list(APPEND _tflm_include_dirs "${_upstream_tflm_root}")
  message(STATUS "TFLM schema: local upstream checkout")
else()
  message(FATAL_ERROR "Missing ${_schema_relative} in TFLM tree and local clone")
endif()

# Backwards-compatible include for source code still using the pre-micro path.
# This is a forwarding header only; it uses the schema from the installed revision.
set(_compat_root "${CMAKE_CURRENT_BINARY_DIR}/tflm-compat")
file(MAKE_DIRECTORY "${_compat_root}/tensorflow/lite/schema")
file(WRITE "${_compat_root}/tensorflow/lite/schema/schema_generated.h"
     "#pragma once\n#include <tensorflow/lite/micro/schema/schema_generated.h>\n")
list(INSERT _tflm_include_dirs 0 "${_compat_root}")

set(_dependency_roots
  "${TFLM_INCLUDE}"
  "${TFLM_INCLUDE}/third_party"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/tflite-micro"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/tflite-micro/tensorflow/lite/micro/tools/make/downloads"
)
# FlatBuffers is needed by micro_interpreter.h and schema_generated.h.
set(_flatbuffers_include "")
foreach(_dep_root IN LISTS _dependency_roots)
  foreach(_candidate
      "${_dep_root}/third_party/flatbuffers/include"
      "${_dep_root}/flatbuffers/include"
      "${_dep_root}/flatbuffers")
    if(EXISTS "${_candidate}/flatbuffers/flatbuffers.h")
      set(_flatbuffers_include "${_candidate}")
      break()
    endif()
  endforeach()
  if(_flatbuffers_include)
    break()
  endif()
endforeach()
if(NOT _flatbuffers_include)
  message(FATAL_ERROR
    "FlatBuffers header flatbuffers/flatbuffers.h not found in the TFLM source tree "
    "or upstream downloads. This is a header availability issue, not proof "
    "that TFLM is uninstalled. Check third_party/tflite-micro/tensorflow/lite/micro/tools/make/downloads/flatbuffers/include.")
endif()
list(APPEND _tflm_include_dirs "${_flatbuffers_include}")
foreach(_dep_root IN LISTS _dependency_roots)
  foreach(_relative "third_party/gemmlowp" "gemmlowp"
                    "third_party/kissfft" "kissfft"
                    "third_party/ruy" "ruy")
    if(IS_DIRECTORY "${_dep_root}/${_relative}")
      list(APPEND _tflm_include_dirs "${_dep_root}/${_relative}")
    endif()
  endforeach()
endforeach()
list(REMOVE_DUPLICATES _tflm_include_dirs)
target_include_directories(picoKeras PRIVATE include ${_tflm_include_dirs})
message(STATUS "TFLM include directories: ${_tflm_include_dirs}")
target_link_libraries(picoKeras PRIVATE "${TFLM_LIBRARY}")
if(WIN32)
 target_link_libraries(picoKeras PRIVATE ws2_32)
endif()
if(MSVC)
 target_compile_options(picoKeras PRIVATE /W4 /EHsc)
else()
 target_compile_options(picoKeras PRIVATE -Wall -Wextra -Wpedantic)
endif()
set_target_properties(picoKeras PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
