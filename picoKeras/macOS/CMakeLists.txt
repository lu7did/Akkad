cmake_minimum_required(VERSION 3.20)
project(picoKeras VERSION 0.2.14 LANGUAGES CXX)

if(NOT APPLE)
  message(FATAL_ERROR "picoKeras/macOS requires macOS")
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
get_filename_component(PK_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(PK_SRC "${PK_ROOT}/src")
set(TFLITE_ROOT "" CACHE PATH "TensorFlow checkout containing tensorflow/lite/CMakeLists.txt")
if(NOT EXISTS "${TFLITE_ROOT}/tensorflow/lite/CMakeLists.txt")
  message(FATAL_ERROR "TFLITE_ROOT must be a valid TensorFlow source checkout; run tools/macOS/build.sh")
endif()

# macOS uses the same source and TFLite backend as Debian; Apple Silicon CPU
# optimizations are handled by TFLite's XNNPACK, Accelerate and the toolchain.
option(PICOKERAS_XNNPACK "Enable optimized XNNPACK CPU delegate" ON)
# KleidiAI is optional inside XNNPACK. Disable it by default while the
# pinned upstream GitLab archive fails its SHA256 check. Do not bypass hashes.
option(PICOKERAS_KLEIDIAI "Enable optional KleidiAI kernels in XNNPACK" OFF)
set(XNNPACK_ENABLE_KLEIDIAI ${PICOKERAS_KLEIDIAI} CACHE BOOL "KleidiAI" FORCE)
# TensorFlow 2.18.1 vendors older libraries (e.g. FP16 with cmake_minimum_required
# below 3.5), which CMake 4 no longer accepts without this compatibility floor.
set(CMAKE_POLICY_VERSION_MINIMUM 3.5 CACHE STRING "Compatibility floor for old TFLite subprojects")
# FP16's old build invokes a nested CMake process to fetch PSimd if this is
# missing. Require a prepared checkout instead, to avoid the CMake 4 failure.
set(PSIMD_SOURCE_DIR "" CACHE PATH "Pinned PSimd source checkout for FP16")
if(NOT EXISTS "${PSIMD_SOURCE_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "Missing PSimd checkout: build using tools/macOS/build.sh")
endif()
option(PICOKERAS_NATIVE "Optimize for the build machine CPU (less portable binary)" ON)
option(PICOKERAS_LTO "Enable IPO/LTO when supported" ON)
set(TFLITE_ENABLE_XNNPACK ${PICOKERAS_XNNPACK} CACHE BOOL "XNNPACK" FORCE)
set(TFLITE_ENABLE_GPU OFF CACHE BOOL "No GPU delegate" FORCE)
set(TFLITE_ENABLE_RUY ON CACHE BOOL "CPU kernels" FORCE)
set(TFLITE_ENABLE_INSTALL OFF CACHE BOOL "No install target" FORCE)
add_subdirectory("${TFLITE_ROOT}/tensorflow/lite" "${CMAKE_CURRENT_BINARY_DIR}/tflite_build" EXCLUDE_FROM_ALL)

add_executable(picoKeras "${PK_SRC}/main.cpp" "${PK_SRC}/board.cpp" "${PK_SRC}/model_tflite.cpp")
target_include_directories(picoKeras PRIVATE "${PK_SRC}")
target_link_libraries(picoKeras PRIVATE tensorflow-lite)
target_compile_definitions(picoKeras PRIVATE PICOKERAS_PLATFORM_MACOS=1 PICOKERAS_MODEL_TFLITE=1)
target_compile_options(picoKeras PRIVATE -O3 -Wall -Wextra -Wpedantic)
if(PICOKERAS_NATIVE)
  target_compile_options(picoKeras PRIVATE -mcpu=native)
endif()
if(PICOKERAS_LTO)
  include(CheckIPOSupported)
  check_ipo_supported(RESULT _ipo_ok OUTPUT _ipo_msg)
  if(_ipo_ok)
    set_property(TARGET picoKeras PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
  else()
    message(WARNING "LTO not supported: ${_ipo_msg}")
  endif()
endif()
# Native Apple frameworks are a suitable acceleration option, but TFLite
# itself decides which kernels and libraries its build can use.
message(STATUS "picoKeras macOS: arch=${CMAKE_OSX_ARCHITECTURES} XNNPACK=${PICOKERAS_XNNPACK} native=${PICOKERAS_NATIVE} IPO=${_ipo_ok}")

# Shared C++ MULTICORE backend: no ARM changes.
option(MULTICORE "Parallel minimax and threaded neural inference" ON)
if(MULTICORE)
  find_package(Threads REQUIRED)
  target_sources(picoKeras PRIVATE "${PK_SRC}/multicore.cpp")
  target_link_libraries(picoKeras PRIVATE Threads::Threads)
  target_compile_definitions(picoKeras PRIVATE PICOKERAS_MULTICORE=1)
endif()
message(STATUS "picoKeras ${PROJECT_VERSION} MULTICORE=${MULTICORE}")

