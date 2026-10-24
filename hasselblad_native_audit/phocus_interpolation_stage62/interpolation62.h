#ifndef HB_INTERPOLATION62_H
#define HB_INTERPOLATION62_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Independent integer interpolation primitives. Pointers address the centre
 * of valid uint16 planes, with a one-row/one-column halo and stride >= 3.
 * Stride is in elements. No CFA selection or image-edge extension occurs.
 * Only the low eight mask bits select directions; higher bits are ignored.
 *
 * The blue-at-red return preserves the native signed 32-bit register result.
 * Its caller stores the low 16 bits. This is an upper-only signed clamp,
 * NOT an ordinary 0..65534 saturation; wrapped negative results are retained.
 */
int32_t hb_blue_at_red62(const uint16_t *colour, const uint16_t *green,
                         uint32_t mask, int stride);

/* Inputs are fully sampled before outputs are written. Outputs may alias
 * input planes, each other, or neighbour sites. Second is written before
 * first, matching the native call contract. Inputs are unchanged except at
 * explicitly aliased output addresses. Outputs store the low 16 bits.
 */
void hb_red_blue_at_green62(const uint16_t *first, const uint16_t *green,
                            const uint16_t *second, uint16_t *out_first,
                            uint16_t *out_second, uint32_t mask, int stride);

#ifdef __cplusplus
}
#endif
#endif
