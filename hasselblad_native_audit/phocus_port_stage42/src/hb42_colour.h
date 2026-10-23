/* SPDX-License-Identifier: MIT
 * Independently written reference colour fragment. No calibration is bundled.
 * Matrices are row-major. Grid is interleaved Cb,Cr, row-major, double precision.
 * RGB16 input is already unpacked, black-subtracted and demosaiced by caller.
 */
#ifndef HB42_COLOUR_H
#define HB42_COLOUR_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { HB42_OK=0, HB42_INVALID=1, HB42_OVERLAP=2 };
enum { HB42_WB_SEPARATE=0, HB42_WB_IN_MATRIX=1, HB42_WB_IN_INPUT=2 };
typedef struct {
    double first[9], second[9], shadow[4];
    double wb[3], exposure;
    uint32_t wb_owner, width, height;
    double bias_x, bias_y;
    const double *grid;
    size_t grid_count;
    const float *curve;
    size_t curve_count;
} hb42_params;
/* Validation rejects unsupported gray thresholds by construction: this ABI
 * implements the verified zero-threshold/null-calibration SDR fragment only.
 * Caller owns array lifetimes; no concurrent mutation is permitted.
 */
int hb42_validate(const hb42_params *p);
/* No in-place processing. Validation failures leave output untouched. */
int hb42_render(const hb42_params *p, const uint16_t *rgb, size_t pixels,
                uint16_t *out);
#ifdef __cplusplus
}
#endif
#endif
