#include "green_site_mask67.h"
#include "raw_gradient67.h"
#include "../phocus_gradient_stage61/gradient_maps61.h"
#include <stdint.h>
int hb_green_site_mask67(const uint16_t *raw_centre,
                         const int16_t *edge_centre,int stride,
                         int16_t first_floor,int16_t second_floor,
                         int16_t signed_gradients[8],int16_t raw_gradients[8],
                         uint16_t *packed_mask) {
    if (!raw_centre || !edge_centre || !signed_gradients || !raw_gradients ||
        !packed_mask || stride<5 || signed_gradients==raw_gradients) return -1;
    if (hb_gradient_directions61(edge_centre,stride,signed_gradients)!=0)return -1;
    if (hb_inline_raw_gradient67(raw_centre,stride,raw_gradients)!=0)return -1;
    *packed_mask=hb_gradient_mask61(signed_gradients,raw_gradients,
                                    first_floor,second_floor);
    return 0;
}
