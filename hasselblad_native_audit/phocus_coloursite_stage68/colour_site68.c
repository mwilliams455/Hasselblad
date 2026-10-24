#include "colour_site68.h"
#include "colour_gradient68.h"
#include "../phocus_gradient_stage61/gradient_maps61.h"
#include "../phocus_green_stage63/green63.h"
#include <stdint.h>
int hb_colour_site_green68(const uint16_t *raw, const int16_t *edge,
    const float *horizontal, const float *vertical, const float *scale,
    int stride, int16_t edge_floor, int16_t raw_floor,
    int32_t *green, int32_t *direction_mask, int16_t *maximum_gradient) {
    if (!raw || !edge || !horizontal || !vertical || !scale || !green ||
        !direction_mask || !maximum_gradient || stride<5) return -1;
    int16_t edge_gradients[8], raw_gradients[8];
    if (hb_gradient_directions61(edge,stride,edge_gradients)!=0 ||
        hb_colour_raw_gradient68(raw,stride,raw_gradients)!=0) return -1;
    hb_green_at_colour63(raw,horizontal,vertical,scale,stride,
       edge_gradients,raw_gradients,edge_floor,raw_floor,
       green,direction_mask,maximum_gradient);
    return 0;
}
