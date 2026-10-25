#ifndef HB_OUTPUT74_H
#define HB_OUTPUT74_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Native-scalar YCC->RGB encoding for the bounded supported graph; gain is
 * deliberately restricted to unity. Independent code; no private profiles.
 * Y, Cr, Cb are the post-ColorNoise output planes, *not* raw RGB inputs.
 * This is the internal linear RGB16 output, not display sRGB or film colour.
 */
int hb74_ycc_to_rgb_pixel(uint16_t y, int16_t cr, int16_t cb,
                          double gain, uint16_t rgb[3]);
/* Crop plane-stride YCC work arrays to interleaved RGB16. All source planes
 * disjoint from writable destination. Caller supplies valid full array spans.
 * Returns -1 for argument error, -2 for unsupported parameters, 0 success.
 * A failed call leaves the output buffer untouched.
 */
int hb74_convert_roi(const uint16_t *y, const int16_t *cr, const int16_t *cb,
                     int work_width,int work_height,int work_stride,
                     int crop_x,int crop_y,int out_width,int out_height,
                     double gain,uint16_t *rgb,size_t output_elements);
#ifdef __cplusplus
}
#endif
#endif
