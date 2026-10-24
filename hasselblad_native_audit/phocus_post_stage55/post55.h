#ifndef HB_POST55_H
#define HB_POST55_H
#include <stddef.h>
#include <stdint.h>

/* Unedited SDR defaults only. No profile matrices or vendor tables embedded. */
int hb55_default_curve(uint16_t *curve);
/* Native version 1 hue preservation with identity contrast/luma curves.
 * Exact input/output aliasing is supported; other overlap is not supported. */
int hb55_gradate(const uint16_t *curve,const uint16_t *input,size_t pixels,uint16_t *output);
/* Power-decoded internal RGB to explicitly supplied linear-sRGB matrix,
 * followed by sRGB transfer and the native CPU uint16 quantization. */
int hb55_output_rgb16(const uint16_t *input,size_t pixels,const double matrix[9],
                     double exponent,uint16_t *output);
#endif
