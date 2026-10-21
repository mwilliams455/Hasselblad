/* SPDX-License-Identifier: MIT */
#ifndef HB_USER_MANUAL_H
#define HB_USER_MANUAL_H
#include "hb_temperature.h"
/* Initialized research context/config, distinct allocations. Golden tables:
 * 1..2 profiles, 1..8 amounts, 1..2 CT points. Unit: 1..2 rows, 1..8 points.
 * Temperature updates require 1..8 rows, 1..8 points (unlike empty lookup).
 * Unsupported shapes return HB_PREP_UNSUPPORTED before this call mutates state.
 * Getter outputs may alias each other, but must lie outside inputs. */
uint32_t hb_e_nd_golden_ct_gain(const unsigned char*,uint32_t,uint32_t*,uint32_t*);
uint32_t hb_e_nd_golden_amount_gain(const unsigned char*,uint32_t,float,uint32_t*,uint32_t*);
uint32_t hb_e_nd_update_temperature(unsigned char*,const unsigned char*);
uint32_t hb_e_nd_update_unit(unsigned char*);
uint32_t hb_e_nd_update_golden(unsigned char*,const unsigned char*);
/* Replaces manual-sample selection at 0x4b162c, before mode requests0x4b16a8.
 * <=64 selected indices and <=1024 statistics; existing temperature-model
 * contract applies. Earlier calibration imports must already be processed.
 * Conversion errors91/92 are intentionally ignored as in original user_proc:
 * outputs start at zero, then clamp to CT2000..10000/tint-99..99. */
uint32_t hb_user_manual_samples(unsigned char*,const unsigned char*,const hb_temperature_model*);
#endif
