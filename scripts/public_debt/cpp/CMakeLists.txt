# Standalone build of the header-only C++ engines: unit tests.
#
# The Python extension is built by setup.py (pybind11); this project compiles the same headers without Python,
# with strict warnings and optional sanitizers, so that the C++ code is checked on its own.
#
#   cmake -S scripts/public_debt/cpp -B build/cpp -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
#   cmake --build build/cpp
#   ctest --test-dir build/cpp --output-on-failure
#
# Sanitizers: -DPD_SANITIZE=address,undefined (memory errors and undefined behaviour) or -DPD_SANITIZE=thread
# (data races in the parallel loops). They cannot be combined in one build.

cmake_minimum_required(VERSION 3.16)
project(public_debt_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(PD_WERROR "Treat compiler warnings as errors" ON)
set(PD_SANITIZE "" CACHE STRING "Comma-separated sanitizers passed to -fsanitize (for example address,undefined)")

find_package(Threads REQUIRED)

add_library(pd_engine_lib INTERFACE)
target_include_directories(pd_engine_lib INTERFACE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pd_engine_lib INTERFACE Threads::Threads)

if(MSVC)
  target_compile_options(pd_engine_lib INTERFACE /W4 /permissive- $<$<BOOL:${PD_WERROR}>:/WX>)
else()
  target_compile_options(pd_engine_lib INTERFACE -Wall -Wextra -Wpedantic -Wshadow -Wnon-virtual-dtor
                         -Wold-style-cast -Wnull-dereference -Wdouble-promotion
                         $<$<BOOL:${PD_WERROR}>:-Werror>)
  # Bounds-checked standard containers in debug-like builds.
  target_compile_definitions(pd_engine_lib INTERFACE $<$<NOT:$<CONFIG:Release>>:_GLIBCXX_ASSERTIONS>)
endif()

if(PD_SANITIZE)
  if(MSVC)
    message(FATAL_ERROR "PD_SANITIZE is supported with GCC and Clang only")
  endif()
  target_compile_options(pd_engine_lib INTERFACE -fsanitize=${PD_SANITIZE} -fno-omit-frame-pointer
                         -fno-sanitize-recover=all)
  target_link_options(pd_engine_lib INTERFACE -fsanitize=${PD_SANITIZE})
endif()

enable_testing()

add_executable(core_tests tests/test_core.cpp)
target_link_libraries(core_tests PRIVATE pd_engine_lib)
add_test(NAME core_tests COMMAND core_tests)

