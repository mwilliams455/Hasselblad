#ifndef HB_SHARPEN85_H
#define HB_SHARPEN85_H
#include <stddef.h>
#include <stdint.h>
/* Bounded full-resolution SDR CPU path. No blur, layers or resize compensation. */
int hb85_tables(int amount, double radius, int noise, int dark,
                int32_t amount_table[16384], uint8_t noise_table[16384],
                uint32_t weights[9], int *taps);
/* RGB14 input/output, row-major interleaved. Replicate-edge fixture. */
int hb85_sharpen14(const uint16_t *input, uint16_t *output, size_t width,
                  size_t height, int amount, double radius, int noise, int dark);
#endif
