/* SPDX-License-Identifier: MIT
 * Historical scene-optimizer CALLER handoff — bounded, evidence-driven replay.
 * The numerical optimizer was lost: this code DOES NOT calculate the original
 * optimizer or temperature LUT and never claims to produce a fresh vendor WB.
 */
#ifndef HB_AWB_OPTIMIZER_BOUNDARY_H
#define HB_AWB_OPTIMIZER_BOUNDARY_H
#include <stdint.h>
#include "hb_awb_frame_stats.h"

#define HB_AWB_OPT_TRACE_REVISION 1u
#define HB_AWB_OPT_FINGERPRINT_SEED UINT64_C(14695981039346656037)

/* This hash is for ACCIDENTAL fixture misassociation only. It is NOT a
 * cryptographic origin signature and must not be represented as evidence
 * that an observation was made on the original vendor firmware. */
uint64_t hb_awb_accumulation_fingerprint(const hb_awb_scene_accumulation *acc);

/* These explicit caller-side deltas are supplied by a reference TRACE.
 * No count formula was retained in the handoff, so it is never guessed. */
typedef struct hb_awb_optimizer_trace {
    uint32_t revision;
    uint64_t frame_serial;
    uint64_t expected_accumulation_fingerprint;
    int32_t observed_optimizer_status;
    uint32_t observed_caller_delta_candidates;
    uint32_t observed_caller_delta_blocks;
    uint64_t observed_caller_delta_samples;
    uint8_t caller_window_observed;
    /* Opaque result bytes from a caller-supplied, instrumented observation;
     * no claims are made about vendor struct layout, units or interpolation. */
    uint8_t opaque_result[32];
} hb_awb_optimizer_trace;

typedef struct hb_awb_optimizer_staged {
    uint64_t frame_serial;
    uint64_t input_fingerprint;
    int32_t observed_optimizer_status;
    uint32_t caller_delta_candidates;
    uint32_t caller_delta_blocks;
    uint64_t caller_delta_samples;
    uint8_t opaque_result[32];
    uint8_t original_firmware_equivalence_proven; /* ALWAYS 0 */
    uint8_t selected_neutral_produced; /* ALWAYS 0 */
} hb_awb_optimizer_staged;

typedef struct hb_awb_optimizer_caller_state {
    uint64_t last_applied_frame_serial;
    uint64_t candidate_count;
    uint64_t consumed_block_count;
    uint64_t consumed_sample_count;
    int32_t last_optimizer_status;
    uint8_t opaque_last_result[32];
    uint8_t selected_neutral_produced; /* ALWAYS 0 */
} hb_awb_optimizer_caller_state;

/* Step 1: stage a trace under an exact accumulation fingerprint. This is a
 * REPLAY of supplied observations, NOT an implementation of the numerical
 * scene optimizer. Does not touch any caller state, including on success. */
int hb_awb_optimizer_stage_observation(const hb_awb_scene_accumulation *acc,
                                        const hb_awb_optimizer_trace *trace,
                                        hb_awb_optimizer_staged *out);

/* Step 2: ONLY AFTER the staged return, apply explicitly observed caller-side
 * count deltas. Prevents double application and wrong-frame reuse. A failure
 * never modifies state. The recorded original behaviour does not establish
 * the delta formula or the caller's action on each error; trace supplies it. */
int hb_awb_optimizer_apply_observed_caller_update(
        const hb_awb_optimizer_staged *staged,
        hb_awb_optimizer_caller_state *state);
#endif