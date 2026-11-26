cmake_minimum_required(VERSION 3.16)
option(PICOSARGON_PICO "Build RP2040/RP2350 firmware" OFF)
if(PICOSARGON_PICO)
 include(pico_sdk_import.cmake)
endif()
project(picoSargon VERSION 0.2.51 LANGUAGES C CXX ASM)
option(STEROIDS "Enable aspiration windows, SEE and razoring (experimental)" ON)
option(TWINS "Enable TWINS compile-time switch for ARM" ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(sargon_core src/board.cpp src/grumpy.cpp src/engine.cpp)
if(STEROIDS)
 target_compile_definitions(sargon_core PUBLIC PICOSARGON_STEROIDS=1)
endif()
if(TWINS)
 target_compile_definitions(sargon_core PUBLIC PICOSARGON_TWINS=1)
endif()
message(STATUS "picoSargon STEROIDS=${STEROIDS}")
message(STATUS "picoSargon TWINS=${TWINS}")
target_include_directories(sargon_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(sargon_core PRIVATE -Wall -Wextra)
# GCC 7+ emits ABI-change notes from libstdc++ vector templates on ARM.
# Silence only these informational -Wpsabi notes; keep all other warnings enabled.
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
 target_compile_options(sargon_core PRIVATE -Wno-psabi)
endif()
if(NOT PICOSARGON_PICO)
 add_executable(picoSargon src/host_main.cpp)
 target_link_libraries(picoSargon PRIVATE sargon_core)
 include(CTest)
 if(BUILD_TESTING AND TWINS)
  find_package(Threads REQUIRED)
  add_executable(test_twins_recovery tests/test_twins_recovery.cpp)
  target_link_libraries(test_twins_recovery PRIVATE sargon_core Threads::Threads)
  add_test(NAME twins_recovery COMMAND test_twins_recovery "${CMAKE_CURRENT_SOURCE_DIR}/assets/bashful.bin")
 endif()
else()
 if(NOT DEFINED ENV{PICO_SDK_PATH} AND NOT PICO_SDK_PATH)
  message(FATAL_ERROR "Set PICO_SDK_PATH for RP2040/RP2350 builds")
 endif()
 set(PICO_CXX_ENABLE_EXCEPTIONS 1)
 pico_sdk_init()
  # Regenerate FLASH images on every change to Bashful; also covers direct CMake builds.
  find_package(Python3 COMPONENTS Interpreter REQUIRED)
  set(BASHFUL_BIN "${CMAKE_CURRENT_SOURCE_DIR}/assets/bashful.bin")
  set(EMBED_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/../tools/ARM/embed_grumpy.py")
  set(BASHFUL_SINGLE "${CMAKE_CURRENT_SOURCE_DIR}/include/generated_grumpy.hpp")
  set(BASHFUL_TWINS "${CMAKE_CURRENT_SOURCE_DIR}/include/twins_grumpy.hpp")
  add_custom_command(
    OUTPUT "${BASHFUL_SINGLE}" "${BASHFUL_TWINS}"
    COMMAND "${Python3_EXECUTABLE}" "${EMBED_SCRIPT}"
            --input "${BASHFUL_BIN}"
            --output "${BASHFUL_SINGLE}"
            --twins-output "${BASHFUL_TWINS}"
    DEPENDS "${BASHFUL_BIN}" "${EMBED_SCRIPT}"
    COMMENT "Embedding bashful.bin in Pico FLASH (single and TWINS)"
    VERBATIM
  )
  add_custom_target(embed_bashful DEPENDS "${BASHFUL_SINGLE}" "${BASHFUL_TWINS}")

  add_executable(picoSargon src/pico_main.cpp)
  add_dependencies(picoSargon embed_bashful)
 target_include_directories(picoSargon PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/config)
 target_link_libraries(picoSargon PRIVATE sargon_core pico_stdlib pico_cyw43_arch_lwip_poll pico_multicore)
 target_compile_definitions(picoSargon PRIVATE PICO_CYW43_ARCH_POLL=1)
 # Guardia para build.ps1: garantizar que el valor que se leyo de config.h
 # es el mismo que ve el compilador al construir pico_main.cpp.
 if(DEFINED PICOSARGON_EXPECTED_PLL_SYS)
  target_compile_definitions(picoSargon PRIVATE
      PICOSARGON_EXPECTED_PLL_SYS=${PICOSARGON_EXPECTED_PLL_SYS})
  message(STATUS "picoSargon PLL_SYS esperado=${PICOSARGON_EXPECTED_PLL_SYS} MHz")
 endif()
 # Reconfigure when config.h toggles mDNS (without affecting the non-mDNS build).
 set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/include/config.h")
 file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/include/config.h" _mdns_setting
      REGEX "^[ \t]*inline[ \t]+constexpr[ \t]+bool[ \t]+MDNS_ENABLED[ \t]*=")
 if(_mdns_setting MATCHES "MDNS_ENABLED[ \t]*=[ \t]*true")
  message(STATUS "picoSargon mDNS compiled: ON")
  target_link_libraries(picoSargon PRIVATE pico_lwip_mdns)
  target_compile_definitions(picoSargon PRIVATE PICOSARGON_MDNS_COMPILED=1)
 else()
  message(STATUS "picoSargon mDNS compiled: OFF")
  target_compile_definitions(picoSargon PRIVATE PICOSARGON_MDNS_COMPILED=0)
 endif()
 pico_enable_stdio_usb(picoSargon 1)
 pico_enable_stdio_uart(picoSargon 0)
 pico_add_extra_outputs(picoSargon)
endif()
