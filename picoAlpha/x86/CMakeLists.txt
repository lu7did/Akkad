cmake_minimum_required(VERSION 3.16)
project(picoAlpha LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(ZLIB REQUIRED)
option(PA_X86_FC1_TILED "Portable FC1: process four output neurons per pass" ON)
if(PA_X86_FC1_TILED)
 set(PA_X86_FC1_TILED_VALUE 1)
else()
 set(PA_X86_FC1_TILED_VALUE 0)
endif()
# Both LC0 networks are loaded at runtime from an external .pb.gz file.
# No Pico embedded headers or ARM intrinsics are required in the Windows build.
add_executable(picoAlpha src/main.cpp src/net.cpp src/board.cpp)
target_compile_definitions(picoAlpha PRIVATE PICOALPHA_DEFAULT_INT8=1)
target_include_directories(picoAlpha PRIVATE include)
target_compile_definitions(picoAlpha PRIVATE PA_X86_FC1_TILED=${PA_X86_FC1_TILED_VALUE})
target_link_libraries(picoAlpha PRIVATE ZLIB::ZLIB)
if(MSVC)
 target_compile_options(picoAlpha PRIVATE /O2 /W3)
else()
 target_compile_options(picoAlpha PRIVATE -O3 -Wall -Wextra)
endif()

# Default executable is INT8. FP32 remains as an explicitly named 32-bit-float reference build.
# The UCI adapter and player selection are unchanged.
add_executable(picoAlpha32 src/main.cpp src/net.cpp src/board.cpp)
target_include_directories(picoAlpha32 PRIVATE include)
target_compile_definitions(picoAlpha32 PRIVATE PA_X86_FC1_TILED=${PA_X86_FC1_TILED_VALUE})
target_link_libraries(picoAlpha32 PRIVATE ZLIB::ZLIB)
if(MSVC)
 target_compile_options(picoAlpha32 PRIVATE /O2 /W3)
else()
 target_compile_options(picoAlpha32 PRIVATE -O3 -Wall -Wextra)
endif()

# Keep both Windows outputs directly in ./build, including multi-config VS generators.
foreach(_target picoAlpha picoAlpha32)
  set_target_properties(${_target} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL "${CMAKE_BINARY_DIR}")
endforeach()
