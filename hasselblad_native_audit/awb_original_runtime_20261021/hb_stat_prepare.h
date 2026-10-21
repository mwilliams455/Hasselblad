/* SPDX-License-Identifier: MIT */
#ifndef HB_STAT_PREPARE_H
#define HB_STAT_PREPARE_H
#include <stdint.h>
#define HB_PREP_UNSUPPORTED UINT32_C(0xfffffffe)
/* Research ABI: caller owns correctly sized buffers and supplies initialized
 * tables. This is not a production raw-file decoder or a device calibration. */
uint32_t hb_e2_main_parse(unsigned char *ctx,unsigned char *e2,unsigned char *out,unsigned char *meta);
uint32_t hb_import_stats(unsigned char *ctx,const unsigned char *in,const unsigned char *meta);
void hb_stat_awb_info(unsigned char *ctx);
uint32_t hb_update_calib_gain(unsigned char *ctx);
uint32_t hb_stat_calib_proc(unsigned char *ctx);
void hb_stat_ae_info(unsigned char *ctx,const unsigned char *config);
#endif
