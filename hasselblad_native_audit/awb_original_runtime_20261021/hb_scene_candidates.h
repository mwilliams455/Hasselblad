/* SPDX-License-Identifier: MIT */
#ifndef HB_SCENE_CANDIDATES_H
#define HB_SCENE_CANDIDATES_H
#include <stdint.h>
#include "hb_temperature.h"
/* Research ABI for the pinned firmware. Validated context/table storage is
 * required. Tables are supplied externally, never embedded in this source.
 * Temperature modes 1/2 require the explicit external model where used;
 * active special scene slots 2/3 are unsupported;
 * this API is not a production input-validation or full-AWB boundary. */
uint32_t hb_interp_opt(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x);
uint32_t hb_candidate_curve(const unsigned char *p,uint32_t ct,uint32_t value,uint32_t *out,int tint);
uint32_t hb_candidate_weight(unsigned char *ctx,const unsigned char *cfg,const unsigned char *p,uint32_t scene,uint32_t slot);
uint32_t hb_candidate_temperature(const unsigned char *ctx,uint32_t mode,uint32_t r,uint32_t g,uint32_t b,float *ct,float *tint);
uint32_t hb_candidate_accumulate(unsigned char *ctx,const unsigned char *p,const unsigned char *curves,uint32_t scene,uint32_t slot,uint32_t mode,uint32_t fraction);
uint32_t hb_candidate_accumulate_with_model(unsigned char *ctx,const unsigned char *cfg,const unsigned char *p,const unsigned char *curves,uint32_t scene,uint32_t slot,uint32_t mode,uint32_t fraction,const hb_temperature_model *model);
uint32_t hb_scene_spec_weight(unsigned char *ctx,const unsigned char *cfg,uint32_t slot);
uint32_t hb_spectral_distribution(const unsigned char *p,unsigned char *out);
uint32_t hb_spectral_ratio(const unsigned char *p,uint32_t ratio,unsigned char *out);
uint32_t hb_normal_scene(unsigned char *ctx,const unsigned char *cfg);
uint32_t hb_normal_scene_with_model(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model);
#endif
