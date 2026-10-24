#ifndef HB_RAW_GRADIENT67_H
#define HB_RAW_GRADIENT67_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Independent scalar replacement for the eight unsigned RAW-site directional
 * gradients embedded inside the bounded original scalar InterpolateRGB path.
 *
 * Centre points to a real RGGB pixel; a valid 2-cell halo must exist on all
 * sides, stride is in uint16 elements and >=5. Neither a CFA nor borders are
 * inferred. The eight output int16 values have order N,E,S,W,NE,SE,SW,NW.
 * Output must be disjoint from the input stencil. Returns -1 on malformed
 * pointers/stride and 0 on success. Supported raw codes: 0..65535.
 * This routine does NOT implement the separate signed-edge gradient, masks,
 * pixel-loop orchestration, demosaic, or Android preview.
 */
int hb_inline_raw_gradient67(const uint16_t *centre, int stride, int16_t out[8]);
#ifdef __cplusplus
}
#endif
#endif
