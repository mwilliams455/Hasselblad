/* SPDX-License-Identifier: MIT */
#include "hb_awb_lifecycle.h"
#include <limits.h>

int hb_awb_lifecycle_advance(hb_awb_lifecycle_journal *journal,
                             uint64_t frame_serial,
                             uint8_t *context, size_t context_bytes,
                             const uint8_t *reawb_handle, size_t reawb_bytes,
                             int inner_status, int final_copy_status,
                             hb_awb_lifecycle_result *result) {
    if (!journal || !context || !reawb_handle || !result ||
        journal->revision != HB_AWB_LIFECYCLE_REVISION ||
        context_bytes != HB_AWB_CONTEXT_BYTES || reawb_bytes != HB_AWB_REAWB_BYTES ||
        !frame_serial || frame_serial <= journal->last_frame_serial ||
        journal->original_scene_estimate_verified ||
        journal->processed_frames == UINT64_MAX ||
        journal->live_publications == UINT64_MAX ||
        journal->confirmed_restorations == UINT64_MAX ||
        journal->reference_overrides == UINT64_MAX ||
        journal->outer_returns_success == UINT64_MAX ||
        journal->inner_returns_error == UINT64_MAX) {
        return HB_AWB_REBUILD_BAD_INPUT;
    }
    /* Perform the bounded original-final-copy rules. All guards above complete
     * before the first write. No speculative original optimizer state touched. */
    hb_awb_completion completion={0};
    const int rc=hb_awb_outer_complete_bounded(context,context_bytes,
                                                inner_status,final_copy_status,
                                                &completion);
    if (rc != HB_AWB_REBUILD_OK) return rc;
    hb_awb_lifecycle_journal next=*journal;
    next.last_frame_serial=frame_serial;
    ++next.processed_frames;
    if (inner_status!=0) ++next.inner_returns_error;
    if (completion.outer_status==0) ++next.outer_returns_success;
    switch(completion.origin) {
        case HB_AWB_ORIGIN_LIVE_PUBLISHED: ++next.live_publications; break;
        case HB_AWB_ORIGIN_RESTORED_CONFIRMED: ++next.confirmed_restorations; break;
        case HB_AWB_ORIGIN_REFERENCE_OVERRIDE: ++next.reference_overrides; break;
        default: return HB_AWB_REBUILD_UNSUPPORTED; /* Cannot arise with bounded completion */
    }
    hb_awb_lifecycle_result output={0};
    output.frame_serial=frame_serial;
    output.inner_status=inner_status;
    output.outer_status=completion.outer_status;
    output.result_origin=completion.origin;
    output.result_restored_or_overridden=(uint8_t)(completion.origin!=HB_AWB_ORIGIN_LIVE_PUBLISHED);
    output.outer_success=(uint8_t)(completion.outer_status==0);
    output.fresh_vendor_estimate_proven=0;
    output.passive_reawb_preserved=1;
    *journal=next;
    *result=output;
    return HB_AWB_REBUILD_OK;
}