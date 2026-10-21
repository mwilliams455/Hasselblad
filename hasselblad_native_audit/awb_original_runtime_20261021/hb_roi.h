/* SPDX-License-Identifier: MIT */
#ifndef HB_ROI_H
#define HB_ROI_H
#include <stdint.h>
/* Initialized context920560/config1502800 research ABI. Six detector lists
 * are bounded to eight records each. Bounds are checked before mutation on
 * active, non-reset calls. Diagnostic logging is excluded. */
uint32_t hb_roi_reinitialize(unsigned char*);
uint32_t hb_roi_process(unsigned char*,const unsigned char*);
#endif
