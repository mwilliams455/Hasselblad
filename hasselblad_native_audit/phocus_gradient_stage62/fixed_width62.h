#ifndef HB_FIXED_WIDTH62_H
#define HB_FIXED_WIDTH62_H
#include <stdint.h>
/* Standalone fixed-width arithmetic for investigating ARM64 helper code.
 * These are arithmetic primitives, NOT reconstructed vendor interpolation.
 * No claim is made that any given native branch uses these operations.
 */
uint16_t hb_low16_u64_62(uint64_t value);
int16_t hb_low16_i64_62(int64_t value);
int32_t hb_low32_i64_62(int64_t value);
uint32_t hb_mul_low32_62(uint32_t a, uint32_t b);
int32_t hb_add_low32_62(int32_t a, int32_t b);
int64_t hb_arm64_sdiv64_62(int64_t numerator, int64_t denominator);
int32_t hb_arm64_sdiv32_62(int32_t numerator, int32_t denominator);
int hb_gt_65534_62(uint64_t unsigned_value);
#endif
