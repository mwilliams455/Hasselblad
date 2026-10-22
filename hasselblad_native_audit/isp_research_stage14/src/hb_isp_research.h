/* SPDX-License-Identifier: MIT
 * Hasselblad Stage14: software ISP research composition.
 * Exact original-reference PREPARATION + exact DISPLAY-only sample model.
 * Not the camera MAIN pixel equation, not a photographic or shipping renderer.
 * No original IQ asset, DSP library, RAW, Camera2, Android or GL interface.
 */
#ifndef HB_ISP_RESEARCH_H
#define HB_ISP_RESEARCH_H
#include <stddef.h>
#include <stdint.h>

#define HB_ISP_RESEARCH_SCHEMA 14u
#define HB_ISP_MAIN_SOURCE_WORDS 49152u
#define HB_ISP_MAIN_PREPARED_WORDS 6144u
#define HB_ISP_CCM_SOURCE_VALUES 768u
#define HB_ISP_CCM_PREPARED_VALUES 96u
#define HB_ISP_GAMMA_DIVS 7u
#define HB_ISP_GAMMA_KNOTS 257u
#define HB_ISP_MAX_PROBE_PIXELS 1024u

/* These statuses belong to this owned adapter, not original vendor code. */
enum hb_isp_research_status {
    HB_ISP_OK=0, HB_ISP_BAD_ARGS=1, HB_ISP_BAD_SHAPE=2,
    HB_ISP_BAD_DOMAIN=3, HB_ISP_ALIAS=4, HB_ISP_ALLOCATION=5,
    HB_ISP_PREPARATION_FAILED=6, HB_ISP_UNVERIFIED_PHOTOGRAPHIC=7
};

enum hb_isp_research_route {
    HB_ISP_ROUTE_NORMAL_STILL3=0,
    HB_ISP_ROUTE_ENHANCED_NORMAL_STILL0=1,
    HB_ISP_ROUTE_ENHANCED_HDR_STILL0=2
};

enum hb_isp_missing_contracts {
    HB_ISP_MISSING_AWB_CALIBRATION=1u<<0,
    HB_ISP_MISSING_SENSOR_TO_ISP_DOMAIN=1u<<1,
    HB_ISP_MISSING_MAIN_CCM_PIXEL_EQUATION=1u<<2,
    HB_ISP_MISSING_MAIN_GAMMA_PIXEL_EQUATION=1u<<3,
    HB_ISP_MISSING_MAIN_LUT_PIXEL_ORACLE=1u<<4,
    HB_ISP_MISSING_HARDWARE_STAGE_ORDER=1u<<5,
    HB_ISP_MISSING_OUTPUT_TRANSFER_AND_R2Y=1u<<6,
    HB_ISP_MISSING_MODE_RUNTIME_CONTROL=1u<<7
};
#define HB_ISP_UNRESOLVED_ALL UINT32_C(255)

typedef struct {
    uint32_t schema;
    uint32_t research_only;
    uint32_t photographic_render_authorized;
    uint32_t main_pixel_sampler_verified;
    uint32_t ccm_pixel_equation_verified;
    uint32_t gamma_pixel_evaluation_verified;
    uint32_t display_only_sampler_reference;
    uint32_t route;  /* Labelled context ONLY. Does not select a new source. */
    uint32_t cct_first_index;
    uint32_t cct_fraction_q8;
    uint32_t gamut_selector;
    uint32_t secondary_ccm_weight_q8;
    uint32_t prepared_lut_words;
    uint32_t prepared_ccm_values;
    uint32_t gamma_coordinate_count;
    uint32_t sampled_test_pixels;
    uint32_t unresolved_contracts_mask;
} hb_isp_research_receipt;

/* Proven original-code MAIN gamma *coordinate* generator, not evaluator.
 * Input is 7 log2 interval counts; sum of 2^d must equal 256.
 * On failure, the 257 output uint32 values remain untouched.
 */
int hb_isp_research_gamma_knots(const uint32_t divisions[7],
                                 uint32_t coordinates[257]);

/* Prepare a synthetic or caller-owned eight-profile array and CCM source.
 * Actual camera LUT bytes are NOT bundled and no file or camera is accessed.
 * CCT profile interpolation and CCM coefficient interpolation reuse the
 * already-audited native-equivalent Stage8/CCM primitives.
 * Gamma coordinates are native-equivalent; gamma PIXEL evaluation is absent.
 * Six source/result arrays have exact lengths and must not overlap.
 * Outputs (including receipt) remain untouched on any failure.
 * Route is a recorded label only; it is not an original mode controller.
 */
int hb_isp_research_prepare(const uint32_t *lut_profiles, size_t lut_source_count,
                            const int32_t *ccm_profiles, size_t ccm_source_count,
                            const uint32_t gamma_divisions[7],
                            int32_t cct_kelvin, int32_t gamut_selector,
                            int32_t secondary_ccm_weight_q8, uint32_t route,
                            uint32_t prepared_lut[6144],
                            int32_t prepared_ccm[96],
                            uint32_t gamma_coordinates[257],
                            hb_isp_research_receipt *receipt);

/* *** DISPLAY-ONLY HYPOTHESIS, NOT PHOTOGRAPHIC MAIN ***
 * Evaluate up to 1024 bounded research input RGB triples. The identity
 * upstream CCM and gamma are NOT claimed to reflect actual camera processing.
 * Only normalized [0,1] RGB values are supported by the original display
 * library oracle; signed or headroom pixels MUST be rejected, not clipped.
 * Works with prepared LUT words but their actual MAIN packing remains unknown.
 * On any error, neither outputs nor receipt are altered.
 */
int hb_isp_research_display_candidate(const uint32_t prepared_lut[6144],
                const double *input_rgb, size_t rgb_count,
                double *output_rgb, hb_isp_research_receipt *receipt);

/* Hard fail-closed gate for the genuine MAIN photographic pipeline.
 * A synthetic/reference success never grants permission to render a photo.
 */
int hb_isp_research_main_gate(uint32_t *missing_contracts_mask);

#endif
