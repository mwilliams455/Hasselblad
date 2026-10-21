/* SPDX-License-Identifier: MIT
 * Hasselblad Photon: bounded scene-AWB recovery checkpoint, 2026-10-21.
 * Source: recorded original X2D II firmware 1.3.16.2 research conclusions.
 * This is a partial reimplementation, NOT original-firmware equivalence.
 */
#ifndef HB_AWB_STAGES_H
#define HB_AWB_STAGES_H
#include <stddef.h>
#include <stdint.h>

#define HB_AWB_CONTEXT_BYTES ((size_t)920560)
#define HB_AWB_REAWB_BYTES ((size_t)1000)
#define HB_AWB_CONFIG_BYTES ((size_t)1502800)
#define HB_AWB_FRAME_BLOCKS_X 32u
#define HB_AWB_FRAME_BLOCKS_Y 32u
#define HB_AWB_FRAME_BLOCKS 1024u
#define HB_AWB_RESULT_BYTES ((size_t)156)

/* Layout addresses recorded at the last verified original-source checkpoint. */
#define HB_AWB_CLEAR_OFFSET ((size_t)0x174)
#define HB_AWB_REFERENCE_REQUEST_OFFSET ((size_t)0xd338)
#define HB_AWB_REFERENCE_RESULT_OFFSET ((size_t)0xd3d8)
#define HB_AWB_LIVE_A_OFFSET ((size_t)0xb0c48)
#define HB_AWB_LIVE_B_OFFSET ((size_t)0xb0ce4)
#define HB_AWB_CONFIRMED_A_OFFSET ((size_t)0xb0d80)
#define HB_AWB_CONFIRMED_B_OFFSET ((size_t)0xb0e1c)
#define HB_AWB_SHADING_VALIDITY_OFFSET ((size_t)-1) /* Not recovered. Caller supplies validity. */
#define HB_AWB_SHADING_REFERENCE_CT_OFFSET ((size_t)0xf008)
#define HB_AWB_SHADING_NORMAL_CT_OFFSET ((size_t)0xb0b6c)
#define HB_AWB_SHADING_OUTPUT_CT_OFFSET ((size_t)0xb2164)
#define HB_AWB_SHADING_PRIMARY_LABEL_OFFSET ((size_t)0xeff8)
#define HB_AWB_SHADING_PRIMARY_COUNT_OFFSET ((size_t)0xeffc)

/* These owned statuses must never be presented as original vendor return codes. */
enum hb_awb_rebuild_status {
    HB_AWB_REBUILD_OK = 0,
    HB_AWB_REBUILD_BAD_INPUT = -1,
    HB_AWB_REBUILD_UNSUPPORTED = -2,
    HB_AWB_REBUILD_CONTINUE_ORIGINAL = 1
};
enum hb_awb_result_origin {
    HB_AWB_ORIGIN_UNKNOWN = 0,
    HB_AWB_ORIGIN_LIVE_PUBLISHED = 1,
    HB_AWB_ORIGIN_RESTORED_CONFIRMED = 2,
    HB_AWB_ORIGIN_REFERENCE_OVERRIDE = 3
};

/* Describes a bounded cleanup branch. final_copy_status is a caller-supplied
 * result of the later original copy helper (0 in known witness cases); this
 * model does not claim to re-create the helper's ABI or error conditions. */
typedef struct hb_awb_completion {
    int preceding_status;
    int final_copy_status;
    int outer_status;
    enum hb_awb_result_origin origin;
    uint8_t reference_request_consumed;
    uint8_t fresh_estimate_proven; /* ALWAYS 0: status alone cannot prove freshness. */
} hb_awb_completion;
int hb_awb_outer_complete_bounded(uint8_t *context, size_t context_bytes,
                                  int preceding_status, int final_copy_status,
                                  hb_awb_completion *out);

/* Explicitly bounded scene entry: only ordinary illumination 0 / scene 3
 * sole-eligible case was historically verified. No synthetic scene estimates. */
typedef struct hb_awb_scene_entry {
    uint32_t ordinary_illumination;
    uint32_t eligible_scene_mask; /* bit N corresponds to scene N */
} hb_awb_scene_entry;
enum hb_awb_scene_decision {
    HB_AWB_SCENE_BAD_INPUT = -1,
    HB_AWB_SCENE_UNSUPPORTED = -2,
    HB_AWB_SCENE_NO_ELIGIBLE = 40, /* Original inner scene status, NOT outer status. */
    HB_AWB_SCENE_SUPPORTED_SELECTED = 1001 /* Owned sentinel; NOT vendor code. */
};
int hb_awb_select_supported_scene(const hb_awb_scene_entry *in);
int hb_awb_recover_no_eligible(uint8_t *context, size_t bytes,
                               const hb_awb_scene_entry *entry,
                               hb_awb_completion *out);

/* Recorded selected-label rule. The array supplies each authentic vendor label
 * ID: memory offsets for the seven source ratios were NOT retained.
 * The input is pre-extracted, not a guessed original struct layout. */
typedef struct hb_awb_shading_choice {
    uint16_t label_ratio[7];
    uint8_t vendor_label_id[7];
    uint8_t validity;
} hb_awb_shading_choice;
typedef struct hb_awb_shading_result {
    uint8_t selected_label_id;
    uint8_t selected_index;
    uint16_t selected_ratio;
    uint32_t chosen_ct;
    uint8_t from_reference_ct;
    uint8_t published;
} hb_awb_shading_result;
int hb_awb_shading_select_bounded(uint8_t *context, size_t bytes,
                                  const hb_awb_shading_choice *choice,
                                  hb_awb_shading_result *out);

/* Exact validity-byte gates from the historical post-publication stage:
 * any nonzero publishes candidate; ONLY exact 1 copies it into history.
 * Caller owns all buffers. Original field offsets/copy sizes are unknown.
 */
typedef struct hb_awb_publication_flags {
    uint8_t candidate_published;
    uint8_t history_copied;
} hb_awb_publication_flags;
int hb_awb_publication_gates(uint8_t validity, const uint8_t *candidate,
                             uint8_t *published, uint8_t *history,
                             size_t bytes, hb_awb_publication_flags *out);

/* Bounded filtering rule. Original connected-component NEIGHBOR TOPOLOGY
 * was not retained; it is an explicit input, never silently assumed. */
enum hb_awb_connectivity { HB_AWB_NEIGHBORS_FOUR = 4, HB_AWB_NEIGHBORS_EIGHT = 8 };
typedef struct hb_awb_component_stats {
    uint16_t groups_removed;
    uint16_t groups_kept;
    uint16_t blocks_removed;
    uint16_t blocks_kept;
} hb_awb_component_stats;
int hb_awb_prune_small_components(const uint8_t *weighted_mask,
                                  uint8_t *filtered_mask,
                                  enum hb_awb_connectivity neighbors,
                                  hb_awb_component_stats *stats);

uint32_t hb_awb_clamp_ct(uint32_t kelvin); /* recorded [2000,10000] K range */
#endif