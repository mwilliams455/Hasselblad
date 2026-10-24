#ifndef HB_INTERPOLATE_WIRING66_H
#define HB_INTERPOLATE_WIRING66_H
#include "schedule66.h"
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Experimental pixel-plane *ownership and call ordering*.
 * The callbacks below are seam points for the existing Stage61-63 independent
 * kernels. No demosaic equations, gradients or masks are invented here.
 */
typedef struct {
    HB66Domain domain;
    const uint16_t *raw;
    uint16_t *red,*green,*blue,*mask;
} HB66Planes;
typedef struct {
    void *user;
    /* Invoked in original prepass order. Does not receive source pixels. */
    int (*prepare)(void *user, HB66Event operation,int row);
    int (*estimate_green)(void *user,int x,int y,uint16_t *green,uint16_t *mask);
    int32_t (*estimate_opposite_colour)(void *user,int x,int y,int red_site,uint16_t mask);
    int (*compute_green_site_mask)(void *user,int x,int y,uint16_t *mask);
    int (*estimate_red_blue_green_site)(void *user,int x,int y,uint16_t mask,
                                        uint16_t *red,uint16_t *blue);
} HB66Callbacks;
typedef struct {
    HB66Counts events;
    uint64_t green_red_calls,green_blue_calls,opposite_colour_calls;
    uint64_t opposite_zero_fallbacks,green_site_mask_calls;
    uint64_t green_site_rb_calls,green_site_zero_fallbacks;
} HB66WiringCounts;
/* 0 succeeds; -1 invalid geometry/buffer/callback; -2 unsupported config;
 * -3 callback abort. Original RAW and all unmodified plane sites retained.
 * No allocation, no edge extension, no picture export/colour conversion.
 * Writable buffers (including mask) and RAW must be disjoint.
 * On callback error, writes already made are intentionally NOT rolled back.
 */
int hb_wire_interpolate66(const HB66Planes *planes, const HB66Callbacks *callbacks,
                          HB66WiringCounts *counts);
#ifdef __cplusplus
}
#endif
#endif
