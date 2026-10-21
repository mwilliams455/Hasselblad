/* SPDX-License-Identifier: MIT */
#ifndef HB_RUN_ENTRY_H
#define HB_RUN_ENTRY_H
#include <stdint.h>
enum hb_run_action { HB_RUN_RETURN, HB_RUN_PREPARE };
enum hb_run_reason { HB_RUN_UNINITIALIZED, HB_RUN_BUSY, HB_RUN_FIXED_RESULT,
                     HB_RUN_CADENCE_SKIP, HB_RUN_RATE_SKIP, HB_RUN_READY };
typedef struct {
    enum hb_run_action action;
    enum hb_run_reason reason;
    uint32_t status; /* Original final status only when action==HB_RUN_RETURN. */
} hb_run_entry_result;
/* Initialized-allocation research ABI: context 920560, config 1502800 bytes.
 * Implements entry through the boundary before E-ND white-LUT preparation.
 * HB_RUN_PREPARE means caller must continue; it is not full AWB success.
 * No callbacks or firmware calls. Null arguments return HB_PREP_UNSUPPORTED. */
uint32_t hb_run_entry(unsigned char *ctx,const unsigned char *config,
                      hb_run_entry_result *out);
#endif
