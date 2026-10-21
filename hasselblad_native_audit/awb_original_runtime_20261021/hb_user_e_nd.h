/* SPDX-License-Identifier: MIT */
#ifndef HB_USER_E_ND_H
#define HB_USER_E_ND_H
#include <stdint.h>
/* Initialized research ABI: context 920560, config 1502800 bytes.
 * Temperature tables: <=8 rows, each 52 bytes with 1..8 gain points.
 * Unit profiles: <=2, each with <=2 groups of <=8 points.
 * Unsupported shapes return HB_PREP_UNSUPPORTED before mutation.
 * Output uint32 pointers may alias each other, outside input storage. */
uint32_t hb_e_nd_temp_row_gain(const unsigned char *row,float amount,uint32_t *red,uint32_t *blue);
uint32_t hb_e_nd_temp_gain(const unsigned char *config,float amount,float temperature,uint32_t *red,uint32_t *blue);
/* Original request helper has no defined status contract. Zero here means
 * supported processing; rejected requests disable correction and retain
 * original partial writes. They do not abort the full user controller. */
uint32_t hb_user_e_nd_unit_request(unsigned char *ctx,const unsigned char *config);
/* Existing calibration imports followed by unit request, through the user
 * boundary before 0x4b162c; the remaining user controller is still external. */
uint32_t hb_user_prepare_calibration(unsigned char *ctx,const unsigned char *config);
#endif
