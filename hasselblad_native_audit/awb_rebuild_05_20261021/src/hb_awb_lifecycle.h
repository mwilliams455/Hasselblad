/* SPDX-License-Identifier: MIT
 * Bounded AWB result lifecycle derived from RECORDED final-copy/outer-controller
 * branch rules. Does not compute vendor AWB estimates or sensor-neutral values.
 */
#ifndef HB_AWB_LIFECYCLE_H
#define HB_AWB_LIFECYCLE_H
#include <stdint.h>
#include <stddef.h>
#include "hb_awb_stages.h"

#define HB_AWB_LIFECYCLE_REVISION 1u

typedef struct hb_awb_lifecycle_journal {
    uint32_t revision;
    uint64_t last_frame_serial;
    uint64_t processed_frames;
    uint64_t live_publications;
    uint64_t confirmed_restorations;
    uint64_t reference_overrides;
    uint64_t outer_returns_success;
    uint64_t inner_returns_error;
    /* No original optimizer or E2 proof exists; NEVER a freshness claim. */
    uint8_t original_scene_estimate_verified;
} hb_awb_lifecycle_journal;

typedef struct hb_awb_lifecycle_result {
    uint64_t frame_serial;
    int inner_status;
    int outer_status;
    enum hb_awb_result_origin result_origin;
    uint8_t result_restored_or_overridden;
    uint8_t outer_success;
    uint8_t fresh_vendor_estimate_proven; /* ALWAYS zero in this checkpoint */
    uint8_t passive_reawb_preserved;
} hb_awb_lifecycle_result;

/* This host contract models only the already-reconstructed final-copy boundary.
 * It must be called with a 920560-byte prepared synthetic/known context and a
 * 1000-byte REAWB handle. No vendor calling convention is assumed.
 * No mutation of any input/output/journal on input or sequence error.
 * On success context and journal update, REAWB handle is never touched.
 * The output origin comes from the verified historical branch criteria, NOT
 * from original ARM64 execution in the current session.
 */
int hb_awb_lifecycle_advance(hb_awb_lifecycle_journal *journal,
                             uint64_t frame_serial,
                             uint8_t *context, size_t context_bytes,
                             const uint8_t *reawb_handle, size_t reawb_bytes,
                             int inner_status, int final_copy_status,
                             hb_awb_lifecycle_result *result);
#endif