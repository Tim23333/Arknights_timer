# Set the minimum version of CMake that can be used
cmake_minimum_required (VERSION 3.8)

# Set the project name
project("AssetStudioFBXNative")

# Set the C++ standard to C++ 14
set(CMAKE_CXX_STANDARD 14)

# Generate the shared library from the library sources
add_library(AssetStudioFBXNative SHARED
    asfbx_skin_context.cpp
    asfbx_morph_context.cpp
    api.cpp
    utils.cpp
    asfbx_context.cpp
    asfbx_anim_context.cpp)

# Add the given directories to those the compiler uses to search for include files
target_include_directories(AssetStudioFBXNative PRIVATE .)

target_link_libraries(AssetStudioFBXNative PRIVATE fbxsdk xml2)