# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file LICENSE.rst or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION ${CMAKE_VERSION}) # this file comes with cmake

# If CMAKE_DISABLE_SOURCE_CHANGES is set to true and the source directory is an
# existing directory in our source tree, calling file(MAKE_DIRECTORY) on it
# would cause a fatal error, even though it would be a no-op.
if(NOT EXISTS "/Users/pedrocolla/akkad/picoKeras/macOS/build/protobuf")
  file(MAKE_DIRECTORY "/Users/pedrocolla/akkad/picoKeras/macOS/build/protobuf")
endif()
file(MAKE_DIRECTORY
  "/Users/pedrocolla/akkad/picoKeras/macOS/build/_deps/protobuf-build"
  "/Users/pedrocolla/akkad/picoKeras/macOS/build"
  "/Users/pedrocolla/akkad/picoKeras/macOS/build/tmp"
  "/Users/pedrocolla/akkad/picoKeras/macOS/build/src/protobuf-populate-stamp"
  "/Users/pedrocolla/akkad/picoKeras/macOS/build/src"
  "/Users/pedrocolla/akkad/picoKeras/macOS/build/src/protobuf-populate-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/Users/pedrocolla/akkad/picoKeras/macOS/build/src/protobuf-populate-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/Users/pedrocolla/akkad/picoKeras/macOS/build/src/protobuf-populate-stamp${cfgdir}") # cfgdir has leading slash
endif()
