/* SPDX-License-Identifier: MIT
 * Portable reconstruction of the bounded coefficient-preparation behaviour
 * checked against original mm_get_coeff and mm_mx_lerp_gap. No vendor assets.
 */
#include "ccm_prepare.h"
#include <string.h>

static int32_t lerp_q8_floor(int32_t a, int32_t b, int32_t weight) {
    int64_t product = ((int64_t)b - a) * weight;
    /* Explicit floor avoids implementation-defined signed right shifts. */
    int64_t quotient = product >= 0 ? product / 256 : -((-product + 255) / 256);
    return (int32_t)((int64_t)a + quotient);
}

int hb_ccm_prepare(const int32_t *source, size_t source_count,
                   int32_t cct, int32_t secondary_weight_q8,
                   int32_t *output, size_t output_count) {
    static const int32_t axis[4] = {2400, 3050, 5550, 9100};
    if (!source || !output || source_count != HB_CCM_SOURCE_VALUES ||
        output_count != HB_CCM_PREPARED_VALUES ||
        secondary_weight_q8 < 0 || secondary_weight_q8 > 256)
        return HB_CCM_INVALID_ARGUMENT;
    for (size_t i = 0; i < source_count; ++i)
        if (source[i] < -32768 || source[i] > 32767)
            return HB_CCM_SOURCE_OUT_OF_RANGE;

    size_t index = 0;
    int32_t fraction = 0;
    if (cct >= axis[3]) {
        index = 2;
        fraction = 256;
    } else if (cct >= axis[0]) {
        while (cct >= axis[index + 1]) ++index;
        fraction = (cct - axis[index]) * 256 / (axis[index + 1] - axis[index]);
    }
    int32_t prepared[HB_CCM_PREPARED_VALUES];
    for (size_t k = 0; k < HB_CCM_PREPARED_VALUES; ++k) {
        size_t a = index * HB_CCM_PREPARED_VALUES + k;
        int32_t low = lerp_q8_floor(source[a], source[a + 96], fraction);
        int32_t high = lerp_q8_floor(source[a + 384], source[a + 480], fraction);
        prepared[k] = lerp_q8_floor(low, high, secondary_weight_q8);
    }
    memcpy(output, prepared, sizeof(prepared));
    return HB_CCM_OK;
}
