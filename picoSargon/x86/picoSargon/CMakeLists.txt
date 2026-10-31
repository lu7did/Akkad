cmake_minimum_required(VERSION 3.16)
project(picoSargon VERSION 0.2.23 LANGUAGES CXX)
option(STEROIDS "Enable aspiration windows, SEE and razoring (experimental)" OFF)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(picoSargon src/host_main.cpp src/board.cpp src/engine.cpp src/grumpy.cpp)
target_compile_definitions(picoSargon PRIVATE PICOSARGON_VERSION="${PROJECT_VERSION}")
if(STEROIDS)
 target_compile_definitions(picoSargon PRIVATE PICOSARGON_STEROIDS=1)
endif()
message(STATUS "picoSargon STEROIDS=${STEROIDS}")
target_include_directories(picoSargon PRIVATE include)
if(MSVC)
    target_compile_options(picoSargon PRIVATE /W3)
else()
    target_compile_options(picoSargon PRIVATE -Wall -Wextra -Wno-psabi)
endif()

# Ubicacion identica con Visual Studio (multi-config) y Ninja (single-config).
set_target_properties(picoSargon PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL "${CMAKE_BINARY_DIR}"
)
