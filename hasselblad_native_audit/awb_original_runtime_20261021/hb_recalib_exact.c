/* SPDX-License-Identifier: MIT */
#include "hb_recalib_exact.h"
uint32_t hb_recalib_exact(uint32_t *a, uint32_t *b, uint32_t ca, uint32_t cb)
{
    if (ca == 0 || cb == 0) return 89;
    *a = (uint32_t)(*a << 12) / ca;
    *b = (uint32_t)(*b << 12) / cb;
    return 0;
}
