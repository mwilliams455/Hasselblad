/* SPDX-License-Identifier: MIT
 * Native1C RAW scene preparation — an owned, explicit, conservative replay
 * contract. NOT a copy of X2D II E2, AE, classification or weighting code.
 * No sensor calibration is inferred. No white balance or CCT is produced.
 */
#ifndef HB_AWB_SCENE_PREPARE_H
#define HB_AWB_SCENE_PREPARE_H
#include <stddef.h>
#include <stdint.h>
#include "hb_awb_frame_stats.h"
#define HB_AWB_GAIN_Q16_MAX (8u * 65536u)
#define HB_AWB_BIAS_Q16_MAX (INT64_C(2048) * INT64_C(65536))
#define HB_AWB_EVIDENCE_PPM UINT64_C(1000000)

typedef struct hb_awb_explicit_calibration {
    /* Per-site gain and bias supplied by caller, in R/Gr/Gb/B order. A unity
     * gain is 65536; each site is modified independently. The exact original
     * firmware calibration coefficents have NOT been recovered. */
    uint32_t channel_gain_q16[4];
    int64_t channel_bias_q16[4]; /* per CFA sample; applied AFTER both gains */
    /* Optional 1024-cell gain; NULL explicitly means unity for ALL cells.
     * Separate spatial component allows lens variation without inventing LUT. */
    const uint32_t *spatial_gain_q16;
} hb_awb_explicit_calibration;

typedef struct hb_awb_ae_evidence {
    /* Input is RAW black-subtracted signal; negative values survive. Values
     * indicate signal *availability*, not original scene AE classification. */
    int64_t raw_block_mean_q16[HB_AWB_FRAME_BLOCKS];
    uint32_t at_or_above_white_ppm[HB_AWB_FRAME_BLOCKS];
    uint32_t at_or_below_black_ppm[HB_AWB_FRAME_BLOCKS];
    int64_t total_raw_sum_q16;
    uint64_t total_samples;
    uint64_t total_at_or_above_white;
    uint64_t total_at_or_below_black;
    int64_t frame_raw_mean_q16;
    uint8_t vendor_ae_equivalence_proven; /* Always 0 */
} hb_awb_ae_evidence;

typedef struct hb_awb_replay_masks {
    /* Original per-block classifier, zone rules and numerical weight formula
     * were lost. Caller MUST provide a classified mask and final weights.
     * Classifier-rejected but weighted blocks require explicit zone origin.
     */
    uint8_t classifier_accepted[HB_AWB_FRAME_BLOCKS];
    uint8_t zone_override[HB_AWB_FRAME_BLOCKS];
    uint8_t final_weight[HB_AWB_FRAME_BLOCKS];
    enum hb_awb_connectivity neighbours;
} hb_awb_replay_masks;

typedef struct hb_awb_scene_prepare_result {
    hb_awb_frame_stats calibrated; /* Only site sums altered, raw remains raw */
    hb_awb_ae_evidence ae;
    hb_awb_scene_accumulation accumulation;
    uint32_t weighted_from_zone_not_classifier;
    uint32_t weighted_from_classifier;
    uint32_t weighted_with_both_origins;
    uint8_t vendor_calibration_equivalence_proven; /* Always 0 */
    uint8_t vendor_classification_equivalence_proven; /* Always 0 */
    uint8_t produces_selected_neutral; /* Always 0 */
} hb_awb_scene_prepare_result;

/* Must operate on an owned RAW block structure. This is an intentionally
 * explicit arithmetic contract: colour_sum' = trunc0(
 *   trunc0(original_site_sum * channel_gain / 65536)
 *   * spatial_gain / 65536) + site_count * channel_bias.
 * Brightness, counts, saturation flags and uncalibrated input are unchanged.
 * Signed values are kept, overflow is rejected, no output on failure.
 */
int hb_awb_apply_explicit_calibration(const hb_awb_frame_stats *input,
                                     const hb_awb_explicit_calibration *calibration,
                                     hb_awb_frame_stats *output);

int hb_awb_prepare_raw_ae_evidence(const hb_awb_frame_stats *input,
                                   hb_awb_ae_evidence *output);

/* These are supplied classification/weighting RESULTS, not an algorithm
 * inferred from vendor firmware. Only the supported zone-reweighting case
 * is admitted. A bad/unsupported fixture never partially changes output.
 */
int hb_awb_scene_prepare_bounded(const hb_awb_frame_stats *original,
                                 const hb_awb_explicit_calibration *calibration,
                                 const hb_awb_replay_masks *recorded,
                                 hb_awb_scene_prepare_result *out);
#endif