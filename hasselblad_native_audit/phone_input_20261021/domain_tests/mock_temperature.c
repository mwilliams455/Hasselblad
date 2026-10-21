/* SPDX-License-Identifier: MIT */
/* Only for coverage-module tests; NOT the real phone temperature model. */
#include "hb_phone_temperature.h"
#include <stdlib.h>
typedef struct { uint32_t status, gain[3]; } hb_test_fixture;
static hb_test_fixture fixture[729];
static int fixture_ready;
struct hb_phone_temperature { uint32_t marker; };
int hb_phone_temperature_create(const hb_phone_temperature_input *input,
                                hb_phone_temperature **out) {
    if (!input || !out) return HB_PHONE_TEMP_ARGUMENT;
    if (input->anchor[0].kelvin == 9999) return HB_PHONE_TEMP_MATRIX;
    hb_phone_temperature *w = calloc(1,sizeof(*w));
    if (!w) return HB_PHONE_TEMP_MEMORY;
    w->marker = input->anchor[0].kelvin;
    *out = w; return HB_PHONE_TEMP_OK;
}
void hb_phone_temperature_destroy(hb_phone_temperature *w) { free(w); }
int hb_phone_temperature_to_gain(const hb_phone_temperature *w, uint32_t ct,
                                 float tint, hb_phone_temperature_gains *out) {
    if (!w || !out) return HB_PHONE_TEMP_ARGUMENT;
    if (w->marker == 7000) {
        if (!fixture_ready || ct < 2000 || ct > 10000 || (ct-2000)%100 ||
            tint < -100 || tint > 100 || ((int32_t)tint+100)%25)
            return HB_PHONE_TEMP_RANGE;
        uint32_t index = (uint32_t)(((int32_t)tint + 100)/25)*81+(ct-2000)/100;
        if (fixture[index].status) return (int)fixture[index].status;
        for (unsigned i=0;i<3;++i) out->gain_q12[i]=fixture[index].gain[i];
        return HB_PHONE_TEMP_OK;
    }
    if (w->marker == 4321 && ct == 4000 && tint == -100)
        return HB_PHONE_TEMP_NATIVE;
    if (tint == 100 && ct < 2300) return HB_PHONE_TEMP_CLIPPED;
    uint32_t index = (ct - 2000) / 100;
    uint32_t red = (uint32_t)(8000 + (int32_t)index*11 + (int32_t)tint*3);
    uint32_t blue = (uint32_t)(10000 + (int32_t)index*7 - (int32_t)tint*4);
    if (tint == 50 && ct == 2800) red = 34000;
    if (tint == 75 && ct == 3100) {
        red = (uint32_t)(8000 + 10*11 + 75*3);
        blue = (uint32_t)(10000 + 10*7 - 75*4);
    }
    out->gain_q12[0] = red; out->gain_q12[1] = 4096; out->gain_q12[2] = blue;
    return HB_PHONE_TEMP_OK;
}

/* Optional read-only fixture injection for exact saved-model status/gain replay.
 * The injected data are supplied privately at test time, never in this file. */
int hb_test_set_fixture(const hb_test_fixture *samples, uint32_t count) {
    if (!samples || count != 729) return 1;
    for (uint32_t i=0;i<count;++i) fixture[i] = samples[i];
    fixture_ready = 1; return 0;
}
