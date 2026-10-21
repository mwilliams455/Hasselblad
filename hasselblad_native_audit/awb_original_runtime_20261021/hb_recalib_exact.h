/* SPDX-License-Identifier: MIT */
#ifndef HB_RECALIB_EXACT_H
#define HB_RECALIB_EXACT_H
#include <stdint.h>
/* Research comparator: exact unsigned wrap and sequential pointer writes.
 * This is not the guarded camera-facing adapter. Nonzero divisors require
 * valid writable gain pointers. Aliasing is permitted, matching the original.
 */
uint32_t hb_recalib_exact(uint32_t *a, uint32_t *b, uint32_t ca, uint32_t cb);
#endif
