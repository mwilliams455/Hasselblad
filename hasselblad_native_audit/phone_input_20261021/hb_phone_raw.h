/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_RAW_H
#define HB_PHONE_RAW_H
#include "../awb_rebuild_04_20261021/src/hb_awb_frame_stats.h"

enum hb_phone_status { HB_PHONE_OK=0, HB_PHONE_BAD_INPUT=1,
    HB_PHONE_PROCESSED_INPUT=2, HB_PHONE_NO_MEMORY=3 };
enum hb_phone_block_flags { HB_PHONE_NONPOSITIVE=1,
    HB_PHONE_SATURATED=2, HB_PHONE_RATIO_RANGE=4 };
enum hb_phone_history { HB_PHONE_UNTOUCHED_RAW16_LE=0,
    HB_PHONE_PREPROCESSED_OR_UNKNOWN=1 };

typedef struct {
    /* Signed normalized means in R,Gr,Gb,B order. Below-black and above-white
     * values are retained. These are camera sensor coordinates, not XYZ. */
    double mean[4];
    double mean_brightness; /* Arithmetic Bayer mean, not vendor AE or CIE Y. */
    uint32_t red_gain_q12, blue_gain_q12;
    uint32_t flags; /* Any flag makes both ratio outputs zero. */
} hb_phone_block;

typedef struct {
    hb_awb_frame_stats raw; /* Exact signed Q16 sums and original sample counts. */
    hb_phone_block blocks[HB_AWB_FRAME_BLOCKS];
    uint32_t ratio_blocks, nonpositive_blocks, saturated_blocks, range_blocks;
    /* No estimator model, spectral input, exposure scale or calibration is
     * inferred. Even valid ratios are NOT a calibrated AWB estimate. */
} hb_phone_raw_grid;

/* Generic single-frame Bayer RAW16 adapter, <=32 MP, 32x32 Bayer-quad grid.
 * Frame geometry/black/white/CFA must describe THESE delivered bytes, with
 * explicit two-pixel aligned crop and original Bayer phase. Do not feed an
 * already normalized, shaded, white-balanced or demosaiced buffer.
 * Each site's normalization is (code-black_site)/(white-black_site).
 * The two normalized green means are averaged before forming G/R and G/B.
 * Ratios truncate to Q12; out-of-range, nonpositive or saturated blocks are
 * marked unusable, never silently clipped. Raw sums/headroom always remain.
 * Failure leaves output untouched. Input and output buffers must not overlap.
 * This does not create vendor E2 bytes or initialize/call hb_run_automatic.
 * The caller must bind metadata to the delivered physical camera/frame.
 */
int hb_phone_raw_build(const uint8_t *raw, size_t raw_bytes,
    const hb_awb_frame_input *frame, enum hb_phone_history history,
    hb_phone_raw_grid *out);
#endif
