#ifndef HB_GREEN_SITE_MASK67_H
#define HB_GREEN_SITE_MASK67_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Compose the PREVIOUSLY VERIFIED Stage61 signed-edge direction and packed
 * mask functions with the new RAW-site gradient67. This is an explicit bridge
 * for Stage66's green-site mask callback, not full InterpolateRGB equivalence.
 * Inputs require two-cell halo, stride >=5, and disjoint output storage.
 * The directional threshold floors belong to the caller, not to a fitted
 * scene. The two intermediate arrays must have at least eight int16 slots.
 */
int hb_green_site_mask67(const uint16_t *raw_centre,
                         const int16_t *edge_centre, int stride,
                         int16_t first_floor, int16_t second_floor,
                         int16_t signed_gradients[8],
                         int16_t raw_gradients[8], uint16_t *packed_mask);
#ifdef __cplusplus
}
#endif
#endif
