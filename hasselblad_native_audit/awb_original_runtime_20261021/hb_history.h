/* SPDX-License-Identifier: MIT */
#ifndef HB_HISTORY_H
#define HB_HISTORY_H
#include <stdint.h>
/* Research ABI for the pinned firmware and validated, bounded context/config
 * layouts. The signed geometry and wrapping arithmetic are intentional. */
int32_t hb_temperature_distance(const unsigned char *ctx,uint32_t ct,uint32_t r,uint32_t b);
uint32_t hb_zone_contains(const unsigned char *zone,uint32_t r,uint32_t b);
uint32_t hb_zone_edge(const unsigned char *zone,uint32_t r,uint32_t b,int32_t *out);
int32_t hb_zone_distance(const unsigned char *zone,uint32_t r,uint32_t b);
uint32_t hb_history_zone_count(const unsigned char *ctx,const unsigned char *cfg,uint32_t category,uint32_t sub,uint32_t n,const unsigned char *zones,uint32_t *out,uint32_t *weighted);
uint32_t hb_history_process(unsigned char *ctx,const unsigned char *cfg);
#endif
