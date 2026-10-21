/* SPDX-License-Identifier: MIT */
#ifndef HB_ROI_SYNC_H
#define HB_ROI_SYNC_H
#include <stdint.h>
typedef struct {
    char sensor_names[3][16]; /* IDs12,15,19 in this research ABI. */
    float templates[8][4]; /* Normalized left,top,right,bottom. */
    float fixed[8][4]; /* Low-mode left,top,width,height. */
    float fallback[8][4];
} hb_roi_sync_model;
/* Initialized context920560/config1502800 research ABI. Model data belongs
 * to the caller; no firmware tables or callbacks are embedded here.
 * Profile count<=6; all matrix-record/model names terminate within16bytes.
 * Unsupported shapes return HB_PREP_UNSUPPORTED before writes. Matrix
 * rejection returns UINT32_MAX and leaves context unchanged. Logging omitted. */
uint32_t hb_roi_sync_matrix(unsigned char*,const unsigned char*,const hb_roi_sync_model*);
uint32_t hb_roi_sync_calculate(unsigned char*,const unsigned char*,const hb_roi_sync_model*);
uint32_t hb_roi_sync_process(unsigned char*,const unsigned char*,const hb_roi_sync_model*);
#endif
