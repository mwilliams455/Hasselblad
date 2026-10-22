/* SPDX-License-Identifier: MIT
 * Stage8 portable, table-agnostic colour-profile preparation research.
 * Independently implemented from native X2D II 1.3.16.2 bounded profile
 * interpolation evidence. NOT a photographic pixel LUT sampler.
 */
#ifndef HB_MAIN_LUT_PROFILE_H
#define HB_MAIN_LUT_PROFILE_H
#include <stddef.h>
#include <stdint.h>

#define HB_MAIN_LUT_PROFILE_SCHEMA 1u
#define HB_MAIN_LUT_PROFILE_COUNT 8u
#define HB_MAIN_LUT_MAX_WORDS_PER_PROFILE 6144u
#define HB_MAIN_LUT_CAMERA_WORDS_PER_PROFILE 6144u

enum hb_main_lut_status {
    HB_MAIN_LUT_OK = 0,
    HB_MAIN_LUT_INVALID_ARGS = 1,
    HB_MAIN_LUT_INVALID_SHAPE = 2,
    HB_MAIN_LUT_UNSUPPORTED_GAMUT = 3,
    HB_MAIN_LUT_OVERLAPPING_MEMORY = 4
};

typedef struct hb_main_lut_receipt {
    uint32_t schema;
    uint32_t cct_first_index, cct_fraction_q8;
    uint32_t gamut_index, gamut_fraction_q8;
    uint32_t words_written;
    uint32_t pixel_sampler_verified;
    uint32_t photographic_render_authorized;
} hb_main_lut_receipt;

/* Both buffers contain little-endian packed two-signed-int16 word values.
 * The input is an opaque 8 x words_per_profile array; no camera table is
 * bundled. CCT-first in each gamut bank, then gamut 0 and 1.
 * Source count must be exactly 8*words_per_profile and destination capacity
 * >= words_per_profile. Gamut is ONLY 0 or 1. This API never accepts pixels.
 * On any error, output words and receipt are untouched.
 * Source and destination must not overlap. */
int hb_main_lut_prepare(const uint32_t *source,
                        size_t source_words,
                        size_t words_per_profile,
                        int32_t cct_kelvin,
                        int32_t gamut_selector,
                        uint32_t *dest,
                        size_t dest_capacity_words,
                        hb_main_lut_receipt *receipt);
#endif
