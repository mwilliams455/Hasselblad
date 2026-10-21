/* SPDX-License-Identifier: MIT */
#ifndef HB_DETECT_H
#define HB_DETECT_H
#include <stdint.h>
/* Pinned research ABI. Caller owns initialized context/config; no original
 * code or model tables are embedded. Unsupported shapes return before writes. */
uint32_t hb_detect_curve(const unsigned char *curve,float value,uint32_t *out);
uint32_t hb_detect_zone_count(const unsigned char *ctx,const unsigned char *cfg,
    unsigned category,unsigned primary_count,const unsigned char *primary,
    unsigned semantic_count,const unsigned char *semantic,uint32_t *out,uint32_t *weighted);
uint32_t hb_detect_outter(unsigned char *ctx,const unsigned char *cfg);
uint32_t hb_detect_process(unsigned char *ctx,const unsigned char *cfg);
#endif
