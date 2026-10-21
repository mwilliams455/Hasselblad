/* SPDX-License-Identifier: MIT */
#ifndef HB_SCENE_OPTIMIZER_H
#define HB_SCENE_OPTIMIZER_H
#include <stdint.h>
/* Research ABI for the pinned firmware. Caller supplies initialized context,
 * validated slot/count and 508-byte-per-scene parameter records. No phone
 * calibration or statistics preparation is performed here. */
uint32_t hb_scene_temperature(const unsigned char *ctx, uint32_t r, uint32_t b);
uint32_t hb_scene_optimizer(unsigned char *ctx, uint32_t slot, uint32_t count,
                            const unsigned char *parameters);
#endif
