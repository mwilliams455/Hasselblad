cmake_minimum_required(VERSION 3.6)

project(dngCreator)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_link_options("-Wl,-z,max-page-size=16384")

file(READ ${CMAKE_CURRENT_SOURCE_DIR}/../../../version.properties ver)
string(REGEX MATCH "VERSION_BUILD=([0-9]*)" _ ${ver})
set(VERSION_BUILD ${CMAKE_MATCH_1})
string(REGEX MATCH "VERSION_NAME=([0-9,.]*)" _ ${ver})
set(VERSION_NAME ${CMAKE_MATCH_1})

# Preserve the exact headers used by the successful pinned upstream build.
# Their original download locations and hashes are in development/hasselblad/.
# Configuration does not fetch code from moving upstream branches.
function(require_pinned_header name expected_hash)
    set(header "${CMAKE_CURRENT_SOURCE_DIR}/deps/${name}")
    if(NOT EXISTS "${header}")
        message(FATAL_ERROR "Missing retained Photon dependency header: ${name}")
    endif()
    file(SHA256 "${header}" actual_hash)
    if(NOT actual_hash STREQUAL expected_hash)
        message(FATAL_ERROR "Retained Photon dependency header hash mismatch: ${name}")
    endif()
endfunction()
require_pinned_header(tiny_dng_writer.h ce4828181c29ff72811b427b777d99e3f337870630a9a56dce819d8763f3e85b)
require_pinned_header(technicallyflac.h 7877dfd21152cd383812a860e18feab667ac8543c55a6b80118b9c1a5f654449)
require_pinned_header(archive.h ea01da96b4c5e3a0e7b07e70c5b1ea8cb73bb14075056a008dbb92cba31209a5)
require_pinned_header(archive_entry.h a8d2e0f18bf9b2ebd9eace883616e481cd5c6ea4f437b23640f90a3331b4506f)

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/deps)

set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR})

# Audited WB arithmetic exposed only by the standalone development-check screen.
# This target has no camera/ISP imports and does not load the vendor libaaa.so.
add_library(hasselblad_wb_jni SHARED
    ${SRC_DIR}/hasselblad/hb_awb_recalib.c
    ${SRC_DIR}/hasselblad/hb_awb_jni.c
)
target_compile_options(hasselblad_wb_jni PRIVATE -Wall -Wextra -Werror)
set_target_properties(hasselblad_wb_jni PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON)

