/* SPDX-License-Identifier: MIT */
#ifndef HB_RESEARCH_CCM_PREPARE_H
#define HB_RESEARCH_CCM_PREPARE_H
#include <stddef.h>
#include <stdint.h>

enum {
    HB_CCM_SOURCE_VALUES = 768,
    HB_CCM_PREPARED_VALUES = 96,
    HB_CCM_OK = 0,
    HB_CCM_INVALID_ARGUMENT = 1,
    HB_CCM_SOURCE_OUT_OF_RANGE = 2
};

/* Research coefficient preparation, not a pixel colour transform.
 * source: eight 96-value profiles, CCT varies fastest, two secondary banks.
 * CCT knots: 2400, 3050, 5550, 9100 K; out-of-axis inputs are clamped.
 * secondary_weight_q8: already calculated bank weight, inclusive 0..256.
 * Supported coefficients are signed 16-bit values stored in int32_t slots.
 * Caller owns all buffers. Exact lengths are required; source/output may alias.
 * Any error leaves output untouched. Status values belong to this adapter.
 */
int hb_ccm_prepare(const int32_t *source, size_t source_count,
                   int32_t cct, int32_t secondary_weight_q8,
                   int32_t *output, size_t output_count);
#endif
