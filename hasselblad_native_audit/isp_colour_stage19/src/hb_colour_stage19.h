/* SPDX-License-Identifier: MIT
 * Stage19 research — D50 PCS -> display-primary *linear* RGB and
 * an independent public Phocus401 WB selector model. NOT HNCS rendering.
 * Does not include proprietary camera/Phocus matrices, LUTs or tone curves.
 */
#ifndef HB_COLOUR_STAGE19_H
#define HB_COLOUR_STAGE19_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HB19_SCHEMA 19u
#define HB19_MAX_PIXELS 4096u
#define HB19_MAX_SELECTOR_SAMPLES 8192u
#define HB19_SRGB 0
#define HB19_DISPLAY_P3 1
enum { HB19_OK=0, HB19_BAD_INPUT=1, HB19_UNSUPPORTED=2,
       HB19_OVERLAP=3, HB19_NUMERIC_ERROR=4 };
typedef struct {
    uint32_t schema;
    uint32_t linear_rgb_only;
    uint32_t d50_to_d65_bradford;
    uint32_t output_gamut;
    uint32_t profile_connection_space_only;
    uint32_t original_main_ccm_pixel_verified;
    uint32_t original_main_lut_pixel_verified;
    uint32_t vendor_hncs_colour_applied;
    uint32_t photographic_render_authorized;
} hb19_output_receipt;
/* 3x3 row-major: ICC D50 PCS (0.9642, 1, 0.8249) to D65
 * linear sRGB or linear Display P3. No sRGB OETF, no clipping or look.
 * On error, output and receipt are unmodified. No input/output alias.
 */
int hb19_build_output_matrix(int gamut, double out_matrix[9],
                             hb19_output_receipt *receipt);
/* Source is already CIE XYZ D50. Preserve finite negatives and headroom.
 * Fail transactionally if any intermediate overflows / invalid input.
 */
int hb19_apply_output_matrix(const double matrix[9], const double *xyz_d50,
                             size_t count, double *linear_rgb);
/* ONLY a selector from public, independent Phocus401 reconstruction.
 * Proprietary WB matrices/LUT entries are intentionally NOT available.
 * Original public model truncates Kelvin toward zero, clamps LUT K to
 * [2000,10000], matrix K to [2000,8000], and extrapolates on edge knots.
 * A selector result does not authorize applying HNCS colour.
 */
typedef struct {
    uint32_t schema;
    int32_t truncated_kelvin;
    int32_t lut_effective_kelvin;
    int32_t matrix_effective_kelvin;
    uint32_t lut_lower_index;     /* 3100,5550,9100 */
    uint32_t matrix_lower_index;  /* 2400,3100,5550,9100 */
    double lut_alpha;
    double matrix_alpha;
    uint32_t original_phocus_payload_present;
    uint32_t hncs_render_authorized;
} hb19_phocus_selector;
int hb19_select_phocus_wb(double kelvin, hb19_phocus_selector *output);
/* A bounded synthetic-only helper for testing Phocus's public LUT
 * float32 storage/rounding after interpolation. Any finite input can
 * be supplied, but it is NOT a MAIN/Phocus photographic LUT decoder.
 */
int hb19_synthetic_phocus_blend(const double *low, const double *high,
                                size_t length, double alpha, float *out);
#ifdef __cplusplus
}
#endif
#endif
