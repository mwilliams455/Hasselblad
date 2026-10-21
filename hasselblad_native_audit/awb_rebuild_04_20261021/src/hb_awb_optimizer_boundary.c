/* SPDX-License-Identifier: MIT */
#include "hb_awb_optimizer_boundary.h"
#include <limits.h>
#include <string.h>

static uint64_t fnv_u64(uint64_t state, uint64_t v) {
    for (unsigned n = 0; n != 8u; ++n) {
        state ^= (uint8_t)(v >> (8u * n));
        state *= UINT64_C(1099511628211);
    }
    return state;
}

uint64_t hb_awb_accumulation_fingerprint(const hb_awb_scene_accumulation *a) {
    if (!a) return 0;
    uint64_t h = HB_AWB_OPT_FINGERPRINT_SEED;
    /* Hash named fields in fixed order; no C padding, endian or pointer ABI. */
    for (unsigned i = 0; i != 4u; ++i) {
        h = fnv_u64(h, (uint64_t)a->weighted_site_sum_q16[i]);
        h = fnv_u64(h, a->weighted_site_count[i]);
    }
    h = fnv_u64(h, (uint64_t)a->weighted_raw_brightness_q16);
    h = fnv_u64(h, a->weighted_sample_count);
    h = fnv_u64(h, a->weighted_at_or_above_white_count);
    h = fnv_u64(h, a->surviving_blocks);
    h = fnv_u64(h, a->weighted_but_unclassified_blocks);
    h = fnv_u64(h, a->filter.groups_removed);
    h = fnv_u64(h, a->filter.groups_kept);
    h = fnv_u64(h, a->filter.blocks_removed);
    h = fnv_u64(h, a->filter.blocks_kept);
    return h;
}

int hb_awb_optimizer_stage_observation(const hb_awb_scene_accumulation *acc,
                                       const hb_awb_optimizer_trace *trace,
                                       hb_awb_optimizer_staged *out) {
    if (!acc || !trace || !out || trace->revision != HB_AWB_OPT_TRACE_REVISION ||
        !trace->frame_serial || !trace->caller_window_observed ||
        !acc->surviving_blocks || !acc->weighted_sample_count ||
        acc->surviving_blocks > HB_AWB_FRAME_BLOCKS ||
        acc->weighted_but_unclassified_blocks > acc->surviving_blocks ||
        acc->filter.blocks_kept != acc->surviving_blocks ||
        acc->filter.blocks_kept + acc->filter.blocks_removed > HB_AWB_FRAME_BLOCKS ||
        acc->vendor_candidate_equivalence_proven)
        return HB_AWB_REBUILD_BAD_INPUT;
    uint64_t fingerprint=hb_awb_accumulation_fingerprint(acc);
    if (trace->expected_accumulation_fingerprint != fingerprint)
        return HB_AWB_REBUILD_UNSUPPORTED;
    hb_awb_optimizer_staged record={0};
    record.frame_serial=trace->frame_serial;
    record.input_fingerprint=fingerprint;
    record.observed_optimizer_status=trace->observed_optimizer_status;
    record.caller_delta_candidates=trace->observed_caller_delta_candidates;
    record.caller_delta_blocks=trace->observed_caller_delta_blocks;
    record.caller_delta_samples=trace->observed_caller_delta_samples;
    memcpy(record.opaque_result,trace->opaque_result,sizeof(record.opaque_result));
    *out=record;
    return HB_AWB_REBUILD_OK;
}

int hb_awb_optimizer_apply_observed_caller_update(
        const hb_awb_optimizer_staged *staged,
        hb_awb_optimizer_caller_state *state) {
    if (!staged || !state || !staged->frame_serial ||
        staged->frame_serial <= state->last_applied_frame_serial ||
        staged->original_firmware_equivalence_proven ||
        staged->selected_neutral_produced || state->selected_neutral_produced)
        return HB_AWB_REBUILD_BAD_INPUT;
    if (state->candidate_count > UINT64_MAX-staged->caller_delta_candidates ||
        state->consumed_block_count > UINT64_MAX-staged->caller_delta_blocks ||
        state->consumed_sample_count > UINT64_MAX-staged->caller_delta_samples)
        return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_optimizer_caller_state temp=*state;
    temp.candidate_count+=staged->caller_delta_candidates;
    temp.consumed_block_count+=staged->caller_delta_blocks;
    temp.consumed_sample_count+=staged->caller_delta_samples;
    temp.last_applied_frame_serial=staged->frame_serial;
    temp.last_optimizer_status=staged->observed_optimizer_status;
    memcpy(temp.opaque_last_result, staged->opaque_result,sizeof(temp.opaque_last_result));
    *state=temp;
    return HB_AWB_REBUILD_OK;
}