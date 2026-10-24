#ifndef HB_INTERPOLATE_SCHEDULE66_H
#define HB_INTERPOLATE_SCHEDULE66_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Independently authored bounded *scheduler*, not independently rendered pixels.
 * All coordinates are aligned RGGB in the already-padded, stride-normalized
 * working domain. Preparation / interpolation callbacks supply pixel math.
 * The original outer DNG import, allocation and alignment scheduler are NOT
 * reproduced. Its tested CPU Interpolate call enables all 16 low flag bits;
 * other dispatch variants are not supported in this checkpoint.
 */
#define HB66_SCALAR_FLAGS UINT16_C(0xffff)
typedef enum {
    HB66_SMOOTH_ROW = 1,     /* x=0, y=source row centre */
    HB66_EDGE_ROW = 2,
    HB66_SCALE_MAP = 3,      /* x=2, y=2; bounds W-2,H-2 exclusive */
    HB66_MID_GREEN_MAP = 4,
    HB66_COPY_RAW_TO_GREEN = 5, /* entire underlying stride*height codes */
    HB66_GREEN_AT_RED = 6,  /* Bayer R site: write R/G/B/mask */
    HB66_GREEN_SITE_TOP = 7, /* Bayer G on red row */
    HB66_GREEN_SITE_LEFT = 8,/* Bayer G on blue row */
    HB66_GREEN_AT_BLUE = 9, /* Bayer B site: write R/G/B/mask */
    HB66_BLUE_AT_RED = 10,  /* mask-gated interpolation or zero fallback */
    HB66_RED_AT_BLUE = 11,
    HB66_MASK_GREEN_RED_ROW = 12, /* compute edge/direction mask */
    HB66_RB_GREEN_RED_ROW = 13, /* mask-gated R/B or zero fallback */
    HB66_MASK_GREEN_BLUE_ROW = 14,
    HB66_RB_GREEN_BLUE_ROW = 15
} HB66Event;

typedef struct {
    int width, height, stride;
    uint16_t flags;
} HB66Domain;
typedef struct {
    uint64_t smooth_rows, edge_rows, scale_calls, midgreen_calls;
    uint64_t copy_raw_codes;
    uint64_t green_colour_estimates, untouched_green_site_assignments;
    uint64_t blue_at_red_candidates, red_at_blue_candidates;
    uint64_t green_site_masks, red_blue_green_candidates;
    uint64_t total_events;
} HB66Counts;
/* Callback MUST NOT access beyond the valid padded working frame. Caller is
 * responsible for applying existing independent interpolation/gradient kernels
 * and checking the direction mask before doing colour writes. This scheduler
 * does not read RAW or create fake intermediate pixel values.
 * Return nonzero from sink to abort enumeration, yielding -3.
 */
typedef int (*HB66Sink)(void *user, HB66Event event, int x, int y);
/* 0 success; -1 malformed geometry/overflow; -2 unsupported native contract;
 * -3 callback failure. Counts are only complete on success.
 */
int hb_schedule66(HB66Domain domain, HB66Sink sink, void *user, HB66Counts *counts);
#ifdef __cplusplus
}
#endif
#endif
