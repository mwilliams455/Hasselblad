/* SPDX-License-Identifier: MIT */
#ifndef HB_SCENE_CONTROLLER_H
#define HB_SCENE_CONTROLLER_H
#include "hb_temperature.h"
#include <stdint.h>
/* Pinned-firmware research ABI: validated context/config and bounded tables.
 * Complete scene stage, not the surrounding AWB controller or REAWB chain. */
uint32_t hb_scene_interpolate(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x);
uint32_t hb_special_gate_curve(const unsigned char *ctx,int32_t camera_index,uint32_t slot,const unsigned char *row,uint32_t *out);
uint32_t hb_special_ct_curve(const unsigned char *ctx,int32_t camera_index,uint32_t slot,const unsigned char *row,uint32_t *out);
uint32_t hb_special_post_weight(unsigned char *ctx,const unsigned char *cfg,int32_t camera_index,uint32_t slot);
uint32_t hb_special_spectral_weight(unsigned char *ctx,const unsigned char *cfg,uint32_t slot);
uint32_t hb_scene_process(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model,int32_t camera_index);
#endif
