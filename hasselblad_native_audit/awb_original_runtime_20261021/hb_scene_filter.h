/* SPDX-License-Identifier: MIT */
#ifndef HB_SCENE_FILTER_H
#define HB_SCENE_FILTER_H
#include <stdint.h>
/* Pinned-firmware research ABI: context is initialized, count <=4096,
 * scene/slot offsets are validated, and each record's CT table index <=80. */
uint32_t hb_scene_filter(unsigned char *ctx,uint32_t scene,uint32_t slot,uint32_t factor);
#endif
