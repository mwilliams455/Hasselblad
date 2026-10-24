#ifndef HB_GREEN63_H
#define HB_GREEN63_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Independent green-at-red/blue estimator. Inputs address the centre of
 * disjoint planes with a two-row/two-column halo, stride >= 5 in elements.
 * All consumed scale-map samples must be finite and nonnegative. Direction arrays
 * contain eight signed codes, ordered N,E,S,W,NE,SE,SW,NW. Threshold floors
 * are explicit caller-owned signed codes, not camera/profile constants.
 * No CFA selection, edge extension, allocation or object ownership occurs.
 * Output scalars must be mutually disjoint and must not alias any input.
 * Native float fused multiply-add and FCVTZS saturation are explicit.
 */
void hb_green_at_colour63(const uint16_t *raw, const float *horizontal,
    const float *vertical, const float *scale, int stride,
    const int16_t first[8], const int16_t second[8],
    int16_t first_floor, int16_t second_floor,
    int32_t *green, int32_t *mask, int16_t *maximum_gradient);

#ifdef __cplusplus
}
#endif
#endif
