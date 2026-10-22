/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_NEUTRAL_BINDING_H
#define HB_PHONE_NEUTRAL_BINDING_H
#include "hb_phone_neutral_observation.h"
#include "../../hb_phone_raw.h"
#include "../../hb_phone_domain.h"

/* Typed bridge between the existing, unchanged phone RAW and Domain1 APIs
 * and Stage4. The caller must independently prove the physical-camera/frame
 * relationship and preserve raw/statistics shading provenance. No HAL neutral. */
typedef struct {
    uint64_t original_sensor_timestamp_ns;
    uint64_t original_exposure_time_ns;
    uint32_t original_ISO;
    uint32_t original_single_raw_frame_proven;
    uint32_t physical_camera_and_result_frame_proven;
    uint32_t original_capture_color_metadata_proven;
    uint32_t raw_statistics_basis; /* HB_NS_BASIS_* */
} hb_ns_capture_binding;

enum hb_ns_bind_status {
    HB_NS_BIND_OK=0,
    HB_NS_BIND_ARGUMENT=1,
    HB_NS_BIND_UNPROVEN=2,
    HB_NS_BIND_DOMAIN_INVALID=3,
    HB_NS_BIND_RAW_INVALID=4,
    HB_NS_BIND_MEMORY=5
};

/* On all nonzero returns BOTH outputs remain unchanged. The native Stage4
 * observer performs further consistency checks and always abstains from WB.
 * Preserve the exactly reported per-point exclusion mask; do not synthesize
 * a nearest HAL or select a radius. */
int hb_phone_neutral_bind(const hb_phone_raw_grid *,
                          const hb_phone_domain_result *,
                          const hb_ns_capture_binding *,
                          hb_ns_frame *, hb_ns_domain *);
#endif
