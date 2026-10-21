/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_SCENE_H
#define HB_PHONE_SCENE_H
#include "hb_phone_raw.h"
#include "hb_phone_temperature.h"

/* Explicit experimental policy. There is intentionally no default or claim
 * that these settings are camera calibration supplied by Camera2. */
typedef struct {
    float center_tint;
    uint32_t radius_q12;           /* 1..4096, in GREEN-normalized gain space */
    uint32_t neighbor_factor;      /* 1..255 and <=radius */
    uint32_t minimum_blocks;       /* 4..1020, a multiple of four */
    double minimum_brightness;     /* [0,1), arithmetic normalized Bayer mean */
    double maximum_brightness;     /* (minimum,1], not EV or scene luminance */
} hb_phone_scene_policy;
typedef struct hb_phone_scene hb_phone_scene;
enum hb_phone_scene_decision {
    HB_PHONE_SCENE_NO_CANDIDATE=0,
    HB_PHONE_SCENE_DIAGNOSTIC_CANDIDATE=1,
    HB_PHONE_SCENE_TEMPERATURE_REJECTED=2
};
enum hb_phone_scene_status {
    HB_PHONE_SCENE_OK=0, HB_PHONE_SCENE_ARGUMENT=1,
    HB_PHONE_SCENE_POLICY=2, HB_PHONE_SCENE_MODEL=3,
    HB_PHONE_SCENE_MEMORY=4, HB_PHONE_SCENE_NATIVE=5
};
enum hb_phone_scene_block_reason {
    HB_PHONE_SCENE_ADMITTED=0, HB_PHONE_SCENE_RAW_REJECTED=1,
    HB_PHONE_SCENE_BRIGHTNESS_REJECTED=2,
    HB_PHONE_SCENE_SIGNED_GAIN_REJECTED=3
};
typedef struct {
    uint32_t reason, classified, locus_index, survives;
    float distance_q12;
    uint16_t weight_before, weight_after;
} hb_phone_scene_block_trace;
typedef struct {
    uint32_t decision, native_status;
    uint32_t raw_valid, admitted, classified, retained;
    uint32_t gain_q12[3];
    float neutral[3];              /* candidate only, green normalized */
    hb_phone_temperature_estimate temperature;
    hb_phone_scene_block_trace blocks[1024];
} hb_phone_scene_result;

/* Bounded ordinary single-candidate route. Exact 81-point locus generated
 * from phone matrices, exhaustive nearest-point classification, then owned
 * firmware weight/filter/accumulation/optimizer leaves. Not hb_run_automatic.
 * No firmware initializer/config/pointers, semantic/spectral/exposure/history
 * data, or HAL neutral. No output is authorized for rendering by this API.
 * Immutable handle; each run starts from empty working state. */
int hb_phone_scene_create(const hb_phone_temperature_input *,
                         const hb_phone_scene_policy *, hb_phone_scene **);
void hb_phone_scene_destroy(hb_phone_scene *);
int hb_phone_scene_locus(const hb_phone_scene *, uint32_t out[81][3]);
/* Input must be the matching original-metadata-bound RAW adapter result.
 * The offline binder currently supports equal per-site normalization spans.
 * Rejected API calls leave output unchanged. Successful no-candidate calls
 * clear all result gains/neutral; they never reuse a previous candidate. */
int hb_phone_scene_run(const hb_phone_scene *, const hb_phone_raw_grid *,
                      hb_phone_scene_result *);
#endif
