/* SPDX-License-Identifier: MIT */
#include "hb_phone_domain.h"
#include <stdint.h>
#include <stdlib.h>

static int valid_request(const hb_phone_domain_request *r,
                         uint32_t *kelvin_count, uint32_t *tint_count) {
    if (r->first_kelvin < 1667 || r->last_kelvin > 100000 ||
        r->first_kelvin > r->last_kelvin || !r->kelvin_step ||
        r->first_tint < -100 || r->last_tint > 100 ||
        r->first_tint > r->last_tint || !r->tint_step) return 0;
    uint32_t dk = r->last_kelvin - r->first_kelvin;
    uint32_t dt = (uint32_t)(r->last_tint - r->first_tint);
    if (dk % r->kelvin_step || dt % r->tint_step) return 0;
    *kelvin_count = dk / r->kelvin_step + 1;
    *tint_count = dt / r->tint_step + 1;
    return *kelvin_count <= HB_PHONE_DOMAIN_MAX_TEMPERATURES &&
           *tint_count <= HB_PHONE_DOMAIN_MAX_TINTS;
}

int hb_phone_domain_evaluate(const hb_phone_temperature_input *input,
                             const hb_phone_domain_request *request,
                             hb_phone_domain_result *out) {
    if (!input || !request || !out) return HB_PHONE_DOMAIN_ARGUMENT;
    uint32_t nk = 0, nt = 0;
    if (!valid_request(request, &nk, &nt)) return HB_PHONE_DOMAIN_RANGE;
    hb_phone_temperature *temperature = NULL;
    int st = hb_phone_temperature_create(input, &temperature);
    if (st) return st == HB_PHONE_TEMP_MEMORY ? HB_PHONE_DOMAIN_MEMORY : HB_PHONE_DOMAIN_MODEL;
    hb_phone_domain_result *result = calloc(1, sizeof(*result));
    if (!result) { hb_phone_temperature_destroy(temperature); return HB_PHONE_DOMAIN_MEMORY; }
    result->schema_version = HB_PHONE_DOMAIN_SCHEMA;
    result->requested = *request;
    result->kelvin_count = nk; result->tint_count = nt; result->point_count = nk * nt;
    for (uint32_t ti = 0; ti < nt; ++ti) {
        int32_t tint = request->first_tint + (int32_t)(ti * request->tint_step);
        int have_previous = 0;
        uint32_t previous_red = 0, previous_blue = 0;
        for (uint32_t ki = 0; ki < nk; ++ki) {
            hb_phone_domain_point *p = &result->points[ti * nk + ki];
            p->kelvin = request->first_kelvin + ki * request->kelvin_step;
            p->tint = tint;
            hb_phone_temperature_gains gains = {{0,0,0}};
            st = hb_phone_temperature_to_gain(temperature, p->kelvin, (float)tint, &gains);
            p->temperature_status = (uint32_t)st;
            if (st == HB_PHONE_TEMP_CLIPPED) {
                p->exclusion = HB_PHONE_DOMAIN_TEMPERATURE_CLIPPED;
                ++result->temperature_clipped; have_previous = 0;
                continue;
            }
            /* Unexpected temperature-model errors are NOT normal exclusions. */
            if (st || !gains.gain_q12[1]) goto native_error;
            for (uint32_t i = 0; i < 3; ++i)
                if (gains.gain_q12[i] < 4096 || gains.gain_q12[i] >= 40960) goto native_error;
            uint32_t red = (uint32_t)(((uint64_t)gains.gain_q12[0] * 4096u) / gains.gain_q12[1]);
            uint32_t blue = (uint32_t)(((uint64_t)gains.gain_q12[2] * 4096u) / gains.gain_q12[1]);
            if (!red || red > 32767 || !blue || blue > 32767) {
                p->exclusion = HB_PHONE_DOMAIN_SCENE_SIGNED_GAIN;
                ++result->scene_signed_gain; have_previous = 0;
                continue;
            }
            /* As in the original scene-constructor guard, an adjacent pair
             * with the same Q12 R/B coordinates cannot define two knots. */
            if (have_previous && red == previous_red && blue == previous_blue) {
                p->exclusion = HB_PHONE_DOMAIN_ADJACENT_DUPLICATE;
                ++result->adjacent_duplicate;
                continue;
            }
            p->gain_q12[0] = red; p->gain_q12[1] = 4096; p->gain_q12[2] = blue;
            ++result->representable;
            previous_red = red; previous_blue = blue; have_previous = 1;
        }
    }
    *out = *result;
    free(result);
    hb_phone_temperature_destroy(temperature);
    return HB_PHONE_DOMAIN_OK;
native_error:
    free(result);
    hb_phone_temperature_destroy(temperature);
    return HB_PHONE_DOMAIN_NATIVE;
}
