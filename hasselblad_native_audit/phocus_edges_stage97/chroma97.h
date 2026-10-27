#ifndef HB_CHROMA97_H
#define HB_CHROMA97_H
#include <stddef.h>
#include <stdint.h>
/* Source-camera RGB16 in, centre (width-4)x(height-4) out. Two real halo
 * pixels on every side; no reflection at internal tile/band boundaries.
 * Ratios are R/G and B/G. Input/output must not overlap. No state is retained.
 * All validation/allocation precedes output writes. */
int hb97_chroma_roi(const uint16_t *rgb,size_t input_count,int width,int height,
    double nr,double nb,uint16_t *output,size_t output_capacity);
#endif
