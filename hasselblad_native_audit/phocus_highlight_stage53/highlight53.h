#ifndef HB_HIGHLIGHT53_H
#define HB_HIGHLIGHT53_H
#include <stddef.h>
#include <stdint.h>

/* Research primitive, before camera-to-colourimetric conversion.
 * No WB, exposure, tone mapping or output encoding should be added implicitly.
 * prepare: 0 = native regular domain; 1 = explicitly enabled analytic limit;
 * -1 = invalid input; -2 = equal lower gains without explicit limit permission.
 */
typedef struct {
    int order[3], undo[3], limit_mode;
    double limits[3], weights[3], middle[3], full[3], projection[3], red_projection[3];
} hb_highlight53;
int hb_highlight53_prepare(hb_highlight53 *out, const double gains[3],
                          const uint16_t truncation[3], int allow_equal_gain_limit);
/* Use only successfully prepared parameters, unchanged. Identical input/output
 * pointers are supported; other overlapping buffers are not supported.
 * RGB16 contains linear sensor samples. */
int hb_highlight53_rgb16(const hb_highlight53 *p, const uint16_t *in,
                        uint16_t *out, size_t pixels);
/* Float input must be finite and nonnegative; output remains in sensor RGB. */
int hb_highlight53_float(const hb_highlight53 *p, const float *in,
                        float *out, size_t pixels);
#endif
