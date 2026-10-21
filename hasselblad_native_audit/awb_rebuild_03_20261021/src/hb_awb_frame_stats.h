/* SPDX-License-Identifier: MIT
 * Owned RAW-to-1024-block statistics adapter, NOT original X2D E2 ABI.
 * Its functions preserve raw brightness and signed black-subtracted headroom.
 */
#ifndef HB_AWB_FRAME_STATS_H
#define HB_AWB_FRAME_STATS_H
#include <stddef.h>
#include <stdint.h>
#include "hb_awb_stages.h"

#define HB_AWB_Q16_ONE INT64_C(65536)
#define HB_AWB_MAX_FRAME_PIXELS UINT64_C(32000000)
#define HB_AWB_MAX_SYNTHETIC_WEIGHT 32u

enum hb_awb_colour_site { HB_AWB_RED=0, HB_AWB_GREEN_RED_ROW=1,
    HB_AWB_GREEN_BLUE_ROW=2, HB_AWB_BLUE=3 };
/* Bayer pattern order is the original sensor's top-left 2x2, not a cropped
 * output with an independently reset phase. */
enum hb_awb_cfa { HB_AWB_RGGB=0, HB_AWB_GRBG=1, HB_AWB_GBRG=2,
                  HB_AWB_BGGR=3 };

typedef struct hb_awb_frame_input {
    uint32_t width, height;
    uint32_t row_stride_bytes, pixel_stride_bytes;
    uint32_t left, top, right, bottom; /* [left,right)x[top,bottom), absolute */
    enum hb_awb_cfa cfa;
    int64_t black_q16[4]; /* Original 2x2 site order, signed raw-code Q16. */
    uint16_t white_code; /* Sensor white threshold, not clamping bound. */
} hb_awb_frame_input;

typedef struct hb_awb_stat_block {
    int64_t site_sum_q16[4]; /* R, Gr, Gb, B; signed, no clipping. */
    uint32_t site_count[4];
    int64_t raw_brightness_sum_q16; /* RAW arithmetic sum, NOT CIE Y/E2 vendor field. */
    uint32_t sample_count;
    uint32_t at_or_above_white_count;
    uint32_t above_white_count;
    uint32_t at_or_below_black_count;
    uint16_t min_sample;
    uint16_t max_sample;
} hb_awb_stat_block;

typedef struct hb_awb_frame_stats {
    hb_awb_stat_block blocks[HB_AWB_FRAME_BLOCKS];
    uint64_t input_sample_count;
    uint8_t vendor_e2_equivalence_proven; /* Always 0. */
} hb_awb_frame_stats;

/* Accepts a 16-bit little-endian RAW_SENSOR stream, with explicitly retained
 * row/pixel strides and 2x2 aligned crop. Blocks partition Bayer QUADS into
 * 32x32, preventing CFA phase changes at non-divisible bin boundaries.
 * All colour transforms/CCM/LUT/WB are absent. Zero is owned success.
 */
int hb_awb_raw_to_block_stats(const uint8_t *raw, size_t raw_bytes,
                              const hb_awb_frame_input *frame,
                              hb_awb_frame_stats *out);

typedef struct hb_awb_scene_accumulation {
    int64_t weighted_site_sum_q16[4];
    uint64_t weighted_site_count[4];
    int64_t weighted_raw_brightness_q16;
    uint64_t weighted_sample_count;
    uint64_t weighted_at_or_above_white_count;
    uint32_t surviving_blocks;
    uint32_t weighted_but_unclassified_blocks;
    hb_awb_component_stats filter;
    uint8_t vendor_candidate_equivalence_proven; /* Always 0. */
} hb_awb_scene_accumulation;

/* Caller supplies PRE-COMPUTED weights and optional classifier-acceptance
 * flags. The weighting policy and original zone/classifier are UNKNOWN.
 * Synthetic weight is bounded to 0..32. Selected blocks undergo Rebuild01
 * connected-component pruning under EXPLICIT 4/8-neighbour topology.
 */
int hb_awb_accumulate_owned_candidates(const hb_awb_frame_stats *frame,
            const uint8_t weights[HB_AWB_FRAME_BLOCKS],
            const uint8_t *accepted_by_classifier,
            enum hb_awb_connectivity neighbours,
            hb_awb_scene_accumulation *out);
#endif