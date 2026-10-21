/* SPDX-License-Identifier: MIT */
#ifndef HB_ATMOSPHERE_H
#define HB_ATMOSPHERE_H
#include "hb_temperature.h"
#include <stdint.h>
/* Pinned-firmware research ABI, requiring validated bounded tables and nonempty
 * nested axes. An active empty basic table or selected empty E-ND value returns
 * HB_PREP_UNSUPPORTED: the original consumes unspecified stack outputs there. */
int32_t hb_atmosphere_interpolate_signed(int32_t x0,int32_t x1,int32_t y0,int32_t y1,float x);
uint32_t hb_atmosphere_ev_row(const unsigned char *row,uint32_t ct,int32_t tint,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_gains(const unsigned char *table,uint32_t ct,float ev,float tint,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_end_value(const unsigned char *row,uint32_t ct,float ev,float tint,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_end_gains(const unsigned char *table,uint32_t ct,float end,float ev,float tint,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_category_distance(const unsigned char *ctx,uint32_t slot,const unsigned char *row,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_category_ct(const unsigned char *ctx,uint32_t slot,const unsigned char *row,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_category_ev(const unsigned char *ctx,uint32_t slot,const unsigned char *row,uint32_t *r,uint32_t *b);
uint32_t hb_atmosphere_process(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model);
#endif