# This owned research ABI is ARM64 only. Other ABIs keep the existing renderer
# and explicitly report that the optional candidate diagnostic is unavailable.
if(ANDROID_ABI STREQUAL "arm64-v8a")
    get_filename_component(HB_AUDIT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit" ABSOLUTE)
    set(HB_PHONE "${HB_AUDIT}/phone_input_20261021")
    set(HB_RUNTIME "${HB_AUDIT}/awb_original_runtime_20261021")
    set(HB_STATS "${HB_AUDIT}/awb_rebuild_04_20261021/src")
    add_library(hasselblad_scene_jni SHARED
        hasselblad/hb_phone_scene_jni.c
        ${HB_PHONE}/hb_phone_scene.c ${HB_PHONE}/hb_phone_temperature.c ${HB_PHONE}/hb_phone_raw.c
        ${HB_RUNTIME}/hb_temperature.c ${HB_RUNTIME}/hb_user_controls.c
        ${HB_RUNTIME}/hb_scene_optimizer.c ${HB_RUNTIME}/hb_scene_candidates.c ${HB_RUNTIME}/hb_scene_filter.c
        ${HB_STATS}/hb_awb_frame_stats.c ${HB_STATS}/hb_awb_stages.c)
    target_include_directories(hasselblad_scene_jni PRIVATE ${HB_PHONE})
    target_compile_options(hasselblad_scene_jni PRIVATE -O2 -Wall -Wextra -Werror
        -Wno-misleading-indentation -ffp-contract=off -ffunction-sections -fdata-sections -fvisibility=hidden)
    target_link_libraries(hasselblad_scene_jni m)
    set_target_properties(hasselblad_scene_jni PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON
        LINK_FLAGS "-Wl,--gc-sections,-z,defs,-z,max-page-size=16384")

    # Domain1 runs only on demand. It is never called by the shutter/scene
    # JNI path and does not have access to RAW or the photographic renderer.
    add_library(hasselblad_domain_jni SHARED
        hasselblad/hb_phone_domain_jni.c
        ${HB_PHONE}/hb_phone_domain.c ${HB_PHONE}/hb_phone_temperature.c
        ${HB_RUNTIME}/hb_temperature.c ${HB_RUNTIME}/hb_user_controls.c
        ${HB_RUNTIME}/hb_scene_optimizer.c)
    target_include_directories(hasselblad_domain_jni PRIVATE ${HB_PHONE})
    target_compile_options(hasselblad_domain_jni PRIVATE -O2 -Wall -Wextra -Werror
        -Wno-misleading-indentation -ffp-contract=off -ffunction-sections -fdata-sections
        -fvisibility=hidden)
    target_link_libraries(hasselblad_domain_jni m)
    set_target_properties(hasselblad_domain_jni PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON
        LINK_FLAGS "-Wl,--gc-sections,-z,defs,-z,max-page-size=16384")

    # Stage8 isolated ARM64 profile interpolation JNI, opt-in diagnostic only.
    # No sensor, RAW, camera table, photographic pixel or renderer hooks.
    set(HB_PHOTO_STAGE8 "${HB_AUDIT}/photographic_profile_stage8")
    add_library(hasselblad_profile_jni SHARED
        hasselblad/hb_photo_profile_jni.c
        "${HB_PHOTO_STAGE8}/src/hb_main_lut_profile.c")
    target_include_directories(hasselblad_profile_jni PRIVATE "${HB_PHOTO_STAGE8}/src")
    target_compile_options(hasselblad_profile_jni PRIVATE -O2 -Wall -Wextra -Werror
        -fvisibility=hidden -ffunction-sections -fdata-sections)
    set_target_properties(hasselblad_profile_jni PROPERTIES
        C_STANDARD 11 C_STANDARD_REQUIRED ON
        LINK_FLAGS "-Wl,--gc-sections,-z,defs,-z,max-page-size=16384")

    # Stage26: original Stage24 PCS-only colourimetry through a bounded JNI tile.
    # It is NOT connected to Camera2, raw processing, saved JPEG or the camera
    # viewfinder. No vendor CCM/LUT assets or HNCS mode are bundled.
    set(HB_STAGE24 "${HB_AUDIT}/isp_colour_stage24/src")
    set(HB_STAGE18 "${HB_AUDIT}/isp_dng_stage18/src")
    set(HB_STAGE19 "${HB_AUDIT}/isp_colour_stage19/src")
    set(HB_STAGE21 "${HB_AUDIT}/isp_main_stage21/src")
    add_library(hasselblad_colour_reference_jni SHARED
        hasselblad/hb_colour_reference_jni.c
        "${HB_STAGE24}/hb24_renderer.c"
        "${HB_STAGE18}/hb_dng_pcs_bridge.c"
        "${HB_STAGE19}/hb_colour_stage19.c"
        "${HB_STAGE21}/hb_main_candidate21.c")
    target_include_directories(hasselblad_colour_reference_jni PRIVATE
        "${HB_STAGE24}" "${HB_STAGE18}" "${HB_STAGE19}" "${HB_STAGE21}")
    target_compile_options(hasselblad_colour_reference_jni PRIVATE
        -O2 -Wall -Wextra -Werror -ffp-contract=off
        -fvisibility=hidden -ffunction-sections -fdata-sections)
    set_target_properties(hasselblad_colour_reference_jni PROPERTIES
        C_STANDARD 11 C_STANDARD_REQUIRED ON
        LINK_FLAGS "-Wl,--gc-sections,-z,defs,-z,max-page-size=16384")
    target_link_libraries(hasselblad_colour_reference_jni m)
endif()


# Stage42 private saved-RAW renderer, available on both configured ABIs.
get_filename_component(HB42_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_port_stage42" ABSOLUTE)
add_library(hasselblad_renderer42_jni SHARED
    hasselblad/hb_renderer42_jni.c "${HB42_ROOT}/src/hb42_colour.c"
    "${HB42_ROOT}/../phocus_highlight_stage53/highlight53.c"
    "${HB42_ROOT}/../phocus_post_stage55/post55.c"
    "${HB42_ROOT}/../phocus_finish_stage88/finish88.c"
    "${HB42_ROOT}/../isp_dng_stage18/src/hb_dng_pcs_bridge.c"
    "${HB42_ROOT}/../isp_colour_stage19/src/hb_colour_stage19.c")
target_include_directories(hasselblad_renderer42_jni PRIVATE "${HB42_ROOT}/src"
    "${HB42_ROOT}/../phocus_highlight_stage53"
    "${HB42_ROOT}/../phocus_post_stage55"
    "${HB42_ROOT}/../phocus_finish_stage88"
    "${HB42_ROOT}/../isp_dng_stage18/src" "${HB42_ROOT}/../isp_colour_stage19/src")
target_compile_options(hasselblad_renderer42_jni PRIVATE -O2 -Wall -Wextra -Werror -ffp-contract=off)
target_link_libraries(hasselblad_renderer42_jni m)
set_target_properties(hasselblad_renderer42_jni PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON
    LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

find_program(PYTHON3_EXECUTABLE python3)

# ---------------------------------------------------------------------------
# ncnn (prebuilt static lib under ncnn/<ABI>/)
#
# Both ML networks (FlowNet + KernelNet) are compiled into ONE shared library
# (libncnnMl.so) that
# links ncnn statically. The FlowNet model requires three custom layers
# (FlownetUpsample / FlownetCorrLookup / FlownetCorrFused) compiled from source
# and registered at runtime via Net::register_custom_layer().
#
# arm64-v8a: ncnn built with Vulkan → GPU inference, glslang .a linked.
# armeabi-v7a: ncnn built without Vulkan → CPU-only, no glslang needed.
# ---------------------------------------------------------------------------
set(NCNN_ABI_DIR "${CMAKE_CURRENT_SOURCE_DIR}/ncnn/${ANDROID_ABI}")
set(NCNN_INC_DIR "${NCNN_ABI_DIR}/include/ncnn")
set(NCNN_LIB_DIR "${NCNN_ABI_DIR}/lib")

if(EXISTS "${NCNN_LIB_DIR}/libncnn.a")
    # --- generate shader headers from .comp files (configure-time) ---
    set(SHADER_DIR "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/shader")
    set(GEN_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/flownet/gen_shader_header.py")
    set(GEN_OUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
    file(MAKE_DIRECTORY "${GEN_OUT_DIR}")

    set(VULKAN_LAYER_SRCS "")
    set(VULKAN_LIBS "")
    set(NCNN_VULKAN OFF)

    if(EXISTS "${NCNN_LIB_DIR}/libSPIRV.a")
        set(NCNN_VULKAN ON)
        # Vulkan layer sources — only compiled when glslang is present
        set(VULKAN_LAYER_SRCS
            "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/flownetupsample_vulkan.cpp"
            "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/flownetcorrlookup_vulkan.cpp"
            "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan/flownetcorrfused_vulkan.cpp"
        )
        set(VULKAN_LIBS
            "${NCNN_LIB_DIR}/libglslang.a"
            "${NCNN_LIB_DIR}/libMachineIndependent.a"
            "${NCNN_LIB_DIR}/libGenericCodeGen.a"
            "${NCNN_LIB_DIR}/libglslang-default-resource-limits.a"
            "${NCNN_LIB_DIR}/libOSDependent.a"
            "${NCNN_LIB_DIR}/libSPIRV.a"
        )
        # Generate shader headers (only needed for Vulkan path)
        foreach(shader flownetcorrfused flownetcorrlookup flownetupsample)
            set(out "${GEN_OUT_DIR}/${shader}_comp.h")
            execute_process(
                COMMAND "${PYTHON3_EXECUTABLE}" "${GEN_SCRIPT}"
                        "${SHADER_DIR}/${shader}.comp" "${shader}_comp_data"
                OUTPUT_FILE "${out}"
                RESULT_VARIABLE gen_result
            )
            if(NOT gen_result EQUAL 0)
                message(WARNING "Failed to generate ${shader}_comp.h")
            endif()
        endforeach()
    endif()

    add_library(ncnnMl SHARED
        ${SRC_DIR}/ncnnMl.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/flownetupsample.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/flownetcorrlookup.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/flownetcorrfused.cpp
        ${VULKAN_LAYER_SRCS}
    )

    target_include_directories(ncnnMl PRIVATE
        "${NCNN_INC_DIR}"
        "${GEN_OUT_DIR}"
        "${CMAKE_CURRENT_SOURCE_DIR}/flownet"
        "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer"
        "${CMAKE_CURRENT_SOURCE_DIR}/flownet/layer/vulkan"
    )

    # OpenMP: compile with -fopenmp so the default CPU impls of the custom
    # FlowNet layers (which use `#pragma omp parallel for num_threads(opt.num_threads)`)
    # actually parallelize. Statically link NDK's libomp.a so there is no
    # runtime libomp.so dependency and no runtime CPU/topology probing picks the
    # thread count — ncnnMl sets opt.num_threads explicitly.
    target_compile_options(ncnnMl PRIVATE
        -fno-rtti -fno-exceptions
        -fopenmp
    )

    execute_process(
        COMMAND "${CMAKE_CXX_COMPILER}" -print-resource-dir
        OUTPUT_VARIABLE NCNN_CLANG_RESOURCE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(ANDROID_ABI STREQUAL "arm64-v8a")
        set(NCNN_OMP_ARCH "aarch64")
    elseif(ANDROID_ABI STREQUAL "armeabi-v7a")
        set(NCNN_OMP_ARCH "arm")
    else()
        set(NCNN_OMP_ARCH "")
    endif()

    if(NCNN_OMP_ARCH AND EXISTS "${NCNN_CLANG_RESOURCE_DIR}/lib/linux/${NCNN_OMP_ARCH}/libomp.a")
        set(NCNN_OMP_LIB "${NCNN_CLANG_RESOURCE_DIR}/lib/linux/${NCNN_OMP_ARCH}/libomp.a")
    else()
        set(NCNN_OMP_LIB "")
        message(WARNING "OpenMP static library (libomp.a) not found for ${ANDROID_ABI}")
    endif()

    target_link_libraries(ncnnMl PRIVATE
        "${NCNN_LIB_DIR}/libncnn.a"
        ${VULKAN_LIBS}
        ${NCNN_OMP_LIB}
        android
        log
    )

    set_target_properties(ncnnMl PROPERTIES
        CXX_STANDARD 17
        CXX_STANDARD_REQUIRED ON
        CXX_EXTENSIONS OFF
    )

    message(STATUS "ncnn enabled for ${ANDROID_ABI} (Vulkan: ${NCNN_VULKAN})")
else()
    message(WARNING "ncnn prebuilt not found for ${ANDROID_ABI}; NcnnML disabled")
    # Generate stub JNI functions so the library loads without ncnn.
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/ncnnMl_stub.cpp"
        "#include <jni.h>\n"
        "extern \"C\" {\n"
        "JNIEXPORT jboolean JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_NcnnMl_nativeEnsureInit(JNIEnv*, jclass) { return JNI_TRUE; }\n"
        "JNIEXPORT jlong JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_FlowNetNcnnProcessor_nativeCreate(JNIEnv*, jclass, jobject, jstring) { return 0; }\n"
        "JNIEXPORT jboolean JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_FlowNetNcnnProcessor_nativeRun(JNIEnv*, jclass, jlong, jobject, jobject, jint, jint, jobject) { return JNI_FALSE; }\n"
        "JNIEXPORT void JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_FlowNetNcnnProcessor_nativeDestroy(JNIEnv*, jclass, jlong) {}\n"
        "JNIEXPORT jlong JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_KernelNetNcnnProcessor_nativeCreate(JNIEnv*, jclass, jobject, jstring) { return 0; }\n"
        "JNIEXPORT jboolean JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_KernelNetNcnnProcessor_nativeRun(JNIEnv*, jclass, jlong, jobject, jint, jint, jfloat, jobject) { return JNI_FALSE; }\n"
        "JNIEXPORT void JNICALL\n"
        "Java_com_particlesdevs_photoncamera_processing_ml_KernelNetNcnnProcessor_nativeDestroy(JNIEnv*, jclass, jlong) {}\n"
        "}\n"
    )
    add_library(ncnnMl SHARED
        "${CMAKE_CURRENT_BINARY_DIR}/ncnnMl_stub.cpp"
    )
    target_link_libraries(ncnnMl PRIVATE
        log
    )
endif()

add_library(${CMAKE_PROJECT_NAME} SHARED
    ${SRC_DIR}/dngCreator.cpp
)
add_library(allocator SHARED
    ${SRC_DIR}/allocator.cpp
    ${SRC_DIR}/rawF16.cpp
)
add_library(flacRecorder SHARED
    ${SRC_DIR}/flacRecorder.cpp
)

# --- MediaCinemaRAW (.mcraw) lossless raw-video encoder ---------------------
# Sources are globbed: dropping additional .cpp/.h files into
# src/main/cpp/mediacinemaraw/{,src} adds them to the build automatically.
# The test/ subdirectory is intentionally outside the glob.
file(GLOB MCRAW_SOURCES
        "${SRC_DIR}/mediacinemaraw/*.cpp"
        "${SRC_DIR}/mediacinemaraw/src/*.cpp"
)
add_library(mcraw SHARED ${MCRAW_SOURCES})
target_include_directories(mcraw PRIVATE "${SRC_DIR}/mediacinemaraw/include")
# Always optimize the encoder, including debug Gradle builds: unoptimized
# debug code multiplies the per-frame encode time several times over and
# starves the RAW video pipeline.
target_compile_options(mcraw PRIVATE -O3)
target_link_libraries(mcraw PRIVATE
        log
)
add_library(
        camera2native SHARED ${SRC_DIR}/native-engine.cpp
)

target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
        VERSION_BUILD="${VERSION_BUILD}"
        VERSION_NAME="${VERSION_NAME}"
)

target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE
        log
        dl
)

target_link_libraries(allocator PRIVATE
        log
        jnigraphics
)

target_link_libraries(flacRecorder PRIVATE
        log
)

target_link_libraries(
        camera2native
        log
)

# --- Halide CPU burst alignment (arm64-v8a only) ----------------------------
# Prebuilt kernels from the halide-align project (stage 1: base pyramid once
# per burst; stage 2: per-frame tile matching; optional level-0 flow
# refinement - alignflow_base gprod precompute + alignflow_f16 per-frame
# Gauss-Newton refinement, linked in and toggled at runtime via
# nSetRefineEnabled in align_jni.cpp)
# + the Halide arm64 runtime, wrapped for Java by align_jni.cpp.
# armeabi-v7a builds skip this library; HalideAlignment.java falls back to
# the GL pyramid path when it is absent.
if (${ANDROID_ABI} STREQUAL "arm64-v8a"
        AND EXISTS ${SRC_DIR}/halide/arm64-v8a/libhalide_runtime_android.a)
    add_library(halidealign SHARED ${SRC_DIR}/halide/align_jni.cpp)
    target_include_directories(halidealign PRIVATE
            ${SRC_DIR}/halide/include
            ${SRC_DIR}/halide/arm64-v8a)
    set_target_properties(halidealign PROPERTIES CXX_STANDARD 17)
    add_library(alignburst_base_f16 STATIC IMPORTED)
    set_target_properties(alignburst_base_f16 PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/alignburst_base_f16.a)
    add_library(alignburst_f16 STATIC IMPORTED)
    set_target_properties(alignburst_f16 PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/alignburst_f16.a)
    add_library(alignflow_base STATIC IMPORTED)
    set_target_properties(alignflow_base PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/alignflow_base.a)
    add_library(alignflow_f16 STATIC IMPORTED)
    set_target_properties(alignflow_f16 PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/alignflow_f16.a)
    add_library(halide_runtime_android STATIC IMPORTED)
    set_target_properties(halide_runtime_android PROPERTIES
            IMPORTED_LOCATION ${SRC_DIR}/halide/arm64-v8a/libhalide_runtime_android.a)
    target_link_libraries(halidealign PRIVATE
            alignburst_base_f16
            alignburst_f16
            alignflow_base
            alignflow_f16
            halide_runtime_android
            log
            dl)
endif()

# Stage75 saved-DNG diagnostic only: exact portable Stage74 target, both app ABIs.
get_filename_component(HB74_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_output_stage74" ABSOLUTE)
add_subdirectory("${HB74_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/hbfinal74")
set_target_properties(hbfinal74 PROPERTIES LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

# Stage76: band assembly of unchanged Stage74 64x64 calls; no synthetic outer borders.
get_filename_component(HB76_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_scene_stage76" ABSOLUTE)
add_library(hbframe76 SHARED "${HB76_ROOT}/frame76.c" "${HB76_ROOT}/jni76.c")
target_link_libraries(hbframe76 PRIVATE hbfinal74)
target_compile_options(hbframe76 PRIVATE -O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
set_target_properties(hbframe76 PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

# Stage77 compact wide tiles, up to four isolated workers.
get_filename_component(HB77_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_speed_stage77" ABSOLUTE)
add_library(hbframe77 SHARED "${HB77_ROOT}/frame77.c" "${HB77_ROOT}/jni77.c")
target_link_libraries(hbframe77 PRIVATE hbfinal74)
target_compile_options(hbframe77 PRIVATE -O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
set_target_properties(hbframe77 PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

# Stage86 bounded sharpening comparison. The existing colour library is unchanged.
get_filename_component(HB85_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_sharpen_stage85" ABSOLUTE)
add_library(hbsharp86 SHARED hasselblad/hb_sharpen86_jni.c "${HB85_ROOT}/sharpen85.c")
target_include_directories(hbsharp86 PRIVATE "${HB85_ROOT}")
target_compile_options(hbsharp86 PRIVATE -O2 -Wall -Wextra -Werror -ffp-contract=off)
target_link_libraries(hbsharp86 m)
set_target_properties(hbsharp86 PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

# Stage96 source-neutral adapter; original Phocus kernels remain in hbfinal74.
get_filename_component(HB96_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_chroma_stage96" ABSOLUTE)
add_library(hbframe96 SHARED "${HB96_ROOT}/frame96.c" "${HB96_ROOT}/jni96.c")
target_link_libraries(hbframe96 PRIVATE hbfinal74 m)
target_compile_options(hbframe96 PRIVATE -O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
set_target_properties(hbframe96 PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

# Stage97 bounded colour-outlier correction; reference Stage96 remains intact.
get_filename_component(HB97_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_edges_stage97" ABSOLUTE)
add_library(hbframe97 SHARED "${HB97_ROOT}/frame97.c" "${HB97_ROOT}/chroma97.c" "${HB97_ROOT}/jni97.c")
target_link_libraries(hbframe97 PRIVATE hbfinal74 m)
target_compile_options(hbframe97 PRIVATE -O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
set_target_properties(hbframe97 PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")

# Stage99 source-camera correction; previous reconstruction stays unchanged.
get_filename_component(HB99_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../hasselblad_native_audit/phocus_fringe_stage99" ABSOLUTE)
add_library(hbfringe99 SHARED "${HB99_ROOT}/chroma99.c" "${HB99_ROOT}/jni99.c")
target_link_libraries(hbfringe99 PRIVATE m)
target_compile_options(hbfringe99 PRIVATE -O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off)
set_target_properties(hbfringe99 PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON LINK_FLAGS "-Wl,-z,defs,-z,max-page-size=16384")
