cmake_minimum_required(VERSION 3.16)
project(vibecheck_lifter)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(pybind11 REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(SPOT REQUIRED libspot)

# Add the Pybind11 module
# Compiles src/lifter.cpp and src/lifter.hpp into vibecheck_lifter.so
pybind11_add_module(vibecheck_lifter
    src/lifter.cpp
    src/lifter.hpp
)

# Link SPOT, BuDDy (bddx), and include headers
target_link_libraries(vibecheck_lifter PRIVATE ${SPOT_LIBRARIES})
target_include_directories(vibecheck_lifter PRIVATE ${SPOT_INCLUDE_DIRS})
target_link_directories(vibecheck_lifter PRIVATE ${SPOT_LIBRARY_DIRS})

# Set the output directory properties so the .so binary lands inside 'src/' for Python access
set_target_properties(vibecheck_lifter PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/src"
)

