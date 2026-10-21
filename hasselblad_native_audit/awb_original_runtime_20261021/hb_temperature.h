/* SPDX-License-Identifier: MIT */
#ifndef HB_TEMPERATURE_H
#define HB_TEMPERATURE_H
#include <stdint.h>
/* Private reference data is supplied by the caller, never compiled into code.
 * Research ABI: validated initialized context/config and 31 four-float rows.
 * No function pointer or original implementation is used by these routines. */
typedef struct { const float *isotemperature_31x4; } hb_temperature_model;
uint32_t hb_temperature_xy(const hb_temperature_model*,const float xy[2],float *ct,float *tint);
uint32_t hb_temperature_matrix_row(const unsigned char *row,float ct,float out[9]);
uint32_t hb_temperature_matrix(const unsigned char *cfg,int ae_enabled,float ae,float ct,float out[9]);
uint32_t hb_temperature_calibrated(const unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model*,uint32_t r,uint32_t g,uint32_t b,float *ct,float *tint);
uint32_t hb_temperature_compute(const unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model*,uint32_t mode,uint32_t r,uint32_t g,uint32_t b,float *ct,float *tint);
#endif
