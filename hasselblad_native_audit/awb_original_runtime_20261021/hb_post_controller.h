/* SPDX-License-Identifier: MIT */
#ifndef HB_POST_CONTROLLER_H
#define HB_POST_CONTROLLER_H
#include "hb_post_results.h"
/* Pinned-firmware research ABI. Initialized context, bounded ordered tables,
 * and the caller's private temperature model are required. REAWB is read only.
 * Unsupported optional inputs return HB_PREP_UNSUPPORTED, never fabricated
 * success. This stage does not implement the surrounding AWB or HNCS renderer. */
uint32_t hb_post_inverse(const unsigned char*,const unsigned char*,const hb_temperature_model*,uint32_t,float,uint32_t,uint32_t out[3]);
uint32_t hb_post_category(unsigned char*,const unsigned char*);
uint32_t hb_post_gate(const unsigned char*,unsigned,const unsigned char*,uint32_t*);
uint32_t hb_post_merge_row(const unsigned char*,const unsigned char*,uint32_t*,uint32_t*);
uint32_t hb_post_iso_row(const unsigned char*,uint32_t,uint32_t,int32_t,uint32_t*,uint32_t*);
uint32_t hb_post_smooth(unsigned char*,uint32_t,uint32_t,const unsigned char*,unsigned char*,uint32_t);
uint32_t hb_post_publish(unsigned char*,const unsigned char*,const unsigned char*);
uint32_t hb_post_sensor_tint(const unsigned char*,int32_t,uint16_t*,int16_t*);
uint32_t hb_post_sensor_transform(unsigned char*,const unsigned char*,uint32_t,uint32_t,int32_t);
uint32_t hb_post_sync_zones(const unsigned char*,const unsigned char*,uint32_t[8],unsigned char[8],float[8],const uint32_t[8],const uint32_t[8]);
uint32_t hb_post_sync_shift(const unsigned char*,const unsigned char*,uint32_t[3],uint32_t,uint32_t,const uint32_t[8],const uint32_t[8],const uint32_t[3]);
uint32_t hb_post_sync(unsigned char*,const unsigned char*,const hb_temperature_model*);
uint32_t hb_post_process(unsigned char*,unsigned char*,const hb_temperature_model*,const unsigned char*);
#endif
