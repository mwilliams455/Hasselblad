/* SPDX-License-Identifier: MIT
 * Exact byte comparison for TWO snapshots from the SAME initialized execution.
 * This does not infer whether any particular capture/source was authentic.
 * Pointer-bearing state from different processes is NOT interchangeable.
 */
#ifndef HB_AWB_STATE_DIFF_H
#define HB_AWB_STATE_DIFF_H
#include <stddef.h>
#include <stdint.h>
#include "hb_awb_stages.h"

typedef struct hb_awb_diff_summary {
    uint64_t context_differences;
    uint64_t reawb_differences;
    uint32_t context_first_mismatch;
    uint32_t reawb_first_mismatch;
    int32_t original_return_status;
    int32_t owned_return_status;
    uint8_t all_bytes_and_status_equal;
    uint8_t original_reference_proven; /* ALWAYS 0; provenance is external. */
} hb_awb_diff_summary;

int hb_awb_compare_state_snapshots(const uint8_t *original_context,
        size_t original_context_bytes,
        const uint8_t *owned_context, size_t owned_context_bytes,
        const uint8_t *original_reawb, size_t original_reawb_bytes,
        const uint8_t *owned_reawb, size_t owned_reawb_bytes,
        int32_t original_status, int32_t owned_status,
        hb_awb_diff_summary *out);
#endif