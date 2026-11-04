# picoKeras ARM v0.1.28 -- TFLM build without MSYS2/make.
# Kernel sources generated from the bundled tflite-micro sources.inc.
# This module does not modify the vendored repository.
if(NOT TFLM_LIBRARY)
  set(_dl "${TFLM_INCLUDE}/tensorflow/lite/micro/tools/make/downloads")
  if(NOT EXISTS "${_dl}/flatbuffers/include/flatbuffers/flatbuffers.h")
    message(FATAL_ERROR "TFLM FlatBuffers headers missing. Run build.ps1 to prepare dependencies")
  endif()
  file(GLOB _tflm_core CONFIGURE_DEPENDS
    "${TFLM_INCLUDE}/tensorflow/lite/micro/*.cc"
    "${TFLM_INCLUDE}/tensorflow/lite/micro/arena_allocator/*.cc"
    "${TFLM_INCLUDE}/tensorflow/lite/micro/memory_planner/*.cc"
    "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/internal/*.cc"
    "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/internal/reference/*.cc")
  list(FILTER _tflm_core EXCLUDE REGEX "(_test|_benchmark)[.]cc$")
  # Target-specific replacements for the generic debug/time implementations.
  list(FILTER _tflm_core EXCLUDE REGEX "/(debug_log|micro_time)[.]cc$")
  set(_pico_port "${CMAKE_CURRENT_LIST_DIR}/../src/tflm_pico_port.cpp")
  if(NOT EXISTS "${_pico_port}")
    message(FATAL_ERROR "picoKeras TFLM platform port missing: ${_pico_port}")
  endif()
  list(APPEND _tflm_core "${_pico_port}")
  set(_tflm_kernels
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/activations.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/activations_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/add.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/add_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/add_n.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/arg_min_max.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/assign_variable.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/basic_classifier.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/batch_matmul.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/batch_matmul_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/batch_to_space_nd.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/broadcast_args.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/broadcast_to.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/call_once.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/cast.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/ceil.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/circular_buffer.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/circular_buffer_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/comparisons.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/concatenation.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/conv.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/conv_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/cumsum.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decode.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decode_state.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decode_state_huffman.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decode_state_lut.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decode_state_prune.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decompress.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/decompress_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/depth_to_space.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/depthwise_conv.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/depthwise_conv_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/dequantize.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/dequantize_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/detection_postprocess.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/div.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/dynamic_update_slice.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/elementwise.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/elu.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/embedding_lookup.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/ethosu.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/exp.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/expand_dims.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/fill.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/floor.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/floor_div.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/floor_mod.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/fully_connected.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/fully_connected_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/gather.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/gather_nd.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/hard_swish.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/hard_swish_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/if.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/kernel_runner.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/kernel_util.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/l2norm.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/l2_pool_2d.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/leaky_relu.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/leaky_relu_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/logical.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/logical_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/logistic.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/logistic_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/log_softmax.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/lstm_eval.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/lstm_eval_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/maximum_minimum.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/mirror_pad.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/mul.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/mul_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/neg.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/pack.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/pad.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/pad_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/pooling.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/pooling_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/prelu.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/prelu_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/quantize.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/quantize_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/read_variable.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/reduce.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/reduce_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/reshape.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/reshape_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/resize_bilinear.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/resize_nearest_neighbor.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/reverse.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/round.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/select.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/shape.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/slice.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/softmax.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/softmax_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/space_to_batch_nd.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/space_to_depth.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/split.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/split_v.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/squared_difference.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/squeeze.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/strided_slice.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/strided_slice_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/sub.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/sub_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/svdf.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/svdf_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/tanh.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/transpose.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/transpose_common.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/transpose_conv.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/unidirectional_sequence_lstm.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/unpack.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/var_handle.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/while.cc"
  "${TFLM_INCLUDE}/tensorflow/lite/micro/kernels/zeros_like.cc"
  )
  foreach(_source IN LISTS _tflm_kernels)
    if(NOT EXISTS "${_source}")
      message(FATAL_ERROR "TFLM source missing from bundled version: ${_source}")
    endif()
  endforeach()
  add_library(tensorflow_microlite STATIC ${_tflm_core} ${_tflm_kernels})
  target_include_directories(tensorflow_microlite PUBLIC
    "${TFLM_INCLUDE}" "${_dl}" "${_dl}/flatbuffers/include"
    "${_dl}/kissfft")
  target_compile_definitions(tensorflow_microlite PRIVATE
    TFLM_REMOVE_VIRTUAL_DELETE TF_LITE_DISABLE_X86_NEON
    FLATBUFFERS_LOCALE_INDEPENDENT=0 FLATBUFFERS_PREFER_PRINTF=1
    KERNELS_OPTIMIZED_FOR_SPEED CPU_M33=1 TF_LITE_MCU_DEBUG_LOG)
  target_compile_options(tensorflow_microlite PRIVATE
    -fno-rtti -fno-exceptions -fno-threadsafe-statics
    -ffunction-sections -fdata-sections -funsigned-char)
  # The local TFLM Pico port includes pico/time.h and calls time_us_64().
  # Link the Pico SDK target to this library itself, so its PUBLIC include
  # directories and compile requirements are available while compiling it.
  target_link_libraries(tensorflow_microlite PUBLIC pico_time pico_stdlib)
  set(_tflm_link tensorflow_microlite)
  message(STATUS "TFLM native CMake static library; ${TFLM_INCLUDE}")
else()
  if(NOT EXISTS "${TFLM_LIBRARY}")
    message(FATAL_ERROR "TFLM_LIBRARY missing: ${TFLM_LIBRARY}")
  endif()
  set(_tflm_link "${TFLM_LIBRARY}")
  message(STATUS "TFLM external archive: ${TFLM_LIBRARY}")
endif()
