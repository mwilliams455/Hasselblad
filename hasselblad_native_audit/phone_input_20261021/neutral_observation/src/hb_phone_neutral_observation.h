/* SPDX-License-Identifier: MIT */
#ifndef HB_PHONE_NEUTRAL_OBSERVATION_H
#define HB_PHONE_NEUTRAL_OBSERVATION_H
#include <stdint.h>

/* Separate, generic scene-evidence ABI; this is NOT the original X2D E2 ABI.
 * Nothing in this API produces or authorizes a photographic WB neutral.
 * Inputs are supplied by the already verified RAW adapter and Domain1 grid.
 * Keep private camera matrices, RAW pixels, and user scene ratios out of Git. */
#define HB_NS_SCHEMA 1u
#define HB_NS_WIDTH 32u
#define HB_NS_BLOCK_COUNT 1024u
#define HB_NS_MAX_KNOTS 729u
#define HB_NS_NO_INDEX UINT32_MAX

enum hb_ns_status {
    HB_NS_OK=0, HB_NS_ARGUMENT=1, HB_NS_FRAME_UNPROVEN=2,
    HB_NS_DOMAIN_INVALID=3, HB_NS_POLICY_INVALID=4, HB_NS_MEMORY=5
};
enum hb_ns_basis {
    HB_NS_BASIS_UNSPECIFIED=0,
    HB_NS_BASIS_UNSHADED_SENSOR=1,
    HB_NS_BASIS_HYPOTHETICAL_SHADED_STATISTICS=2
};
enum hb_ns_exclusion {
    HB_NS_KNOT_VALID=0, HB_NS_KNOT_TEMPERATURE_CLIPPED=1,
    HB_NS_KNOT_SIGNED_GAIN=2, HB_NS_KNOT_DUPLICATE=3
};
enum hb_ns_block_reason {
    HB_NS_BLOCK_EVALUATED=0, HB_NS_BLOCK_RAW_REJECTED=1,
    HB_NS_BLOCK_BRIGHTNESS_REJECTED=2, HB_NS_BLOCK_GREEN_SPLIT_REJECTED=3,
    HB_NS_BLOCK_SIGNED_GAIN_REJECTED=4
};
enum hb_ns_evidence_decision {
    HB_NS_ABSTAIN_NO_CANDIDATE_SUPPORT=1,
    HB_NS_ABSTAIN_UNCALIBRATED=2
};

typedef struct {
    uint32_t kelvin;
    int32_t tint;
    uint32_t red_gain_q12, blue_gain_q12;
    uint32_t exclusion; /* Matches Domain1 public exclusion enum. */
} hb_ns_knot;
typedef struct {
    uint32_t schema, count;
    hb_ns_knot points[HB_NS_MAX_KNOTS]; /* Tint-major, ascending temperature. */
} hb_ns_domain;

typedef struct {
    double mean[4]; /* Original normalized R,Gr,Gb,B sensor sites. */
    double mean_brightness;
    uint32_t red_gain_q12, blue_gain_q12;
    uint32_t raw_flags; /* Retained phone RAW adapter flags: 1,2,4. */
} hb_ns_block;
typedef struct {
    uint64_t sensor_timestamp_ns, exposure_time_ns;
    uint32_t ISO;
    uint32_t bound_to_physical_sensor_and_frame;
    uint32_t original_single_raw_proven;
    uint32_t basis; /* Never silently apply/remove lens shading here. */
    hb_ns_block blocks[HB_NS_BLOCK_COUNT];
} hb_ns_frame;

typedef struct {
    /* Explicit experimental diagnostic controls; never shipping defaults. */
    uint32_t study_radius_q12;         /* 1..4096. NOT a neutral-acceptance radius. */
    uint32_t spatial_edge_radius_q12;  /* 1..4096, true bounded 8-neighbours. */
    uint32_t minimum_support_blocks;   /* 4..1024, diagnostic support only. */
    double minimum_brightness, maximum_brightness; /* 0 <= min < max <= 1 */
    double maximum_green_site_disagreement;        /* 0 < fraction <= 1 */
} hb_ns_policy;

typedef struct {
    uint32_t reason, nearest_knot_index, near_lattice, component_index;
    float distance_q12; /* Distance in GREEN-normalized raw gain coordinates. */
} hb_ns_trace;

typedef struct {
    uint32_t schema, decision, render_permitted, calibrated_policy;
    uint32_t evaluated_blocks, raw_rejected, brightness_rejected;
    uint32_t green_split_rejected, signed_gain_rejected;
    uint32_t near_valid_knot, far_from_grid, near_tint_edge;
    uint32_t near_quadrants_bitmask;
    uint32_t spatial_components, largest_spatial_component;
    uint32_t support_threshold_met; /* Diagnostic ONLY; still ABSTAIN. */
    uint32_t usable_domain_points, excluded_domain_points;
    uint32_t shading_basis; /* Provenance only, do not correct pixels. */
    hb_ns_trace blocks[HB_NS_BLOCK_COUNT];
} hb_ns_result;

/* Output is untouched on ALL API failures. Success intentionally returns only
 * per-frame evidence and an ABSTAIN decision, never a WB gain/neutral vector.
 * No HAL input, no vendor spectral data, no history, no fallback, no renderer.
 * Client must have already bound camera/frame and same profile's Domain1 grid.
 * The absence of a reference illuminant/target cannot be filled by proximity. */
int hb_phone_neutral_observe(const hb_ns_domain *, const hb_ns_frame *,
                             const hb_ns_policy *, hb_ns_result *);
#endif
