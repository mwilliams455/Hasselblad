/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_TEMPERATURE_H
#define HB_PHONE_TEMPERATURE_H
#include <stdint.h>

/* Owned, temperature-only workspace. It is not a full automatic AWB profile.
 * Matrices are ORIGINAL Camera2 row-major XYZ->reference sensor and
 * reference->individual sensor matrices, with no render normalization or WB.
 * Calls on a successfully created handle are read-only and thread safe.
 * Pointer arguments must refer to complete, disjoint objects. */
typedef struct {
    uint32_t kelvin;
    float color[9];
    float calibration[9];
} hb_phone_temperature_anchor;
typedef struct { hb_phone_temperature_anchor anchor[2]; } hb_phone_temperature_input;
typedef struct hb_phone_temperature hb_phone_temperature;
typedef struct { uint32_t gain_q12[3]; } hb_phone_temperature_gains;
typedef struct { float kelvin, tint, ratio_residual; } hb_phone_temperature_estimate;
enum {
    HB_PHONE_TEMP_OK = 0,
    HB_PHONE_TEMP_ARGUMENT = 1,
    HB_PHONE_TEMP_MATRIX = 2,
    HB_PHONE_TEMP_RANGE = 3,
    HB_PHONE_TEMP_CLIPPED = 4,
    HB_PHONE_TEMP_RESIDUAL = 5,
    HB_PHONE_TEMP_MEMORY = 6,
    HB_PHONE_TEMP_NATIVE = 7
};
/* Output is unchanged on all failures. No vendor code/data or initializer. */
int hb_phone_temperature_create(const hb_phone_temperature_input *, hb_phone_temperature **);
void hb_phone_temperature_destroy(hb_phone_temperature *);
int hb_phone_temperature_matrix(const hb_phone_temperature *, float kelvin, float out[9]);
/* Public-table domain 1667..100000 K; |tint|<=150 is an explicit phone guard.
 * A channel reaching the owned leaf's 10x cap is rejected, not accepted. */
int hb_phone_temperature_to_gain(const hb_phone_temperature *, uint32_t kelvin,
                                  float tint, hb_phone_temperature_gains *);
/* Gains represent inverse camera neutral, not pixel RGB. Input scale cancels.
 * Residual is max relative error of reconstructed channel/green gain ratios.
 * A 0.3% residual gate rejects non-converged/unphysical interpretations. */
int hb_phone_temperature_from_gain(const hb_phone_temperature *, const uint32_t gain[3],
                                    hb_phone_temperature_estimate *);
#endif
