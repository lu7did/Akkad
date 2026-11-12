cmake_minimum_required(VERSION 3.16)
set(SARGON_ARM "${CMAKE_CURRENT_LIST_DIR}/../../picoSargon/ARM")
if(NOT EXISTS "${SARGON_ARM}/src/engine.cpp")
  message(FATAL_ERROR "picoSargon/ARM sources required alongside picoPixie/ARM")
endif()
include("${SARGON_ARM}/pico_sdk_import.cmake")
project(picoPixie VERSION 0.1.28 LANGUAGES C CXX ASM)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(PICO_CXX_ENABLE_EXCEPTIONS 1)
pico_sdk_init()
option(STEROIDS "Sargon aspiration/SEE/razoring" ON)
option(TWINS "Two-core RP2350 Sargon search" ON)
if(NOT STEROIDS OR NOT TWINS)
  message(FATAL_ERROR "picoPixie fallback requires STEROIDS=ON and TWINS=ON")
endif()
add_library(sargon_core
  "${SARGON_ARM}/src/board.cpp"
  "${SARGON_ARM}/src/grumpy.cpp"
  "${SARGON_ARM}/src/engine.cpp")
target_include_directories(sargon_core PUBLIC "${SARGON_ARM}/include")
target_compile_definitions(sargon_core PUBLIC PICOSARGON_STEROIDS=1 PICOSARGON_TWINS=1)
target_compile_options(sargon_core PRIVATE -Wall -Wextra -Wno-psabi)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(PICOPIXIE_UCI_MAIN "${CMAKE_CURRENT_BINARY_DIR}/generated/picopixie_uci_main.cpp")
add_custom_command(
  OUTPUT "${PICOPIXIE_UCI_MAIN}"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/src/uci_main_overlay.py"
          "${SARGON_ARM}/src/pico_main.cpp" "${PICOPIXIE_UCI_MAIN}"
  DEPENDS "${SARGON_ARM}/src/pico_main.cpp"
          "${CMAKE_CURRENT_LIST_DIR}/src/uci_main_overlay.py"
  COMMENT "Adapting shared picoSargon UCI transport for picoPixie transactions"
  VERBATIM)
add_executable(picoPixie
  "${PICOPIXIE_UCI_MAIN}"
  src/cloud_https.cpp
  src/picolichess_adapter.cpp)
target_include_directories(picoPixie PRIVATE include config "${SARGON_ARM}/include")
target_link_libraries(picoPixie PRIVATE
  sargon_core pico_stdlib pico_multicore pico_rand
  pico_cyw43_arch_lwip_poll pico_lwip_mbedtls pico_mbedtls)
target_compile_definitions(picoPixie PRIVATE PICO_CYW43_ARCH_POLL=1 PICOSARGON_CLOUD_HOOK=1)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${SARGON_ARM}/include/config.h")
file(STRINGS "${SARGON_ARM}/include/config.h" _mdns_setting
    REGEX "^[ \t]*inline[ \t]+constexpr[ \t]+bool[ \t]+MDNS_ENABLED[ \t]*=")
if(_mdns_setting MATCHES "MDNS_ENABLED[ \t]*=[ \t]*true")
  target_link_libraries(picoPixie PRIVATE pico_lwip_mdns)
  target_compile_definitions(picoPixie PRIVATE PICOSARGON_MDNS_COMPILED=1)
else()
  target_compile_definitions(picoPixie PRIVATE PICOSARGON_MDNS_COMPILED=0)
endif()
pico_enable_stdio_usb(picoPixie 1)
pico_enable_stdio_uart(picoPixie 0)
pico_add_extra_outputs(picoPixie)
message(STATUS "picoPixie v0.1.28 ARM STEROIDS=ON TWINS=ON Board=${PICO_BOARD}")
message(STATUS "picoPixie settings: ${CMAKE_CURRENT_LIST_DIR}/include/config.hpp")
message(STATUS "Shared Wi-Fi / board config: ${SARGON_ARM}/include/config.h")
