# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION ${CMAKE_VERSION}) # this file comes with cmake

# If CMAKE_DISABLE_SOURCE_CHANGES is set to true and the source directory is an
# existing directory in our source tree, calling file(MAKE_DIRECTORY) on it
# would cause a fatal error, even though it would be a no-op.
if(NOT EXISTS "/home/pi/chess/akkad/picoKeras/debian/build/protobuf")
  file(MAKE_DIRECTORY "/home/pi/chess/akkad/picoKeras/debian/build/protobuf")
endif()
file(MAKE_DIRECTORY
  "/home/pi/chess/akkad/picoKeras/debian/build/_deps/protobuf-build"
  "/home/pi/chess/akkad/picoKeras/debian/build"
  "/home/pi/chess/akkad/picoKeras/debian/build/tmp"
  "/home/pi/chess/akkad/picoKeras/debian/build/src/protobuf-populate-stamp"
  "/home/pi/chess/akkad/picoKeras/debian/build/src"
  "/home/pi/chess/akkad/picoKeras/debian/build/src/protobuf-populate-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/home/pi/chess/akkad/picoKeras/debian/build/src/protobuf-populate-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/home/pi/chess/akkad/picoKeras/debian/build/src/protobuf-populate-stamp${cfgdir}") # cfgdir has leading slash
endif()
