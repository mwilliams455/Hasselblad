#ifndef HB_GRADIENT_MAPS61_H
#define HB_GRADIENT_MAPS61_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Independently implemented gradient prepasses. Buffers have height*stride
 * elements and must not overlap. Bounds are [x0,x1),[y0,y1), in aligned RGGB
 * coordinates, visited in 2x2 cells. Outputs outside the written sites retain
 * their incoming values. No edge extension is performed. Return 0 on success,
 * -1 for unsupported arguments. Compile without fast math or FP contraction.
 *
 * Scale maps interleave green-site ratios with adjacent contrast values. A
 * below-threshold stencil stores ratio 1 and leaves its contrast slot intact.
 */
int hb_gradient_scale61(const uint16_t *raw, int width, int height, int stride,
                        int x0, int y0, int x1, int y1, double threshold,
                        float *horizontal, float *vertical);

/* Input maps must contain finite nonnegative values produced by the scale
 * prepass (or explicit equivalent fixtures). Only red/blue sites are written.
 */
int hb_gradient_green61(const uint16_t *raw, int width, int height, int stride,
                        int x0, int y0, int x1, int y1,
                        const float *horizontal, const float *vertical,
                        float *scale, uint16_t *green);

/* Row filters require a complete previous/current/next source row, with
 * row pointing at the current row. Width >= 2, stride >= width; no aliasing.
 * The signed median routine is the median of three row medians, not a full
 * nine-sample median. Smoothing/edge borders are zero; median borders copy.
 */
int hb_gradient_smooth_row61(const uint16_t *row, uint16_t *out, int stride, int width);
int hb_gradient_edge_row61(const uint16_t *row, int16_t *out, int stride, int width);
int hb_gradient_median_row61(const int16_t *row, int16_t *out, int stride, int width);

/* Center needs a 5x5 signed stencil. Output order: N,E,S,W,NE,SE,SW,NW.
 * Narrowing preserves the native low sixteen bits, including wraparound.
 */
int hb_gradient_directions61(const int16_t *center, int stride, int16_t out[8]);
uint16_t hb_gradient_mask61(const int16_t first[8], const int16_t second[8],
                            int16_t first_floor, int16_t second_floor);

#ifdef __cplusplus
}
#endif
#endif
