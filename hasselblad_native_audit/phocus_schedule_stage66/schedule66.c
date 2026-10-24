#include "schedule66.h"
#include <limits.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static void accumulate(HB66Counts *c, HB66Event id) {
    ++c->total_events;
    switch(id) {
    case HB66_SMOOTH_ROW: ++c->smooth_rows; break;
    case HB66_EDGE_ROW: ++c->edge_rows; break;
    case HB66_SCALE_MAP: ++c->scale_calls; break;
    case HB66_MID_GREEN_MAP: ++c->midgreen_calls; break;
    case HB66_GREEN_AT_RED: case HB66_GREEN_AT_BLUE:
        ++c->green_colour_estimates; break;
    case HB66_GREEN_SITE_TOP: case HB66_GREEN_SITE_LEFT:
        ++c->untouched_green_site_assignments; break;
    case HB66_BLUE_AT_RED: ++c->blue_at_red_candidates; break;
    case HB66_RED_AT_BLUE: ++c->red_at_blue_candidates; break;
    case HB66_MASK_GREEN_RED_ROW: case HB66_MASK_GREEN_BLUE_ROW:
        ++c->green_site_masks; break;
    case HB66_RB_GREEN_RED_ROW: case HB66_RB_GREEN_BLUE_ROW:
        ++c->red_blue_green_candidates; break;
    case HB66_COPY_RAW_TO_GREEN: break;
    }
}
static int dispatch(HB66Sink sink, void *user, HB66Counts *count,
                    HB66Event event, int x, int y) {
    if(sink && sink(user,event,x,y)!=0) return -3;
    accumulate(count,event);
    return 0;
}
#define DO(ID,X,Y) do { if(dispatch(sink,user,&c,(ID),(X),(Y))!=0) return -3; } while(0)
int hb_schedule66(HB66Domain d, HB66Sink sink, void *user, HB66Counts *counts) {
    HB66Counts c;
    memset(&c,0,sizeof(c));
    if(counts) memset(counts,0,sizeof *counts);
    if(d.width<=0 || d.height<=0 || d.stride<d.width || d.stride<=0 ||
       (uint64_t)d.stride*(uint64_t)d.height > (uint64_t)SIZE_MAX/sizeof(uint16_t))
        return -1;
    /* Native outer alignment changes dimensions when they are not multiples
     * of 8. Do not accidentally generalize interior scheduling to those cases.
     * The scalar GPU/optimized dispatch and other flag combinations are out of
     * this explicitly bounded original-code contract. */
    if(d.flags!=HB66_SCALAR_FLAGS || d.width<24 || d.height<24 ||
       (d.width&7)!=0 || (d.height&7)!=0 ||
       d.width>INT32_MAX-16 || d.height>INT32_MAX-16) return -2;
    /* O(1) safe-size accounting when no event sink is needed; does not
     * interpolate any pixels. The callback path below remains ordered. */
    if(!sink) {
        const uint64_t g=((uint64_t)d.width-8)/2 * (((uint64_t)d.height-8)/2);
        const uint64_t b=((uint64_t)d.width-12)/2 * (((uint64_t)d.height-12)/2);
        const uint64_t q=((uint64_t)d.width-16)/2 * (((uint64_t)d.height-16)/2);
        c.smooth_rows=(uint64_t)d.height-2;
        c.edge_rows=(uint64_t)d.height-4;
        c.scale_calls=c.midgreen_calls=1;
        c.copy_raw_codes=(uint64_t)d.stride*(uint64_t)d.height;
        c.green_colour_estimates=c.untouched_green_site_assignments=2*g;
        c.blue_at_red_candidates=c.red_at_blue_candidates=b;
        c.green_site_masks=c.red_blue_green_candidates=2*q;
        c.total_events=c.smooth_rows+c.edge_rows+3+4*g+2*b+4*q;
        if(counts)*counts=c;
        return 0;
    }
    for(int y=1;y<d.height-1;++y) DO(HB66_SMOOTH_ROW,0,y);
    for(int y=2;y<d.height-2;++y) DO(HB66_EDGE_ROW,0,y);
    DO(HB66_SCALE_MAP,2,2);
    DO(HB66_MID_GREEN_MAP,2,2);
    DO(HB66_COPY_RAW_TO_GREEN,0,0);
    c.copy_raw_codes=(uint64_t)d.stride*(uint64_t)d.height;
    /* m=4, R and B CFA cells. In the native loop the two intervening green
     * sites are populated between R and B calls. Preserve their order. */
    for(int y=4;y<d.height-4;y+=2) for(int x=4;x<d.width-4;x+=2) {
        DO(HB66_GREEN_AT_RED,x,y);
        DO(HB66_GREEN_SITE_TOP,x+1,y);
        DO(HB66_GREEN_SITE_LEFT,x,y+1);
        DO(HB66_GREEN_AT_BLUE,x+1,y+1);
    }
    /* m=6: the opposite colour at the two colour CFA sites. The native call
     * skips the interpolator if the existing direction mask equals zero and
     * instead writes a zero. Mask/zero choice belongs to the callback. */
    for(int y=6;y<d.height-6;y+=2) for(int x=6;x<d.width-6;x+=2) {
        DO(HB66_BLUE_AT_RED,x,y);
        DO(HB66_RED_AT_BLUE,x+1,y+1);
    }
    /* m=8: directions at the two green CFA sites are *recomputed* before
     * the original missing R/B helper. Do not reuse the red/blue site masks. */
    for(int y=8;y<d.height-8;y+=2) for(int x=8;x<d.width-8;x+=2) {
        DO(HB66_MASK_GREEN_RED_ROW,x+1,y);
        DO(HB66_RB_GREEN_RED_ROW,x+1,y);
        DO(HB66_MASK_GREEN_BLUE_ROW,x,y+1);
        DO(HB66_RB_GREEN_BLUE_ROW,x,y+1);
    }
    if(counts)*counts=c;
    return 0;
}
#undef DO
