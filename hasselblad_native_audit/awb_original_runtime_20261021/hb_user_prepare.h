/* SPDX-License-Identifier: MIT */
#ifndef HB_USER_PREPARE_H
#define HB_USER_PREPARE_H
#include <stdint.h>
/* Initialized-context research ABI: context 920560, config 1502800 bytes.
 * Two base calibration points, two E-ND groups with two points each,
 * one/two temperature rows of ten ratios, and <=15 manual LUT points.
 * Prefix owns user entry through the boundary before original 0x4b1624.
 * Shape guards return HB_PREP_UNSUPPORTED before prefix mutation; original
 * statuses 83/84 retain consumed requests and earlier successful writes.
 * Success means prefix complete, not full user processing or full AWB. */
uint32_t hb_user_calibration_gain(unsigned char *ctx,uint32_t ct,uint32_t *red,uint32_t *blue);
uint32_t hb_user_manual_lut_refresh(unsigned char *ctx,const unsigned char *config);
uint32_t hb_user_base_calibration(unsigned char *ctx,const unsigned char *config);
uint32_t hb_user_prepare_prefix(unsigned char *ctx,const unsigned char *config);
/* Original helper has no specified status; compare context only. */
void hb_user_mode_switch(unsigned char *ctx);
#endif
