/* SPDX-License-Identifier: MIT */
#ifndef HB_POST_RESULTS_H
#define HB_POST_RESULTS_H
#include "hb_temperature.h"
#include <stdint.h>
/* Pinned-firmware research ABI. These are post-processing building blocks,
 * not the complete scene_awb_post_proc controller. Context/config must be
 * initialized and tables bounded. Colour mode requires a nonempty ordered
 * axis and a mapped table index of 0 or 1; unsupported inputs are explicit.
 * Colour-mode count clamping intentionally mutates cfg, as in the original.
 * Normal blending requires input records disjoint from its output record. */
uint32_t hb_post_blend_normal(unsigned char *ctx,uint32_t wa,uint32_t wb,const unsigned char *a,const unsigned char *b);
uint32_t hb_post_golden_conversion(uint32_t r,uint32_t g,uint32_t b,uint32_t *out_r,uint32_t *out_g,uint32_t *out_b,uint32_t scale,uint32_t divisor);
uint32_t hb_post_result_ct(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model);
uint32_t hb_post_golden_snapshot(unsigned char *ctx);
uint32_t hb_post_end_temperature(unsigned char *ctx);
uint32_t hb_post_end_unit(unsigned char *ctx);
uint32_t hb_post_recalibrate(unsigned char *ctx);
uint32_t hb_post_normalize(unsigned char *ctx,const unsigned char *cfg);
uint32_t hb_post_color_mode(unsigned char *ctx,unsigned char *cfg);
/* Exact final helper sequence after result publication, with early exits. */
uint32_t hb_post_finalize(unsigned char *ctx,unsigned char *cfg,const hb_temperature_model *model);
/* Complete mode-2 branch only, including diagnostics and exit validation.
 * Other modes return HB_PREP_UNSUPPORTED before modifying ctx or cfg. */
uint32_t hb_post_mode2(unsigned char *ctx,unsigned char *cfg);
uint32_t hb_post_validate(unsigned char *ctx);
#endif
