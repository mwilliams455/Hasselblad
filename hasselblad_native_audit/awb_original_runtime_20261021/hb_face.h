/* SPDX-License-Identifier: MIT */
#ifndef HB_FACE_H
#define HB_FACE_H
#include <stdint.h>
/* Pinned research ABI. Tables belong to the caller; no calibration/model data
 * is embedded. Unsupported shapes are rejected before context writes. */
uint32_t hb_face_process(unsigned char *ctx,const unsigned char *cfg);
uint32_t hb_face_brightness(const unsigned char *row,float ev,uint32_t brightness);
void hb_face_smooth(unsigned char *ctx,const unsigned char *cfg);
#endif
