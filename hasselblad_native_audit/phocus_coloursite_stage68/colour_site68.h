#ifndef HB_COLOUR_SITE68_H
#define HB_COLOUR_SITE68_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Compose Stage61 edge directions, Stage68 RAW colour-site directions, and
 * Stage63 green estimator. Interior, disjoint output buffers required;
 * consumed float scale map entries must be finite nonnegative. Caller owns
 * CFA phase and threshold floors. No DNG parsing, clip, edge extension,
 * profile selection or noise filtering occurs in this adapter.
 */
int hb_colour_site_green68(const uint16_t *raw, const int16_t *edge,
    const float *horizontal, const float *vertical, const float *scale,
    int stride, int16_t edge_floor, int16_t raw_floor,
    int32_t *green, int32_t *direction_mask, int16_t *maximum_gradient);
#ifdef __cplusplus
}
#endif
#endif
