/* SPDX-License-Identifier: MIT */
/* Stage24 opt-in SOFTWARE RESEARCH renderer: standard DNG PCS, no HNCS claim. */
#ifndef HB24_RENDERER_H
#define HB24_RENDERER_H
#include <stddef.h>
#include <stdint.h>
#include "hb_dng_pcs_bridge.h"
#include "hb_colour_stage19.h"
#include "hb_main_candidate21.h"
#ifdef __cplusplus
extern "C" {
#endif
#define HB24_SCHEMA 24u
#define HB24_MAX_PIXELS 1024u
#define HB24_PCS_ONLY 0
#define HB24_MAIN_HYPOTHESIS 1
/* Distinct component failures are intentionally not collapsed into success. */
enum hb24_status { HB24_OK = 0, HB24_BAD_INPUT = 1,
    HB24_BAD_SIZE = 2, HB24_UNSUPPORTED_PROFILE = 3,
    HB24_NUMERIC = 4, HB24_UNVERIFIED_DOMAIN = 5,
    HB24_OVERLAP = 6 };
typedef struct hb24_context {
    double camera_to_xyz_d50[9];
    double xyz_d50_to_linear_rgb[9];
    uint32_t gamut;
    uint32_t schema;
} hb24_context;
typedef struct hb24_receipt {
    uint32_t schema;
    uint32_t pixel_count;
    uint32_t display_gamut;
    uint32_t pcs_normalized_neutral;
    uint32_t output_linear_light;
    uint32_t uses_stage21_MAIN_hypothesis;
    uint32_t true_hasselblad_ccm_pixel_proven;
    uint32_t true_hasselblad_gamma_pixel_proven;
    uint32_t true_hasselblad_lut_pixel_proven;
    uint32_t true_hasselblad_wb_calibrated;
    uint32_t photographic_render_authorized;
    uint32_t existing_phone_renderer_modified;
} hb24_receipt;

/* DNG matrix fast path: unmatched dual-illuminant matrices fail closed. */
int hb24_build(const double fm1[9], const double fm2[9],
               const double cc1[9], const double cc2[9],
               const double analog_balance[3], const double neutral[3],
               int gamut, hb24_context *context, hb24_receipt *receipt);

/* Already black-corrected, demosaiced camera RGB, 1..1024 samples per call.
 * Mode 0 returns scene-linear sRGB/P3; no transfer, tone, clip or WB estimate.
 * Mode 1 additionally treats linear display RGB as an EXPERIMENTAL input to
 * a Stage21 externally supplied planar LUT: an intentionally UNVERIFIED
 * MAIN domain and output. Reject all out-of-[0,1] values rather than clamp.
 * Mode 1 is NOT an approved camera JPEG renderer or faithful Hasselblad ISP.
 * source, destination, context, receipt and LUT must not overlap.
 * Transactional failure: destination and receipt stay unchanged.
 */
int hb24_process(const hb24_context *context,
                 const double *source_camera_rgb, size_t pixels,
                 double *output_linear_rgb, int mode,
                 const uint32_t *experimental_lut, size_t lut_words,
                 const uint8_t axis_to_input[3],
                 const uint8_t bank_to_output[3],
                 int interpolation, hb24_receipt *receipt);
#ifdef __cplusplus
}
#endif
#endif
