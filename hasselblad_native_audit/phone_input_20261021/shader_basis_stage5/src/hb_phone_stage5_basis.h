/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_STAGE5_BASIS_H
#define HB_PHONE_STAGE5_BASIS_H
#include <stdint.h>
#include <stddef.h>
#include "hb_phone_neutral_observation.h"

/* Independent, source-informed CPU colour-basis study: NOT native ISP/GL parity.
 * The only currently supported image route is full, packed RGGB RAW16, with
 * original physical-sensor/frame provenance and zero crop offset. No render. */
#define HB_S5_SCHEMA 1u
#define HB_S5_RAW 1u
#define HB_S5_PHOTON_RELATIVE 2u

enum hb_s5_status {
    HB_S5_OK=0, HB_S5_ARGUMENT=1, HB_S5_UNPROVEN=2,
    HB_S5_UNSUPPORTED_GEOMETRY=3, HB_S5_INVALID_MAP=4,
    HB_S5_MEMORY=5
};

typedef struct {
    const uint8_t *raw_le16;
    size_t raw_bytes;
    uint32_t width, height, row_stride_bytes;
    uint32_t cfa;              /* RGGB=0 only; no unproven phase/crop support. */
    uint32_t black_raw_code;   /* equal 4 sites, exact sensor codes */
    uint32_t white_raw_code;
    const float *lens_map_rg_gb_b; /* Camera2 row-major RGGB 4-float cells */
    uint32_t map_width, map_height;
    size_t map_floats;       /* exact 4*width*height map extent */
    uint32_t study_basis;      /* RAW or hypothetical Photon relative gain */
    uint64_t timestamp_ns, exposure_ns;
    uint32_t ISO, proven_sensor_and_frame, original_single_raw;
} hb_s5_input;

typedef struct {
    uint32_t schema, study_basis, observed_pixels;
    uint32_t map_quantized_as_fp16, green_channel_average;
    uint32_t saturated_blocks, invalid_ratio_blocks;
    uint32_t study_only, render_permitted;
    hb_ns_frame observation; /* actual new bounded basis => Stage4 evidence */
} hb_s5_result;

/* A shader-EXPRESSION CPU model. For every RAW pixel its map UV is the integer
 * pixel coordinate / full RAW dimensions, then GL_LINEAR at (u*N-0.5),
 * GL_CLAMP_TO_EDGE. Input map is quantized to IEEE binary16 as with Photon's
 * FLOAT_16 GLTexture upload, reconstructed to float32 for bilinear work.
 * R/G/B shading channels = [R,mean(Gr,Gb),B], normalized by their RGB mean.
 * The study deliberately omits HAL whitePoint division: AWB observes sensor
 * chroma before a new WB decision, never fitted to the existing HAL neutral.
 * It also omits shader clipping, highlight reconstruction, RGB-layout, crop,
 * demosaic and tone stages. It is NOT evidence of bit-exact GPU output.
 * Exact checks must precede calls; output untouched on ALL errors. */
int hb_s5_project(const hb_s5_input *input,hb_s5_result *out);
#endif
