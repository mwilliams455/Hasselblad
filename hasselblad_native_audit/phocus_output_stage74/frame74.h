#ifndef HB_FRAME74_H
#define HB_FRAME74_H
#include <stddef.h>
#include <stdint.h>
#include "../phocus_frame_stage73/frame73.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Genuine independent bounded final linear RGB16: interpolation ->
 * ColorNoise -> YCC output conversion. No DNG import, sensor colour LUT,
 * display transform, edge inference, AF or HDR. Exactly Stage73 supported
 * output geometries with its explicit 32px pre-prepared Bayer halo.
 */
typedef struct HB74Receipt {
    uint64_t interpolation_events;
    uint64_t colour_site_estimates;
    uint64_t red_blue_green_calls;
    uint64_t colornoise_converted_sites;
    uint64_t colornoise_correction_sites;
    uint64_t colornoise_directional_sites;
    uint64_t final_rgb16_pixels;
    size_t allocated_bytes;
} HB74Receipt;
/* 0 success; -1 invalid args, -2 unsupported contract, -3 allocation,
 * -4 independent interpolation failure, -5 independent ColorNoise failure,
 * -6 output-conversion failure. Outputs unchanged on all nonzero statuses. */
int hb74_render_final_bounded(const HB73Plan *plan,const HB73Settings *settings,
    const uint16_t *input,size_t input_count,int input_stride,
    uint16_t *rgb,size_t rgb_count,HB74Receipt *receipt);
#ifdef __cplusplus
}
#endif
#endif
