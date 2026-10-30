cmake_minimum_required(VERSION 3.21)
project(AkkadAlphaZero LANGUAGES NONE)
# Thin compatibility entry point. LC0's own build system is Meson;
# delegating preserves its backend registration and generated protobufs.
find_program(POWERSHELL_EXECUTABLE NAMES pwsh powershell REQUIRED)
add_custom_target(AlphaZero ALL
  COMMAND "${POWERSHELL_EXECUTABLE}" -NoProfile -ExecutionPolicy Bypass -File "${CMAKE_CURRENT_SOURCE_DIR}/build.ps1"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  COMMENT "Compile AlphaZero.exe with the LCZero C++ inference backend"
  VERBATIM)
