#ifndef HB_NOISE65_H
#define HB_NOISE65_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Independent scene-agnostic ColorNoise implementation for bounded CPU routes.
 * Status 0: executed supported path; -1: bad arguments; -2: an original path
 * requiring unported getYErrorMapShort / ColorFilter2Short. No side effects
 * occur on -1/-2. The passed arrays are separate, stride-wide planes of
 * height rows; width<=stride. No edge extension or hidden allocations.
 * Pointers and coefficients are explicit; no private camera data is included.
 *
 * Flags bit5: RGB->YCC interior (8px margin) and sequential 3x3 Y clamp.
 * Flags bit6, optimized_view=0: row smoothing/median and optional directional
 * YCC correction (12px margin). Alternative native class is not replicated.
 * With flag bit6, strength must be zero or negative; positive strength uses
 * additional unsupported original functions and returns -2.
 * The candidate YCC kernel is from Stage64 and needs separate original-CPU
 * confirmation before full-stage parity can be claimed.
 */
typedef struct HBNoiseContext65 {
    int width, height, stride;
    uint16_t flags;
    uint8_t optimized_view;
    int32_t strength;
    const uint16_t *red, *green, *blue;
    uint16_t *y;
    int16_t *c1, *c2;
    const uint16_t *direction_mask;
    uint16_t *smooth_y;
    int16_t *median_c1, *median_c2;
    uint16_t *out_y;
    int16_t *out_c1, *out_c2, *out_aux;
} HBNoiseContext65;

typedef struct HBNoiseCounters65 {
    uint64_t converted_sites;
    uint64_t clamped_sites;
    uint64_t smoothing_rows;
    uint64_t median_rows;
    uint64_t correction_sites;
    uint64_t nonzero_mask_sites;
    uint64_t median_selected_sites;
} HBNoiseCounters65;

int hb_color_noise65(HBNoiseContext65 *ctx, HBNoiseCounters65 *counts);
int hb_color_noise_prepare65(const HBNoiseContext65 *ctx, HBNoiseCounters65 *counts);
int hb_color_noise_rows65(const HBNoiseContext65 *ctx, HBNoiseCounters65 *counts);
int hb_color_noise_correct65(const HBNoiseContext65 *ctx, HBNoiseCounters65 *counts);
#ifdef __cplusplus
}
#endif
#endif
