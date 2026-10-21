/* SPDX-License-Identifier: MIT */
#ifndef HB_WHITE_LUT_H
#define HB_WHITE_LUT_H
#include <stdint.h>
/* Initialized-allocation research ABI. Context 920560, config 1502800 bytes.
 * Sparse points contain four uint32 fields: CT, R gain, B gain, distance.
 * Count <=15; for count >=2 CT must be within 2000..10000. Output is 81
 * four-word records, disjoint from points and context index scratch 0x308.
 * Decreasing CT indices return original status 33 with partial writes;
 * nonpositive extrapolated gains return 30 with partial writes.
 * Unsafe counts/CTs return HB_PREP_UNSUPPORTED before mutation. */
uint32_t hb_white_lut_expand(unsigned char *ctx,const unsigned char *points,
                             unsigned count,unsigned char *output);
/* Reconstruct active E-ND table selection/interpolation and baseline restore.
 * Selected sparse tables obey the expansion contract. Interpolated axes must
 * be finite and ordered; selected lower/upper tables have equal point counts,
 * matching the baseline count used by the downstream statistics search.
 * Original above-all-axes selection of the FIRST table is preserved.
 * No original callbacks, logging, initialization or phone calibration. */
uint32_t hb_white_lut_prepare(unsigned char *ctx,const unsigned char *config);
#endif
