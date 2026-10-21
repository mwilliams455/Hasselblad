/* SPDX-License-Identifier: MIT
 * Partial, source-documented reconstruction. See README before reusing.
 */
#include "hb_awb_stages.h"
#include <string.h>

static uint32_t le32(const uint8_t *data) {
    return (uint32_t)data[0] | ((uint32_t)data[1]<<8) |
        ((uint32_t)data[2]<<16) | ((uint32_t)data[3]<<24);
}
static void write_le32(uint8_t *data, uint32_t value) {
    for (int i=0; i<4; ++i) data[i]=(uint8_t)(value >> (8*i));
}

int hb_awb_outer_complete_bounded(uint8_t *context, size_t context_bytes,
                                  int preceding_status, int final_copy_status,
                                  hb_awb_completion *out) {
    if (!context || context_bytes < HB_AWB_CONTEXT_BYTES || !out) return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_completion record = {0};
    record.preceding_status = preceding_status;
    record.final_copy_status = final_copy_status;
    /* The recorded original controller clears all four bytes at 0x174. */
    memset(context + HB_AWB_CLEAR_OFFSET, 0, 4);
    if (context[HB_AWB_REFERENCE_REQUEST_OFFSET] == 1u) {
        /* Exact request byte 1: reference replaces live + confirmed pairs. */
        for (size_t n = 0; n < HB_AWB_RESULT_BYTES; ++n) {
            const uint8_t value = context[HB_AWB_REFERENCE_RESULT_OFFSET+n];
            context[HB_AWB_LIVE_A_OFFSET+n] = value;
            context[HB_AWB_LIVE_B_OFFSET+n] = value;
            context[HB_AWB_CONFIRMED_A_OFFSET+n] = value;
            context[HB_AWB_CONFIRMED_B_OFFSET+n] = value;
        }
        context[HB_AWB_REFERENCE_REQUEST_OFFSET] = 0;
        record.reference_request_consumed = 1;
        record.origin = HB_AWB_ORIGIN_REFERENCE_OVERRIDE;
    } else if (preceding_status != 0) {
        memmove(context + HB_AWB_LIVE_A_OFFSET,
                context + HB_AWB_CONFIRMED_A_OFFSET, HB_AWB_RESULT_BYTES);
        memmove(context + HB_AWB_LIVE_B_OFFSET,
                context + HB_AWB_CONFIRMED_B_OFFSET, HB_AWB_RESULT_BYTES);
        record.origin = HB_AWB_ORIGIN_RESTORED_CONFIRMED;
    } else {
        memmove(context + HB_AWB_CONFIRMED_A_OFFSET,
                context + HB_AWB_LIVE_A_OFFSET, HB_AWB_RESULT_BYTES);
        memmove(context + HB_AWB_CONFIRMED_B_OFFSET,
                context + HB_AWB_LIVE_B_OFFSET, HB_AWB_RESULT_BYTES);
        record.origin = HB_AWB_ORIGIN_LIVE_PUBLISHED;
    }
    /* Original *later* helper status overwrote an earlier status in the recorded
     * path; the source-level helper call/return is not available. */
    record.outer_status = final_copy_status;
    record.fresh_estimate_proven = 0;
    *out = record;
    return HB_AWB_REBUILD_OK;
}

int hb_awb_select_supported_scene(const hb_awb_scene_entry *in) {
    if (!in) return HB_AWB_SCENE_BAD_INPUT;
    if (in->ordinary_illumination != 0) return HB_AWB_SCENE_UNSUPPORTED;
    if (in->eligible_scene_mask == 0) return HB_AWB_SCENE_NO_ELIGIBLE;
    if (in->ordinary_illumination == 0 && in->eligible_scene_mask == (1u << 3))
        return HB_AWB_SCENE_SUPPORTED_SELECTED;
    return HB_AWB_SCENE_UNSUPPORTED;
}

int hb_awb_recover_no_eligible(uint8_t *context, size_t bytes,
                               const hb_awb_scene_entry *entry,
                               hb_awb_completion *out) {
    if (!context || bytes < HB_AWB_CONTEXT_BYTES || !entry || !out) return HB_AWB_REBUILD_BAD_INPUT;
    if (hb_awb_select_supported_scene(entry) != HB_AWB_SCENE_NO_ELIGIBLE)
        return HB_AWB_REBUILD_UNSUPPORTED;
    return hb_awb_outer_complete_bounded(context, bytes, 40, 0, out);
}

