/* SPDX-License-Identifier: MIT
 * Stage9: isolated reconstruction of X2D II DISPLAY-HAL 16^3 LUT format.
 * The relation to saved-photo MAIN_3DLUT is UNPROVEN. No photo renderer hook.
 */
#ifndef HB_DISPLAY_LUT16_H
#define HB_DISPLAY_LUT16_H
#include <stddef.h>
#include <stdint.h>
#define HB_DISPLAY_LUT16_WIDTH 16u
#define HB_DISPLAY_LUT16_WORDS 6144u
#define HB_DISPLAY_LUT16_SCHEMA 1u

enum hb_display_lut16_status {
    HB_DISPLAY_LUT16_OK=0,
    HB_DISPLAY_LUT16_BAD_ARGUMENT=1,
    HB_DISPLAY_LUT16_BAD_TABLE=2,
    HB_DISPLAY_LUT16_OUT_OF_DOMAIN=3,
    HB_DISPLAY_LUT16_OVERLAP=4
};

/* Exact 12-bit display packing: q=128*R+8*G+B/2; two B values per word.
 * Component banks begin at q, q+2048 and q+4096. All three values are /4095.
 * source_count MUST be exactly 6144 32-bit words, channels 0..15.
 * Output untouched on failure; output must not alias source LUT words.
 */
int hb_display_lut16_node(const uint32_t *source, size_t source_count,
                          uint32_t r, uint32_t g, uint32_t b, double rgb[3]);

/* Reconstructs ONLY original do_3dlut_trans display-HAL subset:
 * finite input RGB in [0,1], width=16, scale=1 and normal trilinear weights.
 * in and out may be the same three-double buffer; source is read-only.
 * This is NOT validated for negative/headroom signals or MAIN_3DLUT.
 */
int hb_display_lut16_trilinear(const uint32_t *source, size_t source_count,
                               const double input[3], double output[3]);
#endif
