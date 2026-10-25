#ifndef HB_FRAME77_H
#define HB_FRAME77_H
#include <stddef.h>
#include <stdint.h>
/* Same sensor-interior band contract as Stage76. Width is 128..8192;
 * output is (raw_width-64)&~1. At most four isolated workers. Input is
 * immutable and output is unchanged on failure. No global mutable state. */
int hb77_render_band(const uint16_t *band,size_t input_count,int raw_width,
    int row_offset,int row_count,int workers,uint16_t *output,size_t output_capacity);
#endif
