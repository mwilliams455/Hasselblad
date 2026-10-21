/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_DOMAIN_H
#define HB_PHONE_DOMAIN_H
#include "hb_phone_temperature.h"
#include <stdint.h>

/* Separate, diagnostic-only temperature/tint coverage. A representable point
 * is NOT a selected illuminant, a native scene candidate or a render permit.
 * The fixed 81-point hb_phone_scene ABI remains unchanged. */
#define HB_PHONE_DOMAIN_MAX_TEMPERATURES 81u
#define HB_PHONE_DOMAIN_MAX_TINTS 9u
#define HB_PHONE_DOMAIN_MAX_POINTS (HB_PHONE_DOMAIN_MAX_TEMPERATURES * HB_PHONE_DOMAIN_MAX_TINTS)
#define HB_PHONE_DOMAIN_SCHEMA 1u

typedef struct {
    uint32_t first_kelvin, last_kelvin, kelvin_step;
    int32_t first_tint, last_tint;
    uint32_t tint_step;
} hb_phone_domain_request;

enum hb_phone_domain_status {
    HB_PHONE_DOMAIN_OK = 0,
    HB_PHONE_DOMAIN_ARGUMENT = 1,
    HB_PHONE_DOMAIN_RANGE = 2,
    HB_PHONE_DOMAIN_MODEL = 3,
    HB_PHONE_DOMAIN_MEMORY = 4,
    HB_PHONE_DOMAIN_NATIVE = 5
};
enum hb_phone_domain_exclusion {
    HB_PHONE_DOMAIN_REPRESENTABLE = 0,
    HB_PHONE_DOMAIN_TEMPERATURE_CLIPPED = 1,
    HB_PHONE_DOMAIN_SCENE_SIGNED_GAIN = 2,
    HB_PHONE_DOMAIN_ADJACENT_DUPLICATE = 3
};

typedef struct {
    uint32_t kelvin;
    int32_t tint;
    uint32_t exclusion;
    uint32_t temperature_status;    /* Exact hb_phone_temperature_to_gain status. */
    uint32_t gain_q12[3];          /* Representable only; green is 4096. */
} hb_phone_domain_point;

typedef struct {
    uint32_t schema_version;
    hb_phone_domain_request requested;
    uint32_t kelvin_count, tint_count, point_count;
    uint32_t representable, temperature_clipped, scene_signed_gain, adjacent_duplicate;
    hb_phone_domain_point points[HB_PHONE_DOMAIN_MAX_POINTS]; /* tint-major; ascending CT */
} hb_phone_domain_result;

/* Explicit integer grid (tint unit = the owned temperature leaf's tint unit).
 * Kelvin: [1667,100000], tint: [-100,100], at most 81 x 9 points.
 * Endpoints must lie exactly on the supplied positive step grid; no silent
 * truncation. Every point is reported, including excluded points. This is
 * relatively expensive: generate per physical-camera metadata profile, NOT
 * once per RAW block or on the shutter hot path.
 * Inputs and output must be complete, disjoint objects. On API failure the
 * entire output remains unchanged. No HAL WB, luminance priors, pixel data,
 * lens shading, fallback, LUT interpolation or photographic rendering. */
int hb_phone_domain_evaluate(const hb_phone_temperature_input *,
                             const hb_phone_domain_request *,
                             hb_phone_domain_result *);
#endif
