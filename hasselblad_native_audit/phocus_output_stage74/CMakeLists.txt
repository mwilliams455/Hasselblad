cmake_minimum_required(VERSION 3.21)
project(HasselbladStage74 C)
if(NOT ANDROID)
    message(FATAL_ERROR "Stage74 CMake integration is Android NDK only; run_host74.sh covers host tests")
endif()
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
get_filename_component(HB_AUDIT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(HB_SOURCE
    ${HB_AUDIT_ROOT}/phocus_gradient_stage61/gradient_maps61.c
    ${HB_AUDIT_ROOT}/phocus_interpolation_stage62/interpolation62.c
    ${HB_AUDIT_ROOT}/phocus_green_stage63/green63.c
    ${HB_AUDIT_ROOT}/phocus_inline_stage67/raw_gradient67.c
    ${HB_AUDIT_ROOT}/phocus_inline_stage67/green_site_mask67.c
    ${HB_AUDIT_ROOT}/phocus_coloursite_stage68/colour_gradient68.c
    ${HB_AUDIT_ROOT}/phocus_coloursite_stage68/colour_site68.c
    ${HB_AUDIT_ROOT}/phocus_schedule_stage66/schedule66.c
    ${HB_AUDIT_ROOT}/phocus_schedule_stage66/wiring66.c
    ${HB_AUDIT_ROOT}/phocus_integrated_stage69/interpolate69.c
    ${HB_AUDIT_ROOT}/phocus_frame_stage73/frame73.c
    ${HB_AUDIT_ROOT}/phocus_noise_stage65/noise65.c
    ${HB_AUDIT_ROOT}/phocus_colour_stage64/ycc64.c
    ${CMAKE_CURRENT_LIST_DIR}/output74.c
    ${CMAKE_CURRENT_LIST_DIR}/frame74.c
    ${CMAKE_CURRENT_LIST_DIR}/jni_bridge74.c)
add_library(hbfinal74 SHARED ${HB_SOURCE})
target_compile_options(hbfinal74 PRIVATE -O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
target_link_libraries(hbfinal74 PRIVATE m)
