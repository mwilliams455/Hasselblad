#ifndef HB_FRAME73_H
#define HB_FRAME73_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* These are intermediate pre-ColorNoise R/G/B and direction codes, NOT a
 * displayed/final Phocus RGB image. This bounded tile interface contains
 * neither any vendor binaries nor calibration/colour profiles.
 */
typedef enum {
    HB73_OK=0, HB73_BAD_ARGUMENT=-1, HB73_UNSUPPORTED=-2,
    HB73_ALLOCATION_FAILED=-3, HB73_INTERPOLATION_FAILED=-4
} HB73Status;
typedef enum { HB73_RGGB=0 } HB73Cfa;
typedef struct {
    int output_width, output_height;
    int source_width, source_height;
    int work_width, work_height, work_stride;
    int crop_x, crop_y;
    /* 1: full CPU final-output parity tested; 2: original outer geometry
     * measured but full pixel parity not yet established. Both bounded. */
    int evidence_scope;
} HB73Plan;
typedef struct {
    int cfa;
    unsigned flags;
    double scale_threshold;
    int edge_gradient_floor, raw_gradient_floor;
    /* Only samples outside the supplied image + halo are filled. This is
     * an explicit diagnostics value, NOT a claimed original native edge rule. */
    uint16_t alignment_tail_fill;
} HB73Settings;
typedef struct {
    uint64_t interpolator_events;
    uint64_t red_blue_green_calls;
    uint64_t colour_site_estimates;
    size_t allocated_bytes;
} HB73Receipt;

/* Fail closed to dimensions measured in the original bounded CPU graph.
 * Work alignment is observed here, not generalized to a full-frame router.
 * Does not allocate or inspect image content. */
int hb73_plan(int output_width, int output_height, HB73Plan *plan);

/* Input is already-prepared uint16 RGGB with an explicit 32px halo on each
 * side. Source shape is (H+64) x (W+64), input_stride >= W+64 in elements.
 * The caller owns the Bayer samples, GainMap / WB / black / white mapping and
 * any external sensor/CFA transformations. No implicit border extension.
 * Source buffer and output must be disjoint. Source is never modified.
 * Packed output is R,G,B,mask per cropped pixel, before colour-noise/YCC.
 * All buffers owned here are separate. On failure the caller output remains
 * untouched; no partial results are exported. Never call this on UI thread.
 */
int hb73_render_pre_noise(const HB73Plan *plan, const HB73Settings *settings,
    const uint16_t *prepared_halo_bayer, size_t input_element_count,
    int input_stride, uint16_t *packed_rgb_mask,
    size_t output_element_count, HB73Receipt *receipt);
#ifdef __cplusplus
}
#endif
#endif
