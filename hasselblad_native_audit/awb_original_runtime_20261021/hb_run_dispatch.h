/* SPDX-License-Identifier: MIT */
#ifndef HB_RUN_DISPATCH_H
#define HB_RUN_DISPATCH_H
#include <stdint.h>
enum hb_dispatch_action { HB_DISPATCH_RETURN, HB_DISPATCH_AUTO_REFRESH,
    HB_DISPATCH_AUTO_REUSE, HB_DISPATCH_MANUAL, HB_DISPATCH_CUSTOM,
    HB_DISPATCH_COMPLETE_ERROR };
typedef struct{enum hb_dispatch_action action;uint32_t status;} hb_dispatch_result;
/* After successful owned user processing, replaces outer0x471e78 through
 * automatic refresh/reuse selection and refresh scratch clearing. Mode2 and
 * custom mode bodies remain external. Full controller completion also remains
 * the caller's responsibility. No original calls occur here.
 * Return0 means supported dispatch, not full AWB completion. The original
 * stage status is in out->status. Statistics guards return HB_PREP_UNSUPPORTED
 * after setting the busy marker, preserving the original stage ordering. */
uint32_t hb_run_dispatch(unsigned char*,const unsigned char*,const unsigned char*,hb_dispatch_result*);
#endif
