#ifndef HB_COLOUR_GRADIENT68_H
#define HB_COLOUR_GRADIENT68_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Independently reconstructed RAW16 gradients used by the scalar
 * InterpolateRGB at the two colour (R/B) sites. Inputs must point to an
 * interior 5x5 source neighbourhood, stride >= 5 elements. Aligned RGGB is
 * selected by the calling scheduler; this helper does not extend edges.
 * Result order: N,E,S,W,NE,SE,SW,NW; signed 16-bit low-bit wrap semantics.
 * The first four directions deliberately reuse Stage67's independently
 * verified cardinal calculations. The last four use the colour-site-only
 * six-difference diagonals recovered in Stage68.
 */
int hb_colour_raw_gradient68(const uint16_t *raw, int stride, int16_t out[8]);
#ifdef __cplusplus
}
#endif
#endif
