#include "fixed_width62.h"
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>

int main(void) {
    assert(hb_low16_u64_62(UINT64_C(0x10005)) == 5);
    assert(hb_low16_i64_62(-1) == -1);
    assert(hb_low16_i64_62(INT64_C(65535)) == -1);
    assert(hb_low16_i64_62(INT64_C(32768)) == INT16_MIN);
    assert(hb_low32_i64_62(INT64_C(0x80000000)) == INT32_MIN);
    assert(hb_low32_i64_62(-1) == -1);
    assert(hb_mul_low32_62(UINT32_MAX, UINT32_MAX) == 1);
    assert(hb_mul_low32_62(UINT32_C(65536), UINT32_C(65536)) == 0);
    assert(hb_add_low32_62(INT32_MAX, 1) == INT32_MIN);
    assert(hb_add_low32_62(INT32_MIN, -1) == INT32_MAX);
    assert(hb_arm64_sdiv64_62(7, 3) == 2);
    assert(hb_arm64_sdiv64_62(-7, 3) == -2);
    assert(hb_arm64_sdiv64_62(-7, -3) == 2);
    assert(hb_arm64_sdiv64_62(777, 0) == 0);
    assert(hb_arm64_sdiv64_62(INT64_MIN, -1) == INT64_MIN);
    assert(hb_arm64_sdiv32_62(7, -3) == -2);
    assert(hb_arm64_sdiv32_62(7, 0) == 0);
    assert(hb_arm64_sdiv32_62(INT32_MIN, -1) == INT32_MIN);
    assert(hb_gt_65534_62(UINT64_C(65534)) == 0);
    assert(hb_gt_65534_62(UINT64_C(65535)) == 1);
    assert(hb_gt_65534_62(UINT64_MAX) == 1);
    puts("STAGE62_FIXED_WIDTH_C11_SELF_TEST_PASS");
    return 0;
}
