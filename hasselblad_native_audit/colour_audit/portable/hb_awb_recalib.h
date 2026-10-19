#ifndef HB_AWB_RECALIB_H
#define HB_AWB_RECALIB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Proven only for this exact input ELF; these are provenance, not image-look IDs. */
#define HB_AWB_FIRMWARE "Hasselblad X2D II 100C 1.3.16.2"
#define HB_AWB_LIBRARY "libaaa.so"
#define HB_AWB_LIBRARY_SHA256 "7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba"
#define HB_AWB_SYMBOL "scene_awb_result_recalib_unit"
#define HB_AWB_SYMBOL_VA UINT32_C(0x4a39a0)
#define HB_AWB_SYMBOL_BYTES UINT32_C(56)
#define HB_AWB_Q12_UNITY UINT32_C(4096)
/* Largest input whose original 32-bit left shift by 12 cannot overflow. */
#define HB_AWB_MAX_SAFE_GAIN (UINT32_MAX >> 12)

/* Adapter status values are ours, not vendor-defined enum names. */
enum hb_awb_adapter_status {
    HB_AWB_OK = 0,
    HB_AWB_ZERO_CALIBRATION = 1,
    HB_AWB_GAIN_OVERFLOW = 2,
    HB_AWB_ORIGINAL_MISSING = 3,
    HB_AWB_ORIGINAL_REJECTED = 4
};

typedef struct hb_awb_q12_pair {
    uint32_t a;
    uint32_t b;
} hb_awb_q12_pair;

typedef struct hb_awb_recalib_result {
    int32_t adapter_status;
    /* Valid only when original_called == 1; never fabricate a vendor return. */
    uint32_t original_status;
    uint32_t original_called;
    /* Remains equal to the input on every error. */
    hb_awb_q12_pair output;
} hb_awb_recalib_result;

/* ABI recovered from the exact function and corroborated by its firmware callers. */
typedef uint32_t (*hb_awb_original_recalib_fn)(uint32_t *gain_a,
                                             uint32_t *gain_b,
                                             uint32_t calibration_a,
                                             uint32_t calibration_b);

/*
 * Recovered Q12 arithmetic only. This does not infer calibration, determine WB,
 * invoke full AWB, apply gains to pixels, or implement an HNCS renderer.
 * Inputs/calibrations must already be expressed in the audited routine's units.
 */
hb_awb_recalib_result hb_awb_recalib_portable(hb_awb_q12_pair input,
                                            hb_awb_q12_pair calibration);

/*
 * Optional adapter to an already loaded, exact-hash, ABI-verified original.
 * This library never dlopens anything and never guesses/casts arbitrary symbols.
 * It validates before calling and commits output only when the vendor returns 0.
 */
hb_awb_recalib_result hb_awb_recalib_original(hb_awb_original_recalib_fn original,
                                            hb_awb_q12_pair input,
                                            hb_awb_q12_pair calibration);

#ifdef __cplusplus
}
#endif
#endif
