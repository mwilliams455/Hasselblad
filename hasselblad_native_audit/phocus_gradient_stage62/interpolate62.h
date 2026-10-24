#ifndef HB_GRADIENT_INTERPOLATE62_H
#define HB_GRADIENT_INTERPOLATE62_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Native CPU helper scope: center pointers into valid 16-bit sample planes
 * with one-site horizontal and vertical/diagonal halos, positive stride.
 * Mask bits correspond to the upstream 8-direction selection; each set bit
 * contributes one weighted estimate only when its green denominator is nonzero.
 * Calling code is responsible for CFA, allocation, and halo discipline.
 *
 * Returns the full 32-bit AArch64-style W0 code (including its low 16 bits).
 * A native caller may narrow this result to 16 bits when writing RGB planes.
 */
uint32_t hb_blue_at_red_code62(const uint16_t *blue, const uint16_t *green,
                               uint32_t mask, int stride);
/* Returns 0 on success, -1 for invalid pointers/stride. Snapshot of relevant
 * source samples precedes BOTH output writes, preserving in-place aliases.
 */
int hb_red_blue_at_green62(const uint16_t *red, const uint16_t *green,
                           const uint16_t *blue, uint16_t *out_red,
                           uint16_t *out_blue, uint32_t mask, int stride);
#ifdef __cplusplus
}
#endif
#endif
