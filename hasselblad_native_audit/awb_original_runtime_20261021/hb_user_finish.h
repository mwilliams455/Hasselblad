/* SPDX-License-Identifier: MIT */
#ifndef HB_USER_FINISH_H
#define HB_USER_FINISH_H
#include "hb_temperature.h"
/* Record needs 28 readable bytes. Status246 means six nonzero gain words;
 * status247 means at least one zero. No other numerical bounds are imposed. */
uint32_t hb_user_gain_record_valid(const unsigned char*);
/* Final user requests from0x4b16d4: two toggles, fixed result, persistent
 * toggle sync and bounded override. Initialized920560-byte research context.
 * An accepted fixed result needs <=2 base calibration points; unsupported
 * shape returns HB_PREP_UNSUPPORTED before any tail mutation. Invalid fixed
 * requests do not need the calibration table. Native validation rejection
 * consumes requests and clears validity flags, returning0. */
uint32_t hb_user_finish(unsigned char*);
/* Complete numerical user stage. Uses the existing bounded contracts for
 * calibration imports, manual selection and CT/tint/gain handlers. Stops on
 * first error, preserving earlier writes. No original firmware callbacks.
 * Diagnostic logging is outside this reconstruction. */
uint32_t hb_user_process(unsigned char*,const unsigned char*,const hb_temperature_model*);
#endif
