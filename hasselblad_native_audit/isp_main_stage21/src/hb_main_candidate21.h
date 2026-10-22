/* SPDX-License-Identifier: MIT
 * Stage21: one experimental 16^3 PLANAR photographic-LUT hypothesis.
 * Neither MAIN pixel layout nor MAIN hardware interpolation is verified.
 * Never attach this to Android saved-photo processing as an HNCS renderer.
 */
#ifndef HB_MAIN_CANDIDATE21_H
#define HB_MAIN_CANDIDATE21_H
#include <stddef.h>
#include <stdint.h>

#define HB21_TABLE_WORDS 6144u
#define HB21_MAX_POINTS 8192u
#define HB21_SCHEMA 1u

enum hb21_status {
    HB21_OK=0,
    HB21_BAD_ARGUMENT=1,
    HB21_BAD_SHAPE=2,
    HB21_INVALID_LUT=3,
    HB21_INVALID_RGB=4,
    HB21_INVALID_PERMUTATION=5,
    HB21_INVALID_INTERPOLATION=6,
    HB21_OVERLAP=7
};
enum hb21_interpolation {
    HB21_TRILINEAR=0,
    HB21_TETRAHEDRAL=1
};

typedef struct hb21_receipt {
    uint32_t schema;
    uint32_t points;
    uint32_t interpolation;
    uint32_t axis_to_input_code;
    uint32_t bank_to_output_code;
    uint32_t source_words;
    uint32_t planar_packing_assumed;
    uint32_t main_isp_pixel_equivalence_proven;
    uint32_t photographic_render_authorized;
} hb21_receipt;

/* Receives one previously prepared 6144-word 3D LUT (Stage8 C preparation).
 * Coordinates are three finite normalized (0..1) linear RGB values. This
 * input transfer/domain is a HYPOTHESIS, not a verified MAIN ISP interface.
 * axis_to_input[i] selects the input channel for physical grid axis i;
 * bank_to_output[i] selects the output channel for physical bank i.
 * Each mapping MUST permute {0,1,2}. Source stores 3 planar banks of 2048
 * words, two 12-bit B-steps per word, with an assumed 16^3 spatial grid.
 * Tetrahedral interpolation is an ALTERNATIVE mathematical experiment.
 * Unlike the proven DISPLAY path, neither candidate was run on MAIN hardware.
 * Strict validation and reject-all-on-error; output/receipt unchanged on
 * invalid input. Exact in-place input/output is supported, other overlap not.
 */
int hb21_sample_candidate(const uint32_t *source, size_t source_words,
                          const double *input, size_t input_scalars,
                          double *output, size_t output_scalars,
                          size_t points, const uint8_t axis_to_input[3],
                          const uint8_t bank_to_output[3],
                          int interpolation, hb21_receipt *receipt);
#endif
