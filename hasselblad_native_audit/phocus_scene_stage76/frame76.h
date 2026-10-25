#ifndef HB_FRAME76_H
#define HB_FRAME76_H
#include <stddef.h>
#include <stdint.h>
/* Assemble only the sensor interior, using exact 64x64 Stage74 calls.
 * band contains 128 complete sensor rows. Output width is (raw_width-64)&~1.
 * row_offset/row_count select rows inside each 64-row tile output.
 * No invented sensor-border samples, new CFA, or native Phocus full-frame claim.
 * Output is unchanged on any error. Input/output must not overlap. */
int hb76_render_band(const uint16_t *band,size_t input_count,int raw_width,
    int row_offset,int row_count,uint16_t *output,size_t output_capacity);
#endif
