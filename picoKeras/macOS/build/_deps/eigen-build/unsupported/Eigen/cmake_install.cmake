# Install script for directory: /Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/usr/bin/objdump")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Devel" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/eigen3/unsupported/Eigen" TYPE FILE FILES
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/AdolcForward"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/AlignedVector3"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/ArpackSupport"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/AutoDiff"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/BVH"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/EulerAngles"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/FFT"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/IterativeSolvers"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/KroneckerProduct"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/LevenbergMarquardt"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/MatrixFunctions"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/MPRealSupport"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/NNLS"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/NonLinearOptimization"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/NumericalDiff"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/OpenGLSupport"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/Polynomials"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/SparseExtra"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/SpecialFunctions"
    "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/Splines"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Devel" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/eigen3/unsupported/Eigen" TYPE DIRECTORY FILES "/Users/pedrocolla/akkad/picoKeras/macOS/build/eigen/unsupported/Eigen/src" FILES_MATCHING REGEX "/[^/]*\\.h$")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("/Users/pedrocolla/akkad/picoKeras/macOS/build/_deps/eigen-build/unsupported/Eigen/CXX11/cmake_install.cmake")

endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "/Users/pedrocolla/akkad/picoKeras/macOS/build/_deps/eigen-build/unsupported/Eigen/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