int hb_awb_shading_select_bounded(uint8_t *context, size_t bytes,
                                  const hb_awb_shading_choice *choice,
                                  hb_awb_shading_result *out) {
    if (!context || bytes < HB_AWB_CONTEXT_BYTES || !choice || !out) return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_shading_result result = {0};
    if (choice->validity != 1) { *out=result; return HB_AWB_REBUILD_OK; }
    unsigned selected=0;
    for (unsigned i=1; i<7; ++i)
        if (choice->label_ratio[i] >= choice->label_ratio[selected]) selected=i;
    const uint8_t label = choice->vendor_label_id[selected];
    /* Conditions are historical findings, not guessed ratio offsets. */
    uint32_t primary_label = le32(context+HB_AWB_SHADING_PRIMARY_LABEL_OFFSET);
    uint32_t count = le32(context+HB_AWB_SHADING_PRIMARY_COUNT_OFFSET);
    const int use_reference = label==1u || label==4u || (primary_label==3 && count>=60);
    const uint32_t ct=le32(context+(use_reference ? HB_AWB_SHADING_REFERENCE_CT_OFFSET : HB_AWB_SHADING_NORMAL_CT_OFFSET));
    write_le32(context+HB_AWB_SHADING_OUTPUT_CT_OFFSET,ct);
    result.selected_label_id=label;
    result.selected_index=(uint8_t)selected;
    result.selected_ratio=choice->label_ratio[selected];
    result.chosen_ct=ct;
    result.from_reference_ct=(uint8_t)use_reference;
    result.published=1;
    *out=result;
    return HB_AWB_REBUILD_OK;
}

int hb_awb_publication_gates(uint8_t validity, const uint8_t *candidate,
                             uint8_t *published, uint8_t *history,
                             size_t bytes, hb_awb_publication_flags *out) {
    if (!candidate || !published || !history || !out || !bytes)
        return HB_AWB_REBUILD_BAD_INPUT;
    /* This lightweight contract does not support partially overlapping buffers.
     * Exact aliases are safe and used by a few callers. Caller must enforce
     * provenance of genuinely distinct source/destination regions. */
    *out = (hb_awb_publication_flags){0};
    if (validity != 0) {
        memmove(published, candidate, bytes);
        out->candidate_published = 1;
        if (validity == 1) {
            memmove(history, candidate, bytes);
            out->history_copied = 1;
        }
    }
    return HB_AWB_REBUILD_OK;
}

int hb_awb_prune_small_components(const uint8_t *weighted_mask,
                                  uint8_t *filtered_mask,
                                  enum hb_awb_connectivity neighbors,
                                  hb_awb_component_stats *stats) {
    if (!weighted_mask || !filtered_mask || !stats ||
        (neighbors != HB_AWB_NEIGHBORS_FOUR && neighbors != HB_AWB_NEIGHBORS_EIGHT))
        return HB_AWB_REBUILD_BAD_INPUT;
    /* Separate visited/output allows input==output. Queue capacity exactly 1024. */
    uint8_t active[HB_AWB_FRAME_BLOCKS];
    uint8_t visited[HB_AWB_FRAME_BLOCKS] = {0};
    unsigned queue[HB_AWB_FRAME_BLOCKS];
    for (unsigned i=0; i<HB_AWB_FRAME_BLOCKS; ++i) active[i] = weighted_mask[i] != 0;
    memset(filtered_mask, 0, HB_AWB_FRAME_BLOCKS);
    hb_awb_component_stats tally={0};
    for (unsigned first=0; first<HB_AWB_FRAME_BLOCKS; ++first) {
        if (!active[first] || visited[first]) continue;
        unsigned begin=0, end=0;
        visited[first]=1;
        queue[end++]=first;
        while (begin<end) {
            unsigned k=queue[begin++];
            int x=(int)(k%HB_AWB_FRAME_BLOCKS_X);
            int y=(int)(k/HB_AWB_FRAME_BLOCKS_X);
            for (int dy=-1;dy<=1;++dy) {
                for (int dx=-1;dx<=1;++dx) {
                    if ((!dx && !dy) || (neighbors==HB_AWB_NEIGHBORS_FOUR && dx && dy)) continue;
                    int nx=x+dx, ny=y+dy;
                    if (nx<0||ny<0||nx>=32||ny>=32) continue;
                    unsigned n=(unsigned)(ny*32+nx);
                    if (active[n] && !visited[n]) { visited[n]=1; queue[end++]=n; }
                }
            }
        }
        /* Recorded condition is <=3, not <3; topology is a caller parameter. */
        if (end<=3) { ++tally.groups_removed; tally.blocks_removed+=(uint16_t)end; }
        else {
            ++tally.groups_kept;
            tally.blocks_kept+=(uint16_t)end;
            for (unsigned k=0;k<end;++k) filtered_mask[queue[k]]=1;
        }
    }
    *stats=tally;
    return HB_AWB_REBUILD_OK;
}

uint32_t hb_awb_clamp_ct(uint32_t kelvin) {
    if (kelvin < 2000u) return 2000u;
    if (kelvin > 10000u) return 10000u;
    return kelvin;
}