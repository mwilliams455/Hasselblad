/* SPDX-License-Identifier: MIT */
#ifndef HB_USER_CONTROLS_H
#define HB_USER_CONTROLS_H
#include "hb_temperature.h"
/* Initialized research context/config and existing calibrated-temperature
 * model contract. Converter outputs are outside input storage; output aliases
 * are supported. No original function callbacks occur in owned code. */
uint32_t hb_user_ct_tint_to_gain(const unsigned char*,const unsigned char*,const hb_temperature_model*,uint32_t,float,uint32_t,uint32_t*,uint32_t*,uint32_t*);
uint32_t hb_user_result_manual(unsigned char*,const uint32_t[3],const uint32_t[3],uint32_t,float,uint32_t,uint8_t);
uint32_t hb_user_result_golden_snapshot(unsigned char*);
/* correction0=base,1=temperature,2=unit,3=golden. Zero divisor returns89
 * before writing gain records. */
uint32_t hb_user_result_recalibrate(unsigned char*,unsigned);
uint32_t hb_user_update_ct(unsigned char*,const unsigned char*,const hb_temperature_model*);
uint32_t hb_user_update_ct_tint(unsigned char*,const unsigned char*,const hb_temperature_model*);
uint32_t hb_user_update_gain(unsigned char*,const unsigned char*,const hb_temperature_model*);
/* Connects the already-owned mode helper, then CT, CT/tint and direct gain.
 * Each exact1 request is consumed before original validation errors. Shapes
 * outside the research contract return HB_PREP_UNSUPPORTED before that
 * handler's mutation, not before earlier handlers in the sequence. */
uint32_t hb_user_controls(unsigned char*,const unsigned char*,const hb_temperature_model*);
#endif
