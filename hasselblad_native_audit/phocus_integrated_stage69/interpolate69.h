#ifndef HB_INTERPOLATE69_H
#define HB_INTERPOLATE69_H
#include <stdint.h>
#include "../phocus_schedule_stage66/wiring66.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Explicitly bounded host-only scalar RGGB pipeline, not a native or device
 * equivalence claim. Every callback uses the existing independently ported
 * kernels from Stage61/62/63/67/68, not placeholder pixel formulas.
 * Scratch planes and all output planes are full stride*height arrays. The
 * caller owns their storage; no allocation, crop, edge extension, RAW import,
 * sensor adaptation, YCC denoising, or colour management is performed here.
 * Signed edge row: smooth(RAW); scale maps: RAW; per-site gradients: signed
 * edge plus separate RAW formula selected by CFA site. Caller-provided
 * threshold floors and scale threshold are NOT fitted to the image.
 */
typedef struct {
    uint16_t *smoothed_raw;
    int16_t *signed_edge;
    float *horizontal_scale;
    float *vertical_scale;
    float *midgreen_scale;
    uint16_t *midgreen_codes;
} HB69Scratch;
typedef struct {
    double scale_threshold;
    int16_t edge_floor;
    int16_t raw_floor;
} HB69Parameters;
typedef struct {
    HB66WiringCounts wiring;
    uint64_t successful_preparations;
    uint64_t real_colour_site_estimates;
    uint64_t real_green_site_masks;
    uint64_t real_opposite_colour_calls;
    uint64_t real_red_blue_green_calls;
    uint64_t colour_sites_with_no_direction;
} HB69Results;
/* Return 0 on successful host composition, negative otherwise.
 * -1 bad pointers, aliases or params, -2 unsupported domain/dispatch,
 * -3 a kernel/event failed. On failure already-written output and scratch
 * data may remain modified, matching the Stage66 callback abort contract.
 */
int hb_interpolate69(const HB66Planes *planes, const HB69Scratch *scratch,
                     HB69Parameters params, HB69Results *results);
#ifdef __cplusplus
}
#endif
#endif
