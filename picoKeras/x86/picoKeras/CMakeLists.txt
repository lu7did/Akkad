cmake_minimum_required(VERSION 3.20)
project(picoKeras VERSION 0.2.1 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(TENSORFLOW_ROOT "" CACHE PATH "TensorFlow C library distribution root")
find_path(TF_INCLUDE tensorflow/c/c_api.h HINTS "${TENSORFLOW_ROOT}/include" NO_DEFAULT_PATH REQUIRED)
find_library(TF_LIBRARY NAMES tensorflow libtensorflow HINTS "${TENSORFLOW_ROOT}/lib" NO_DEFAULT_PATH REQUIRED)

add_executable(picoKeras src/main.cpp src/model.cpp src/board.cpp)
target_include_directories(picoKeras PRIVATE include "${TF_INCLUDE}")
target_link_libraries(picoKeras PRIVATE "${TF_LIBRARY}")

if(WIN32)
    target_link_libraries(picoKeras PRIVATE ws2_32)
    set(TF_RUNTIME_DLL "${TENSORFLOW_ROOT}/lib/tensorflow.dll")
    if(EXISTS "${TF_RUNTIME_DLL}")
        add_custom_command(TARGET picoKeras POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${TF_RUNTIME_DLL}" "$<TARGET_FILE_DIR:picoKeras>"
            COMMENT "Copy TensorFlow runtime DLL alongside picoKeras executable"
        )
    endif()
endif()

if(MSVC)
    target_compile_options(picoKeras PRIVATE /O2 /EHsc /W4)
else()
    target_compile_options(picoKeras PRIVATE -O3 -Wall -Wextra -Wpedantic)
endif()
