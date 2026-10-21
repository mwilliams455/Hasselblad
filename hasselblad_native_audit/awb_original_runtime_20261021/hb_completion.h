/* SPDX-License-Identifier: MIT */
#ifndef HB_COMPLETION_H
#define HB_COMPLETION_H
#include <stdint.h>
/* Research ABI: initialized 920560-byte context and 1000-byte REAWB handle.
 * No original callbacks. Active REAWB / linked storage are not implemented. */
enum hb_result_copy { HB_CONFIRM_LIVE, HB_RESTORE_CONFIRMED,
                      HB_REFERENCE_TO_LIVE, HB_REFERENCE_TO_CONFIRMED };
enum hb_completion_origin { HB_LIVE_PUBLISHED, HB_CONFIRMED_RESTORED,
                            HB_REFERENCE_PUBLISHED };
typedef struct {
    uint32_t preceding_status;
    enum hb_completion_origin origin;
    unsigned reference_consumed;
} hb_completion_record;
uint32_t hb_result_copy(unsigned char *ctx,enum hb_result_copy direction);
/* The original copy helpers return zero on initialized contexts, replacing the
 * preceding status. A zero return does not establish a fresh estimate. */
uint32_t hb_outer_complete(unsigned char *ctx,uint32_t preceding_status,
                           hb_completion_record *record);
uint32_t hb_shading_temperature(unsigned char *ctx);
/* Supports disabled processing, nonzero modes, and mode zero with run != 1.
 * save == 1 is supported only when its packed confidence is <= 122: above
 * that threshold linked storage is required, even if processing is disabled.
 * Unsupported paths leave both buffers unchanged. */
uint32_t hb_reawb_passive(unsigned char *ctx,unsigned char *state);
#endif
