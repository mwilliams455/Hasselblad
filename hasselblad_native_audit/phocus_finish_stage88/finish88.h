#ifndef HB_FINISH88_H
#define HB_FINISH88_H
#include <stddef.h>
#include <stdint.h>
/* Same Stage55 operations with bounded, process-owned lookup caches. */
int hb88_gradate(const uint16_t *input,size_t pixels,uint16_t *output);
int hb88_output_rgb16(const uint16_t *input,size_t pixels,const double matrix[9],
                     double exponent,uint16_t *output);
#ifdef HB88_TESTING
unsigned long hb88_decode_builds(void);
unsigned long hb88_curve_builds(void);
#endif
#endif
