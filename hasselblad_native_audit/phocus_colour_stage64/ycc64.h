#ifndef HB_DIRECTIONAL_YCC64_H
#define HB_DIRECTIONAL_YCC64_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Candidate independent implementation of the bounded original CPU
 * DirectionalColorCorrectionYCC path. No image edges or CFA discovery.
 *
 * All input pointers are centred on the same pixel and support two-sided
 * offsets {1,stride,stride-1,stride+1} in uint16/int16 *elements*.
 * The mask has eight low direction bits and a four-bit count at bits 8..11;
 * output references must be disjoint and not alias source arrays.
 * This is pre-native-parity research, NOT yet a verified Phocus port.
 */
int hb_directional_ycc64(uint32_t direction_mask,
                         const uint16_t *centre_y,
                         const int16_t *centre_c1, const int16_t *centre_c2,
                         const uint16_t *neighbours_y,
                         const int16_t *neighbours_c1,
                         const int16_t *neighbours_c2,
                         uint16_t *out_y,
                         int16_t *out_c1, int16_t *out_c2,
                         int16_t *out_level,
                         int stride);
#ifdef __cplusplus
}
#endif
#endif
