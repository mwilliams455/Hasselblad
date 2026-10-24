#include "fixed_width62.h"
#include <limits.h>
#include <string.h>

uint16_t hb_low16_u64_62(uint64_t value) {
    return (uint16_t)value;
}
int16_t hb_low16_i64_62(int64_t value) {
    const uint16_t bits = (uint16_t)(uint64_t)value;
    int16_t result;
    memcpy(&result, &bits, sizeof result);
    return result;
}
int32_t hb_low32_i64_62(int64_t value) {
    const uint32_t bits = (uint32_t)(uint64_t)value;
    int32_t result;
    memcpy(&result, &bits, sizeof result);
    return result;
}
uint32_t hb_mul_low32_62(uint32_t a, uint32_t b) {
    return (uint32_t)((uint64_t)a * (uint64_t)b);
}
int32_t hb_add_low32_62(int32_t a, int32_t b) {
    return hb_low32_i64_62((int64_t)a + (int64_t)b);
}
int64_t hb_arm64_sdiv64_62(int64_t numerator, int64_t denominator) {
    /* Explicit AArch64 SDIV instruction behavior (not the C11 / operator's
     * undefined zero or INT64_MIN/-1 cases). Whether the real helper reaches
     * those inputs is a separate native observation.
     */
    if (!denominator) return 0;
    if (numerator == INT64_MIN && denominator == -1) return INT64_MIN;
    return numerator / denominator;
}
int32_t hb_arm64_sdiv32_62(int32_t numerator, int32_t denominator) {
    if (!denominator) return 0;
    if (numerator == INT32_MIN && denominator == -1) return INT32_MIN;
    return numerator / denominator;
}
int hb_gt_65534_62(uint64_t unsigned_value) {
    /* Predicate only. The native *branch action* remains undetermined. */
    return unsigned_value > UINT64_C(65534);
}
