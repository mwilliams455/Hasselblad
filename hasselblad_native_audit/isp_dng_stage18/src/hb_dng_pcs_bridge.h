/* SPDX-License-Identifier: MIT
 * Stage18 camera -> XYZ D50 reference. DNG ForwardMatrix-compatible bounded
 * branch only. Not Hasselblad CCM, not HNCS photographic output.
 */
#ifndef HB_DNG_PCS_BRIDGE_H
#define HB_DNG_PCS_BRIDGE_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HB_DNG_PCS_BRIDGE_SCHEMA 18u
#define HB_DNG_PCS_MAX_PROBE_PIXELS 1024u
/* Distinct Stage18 status values, not DNG SDK status codes. */
enum { HB_DNG_PCS_OK=0, HB_DNG_PCS_INVALID=1, HB_DNG_PCS_UNSUPPORTED_INTERPOLATION=2,
       HB_DNG_PCS_SINGULAR=3, HB_DNG_PCS_OVERLAP=4 };
typedef struct {
    unsigned schema;
    unsigned dual_forward_equal;
    unsigned dual_calibration_equal;
    unsigned camera_white_balanced;
    unsigned numerical_pcs_white_verified;
    unsigned original_hasselblad_ccm_verified;
    unsigned original_hasselblad_lut_verified;
    unsigned photographic_render_authorized;
} hb_dng_pcs_receipt;
/* Parameters are natively encoded DNG matrices/metadata converted to f64.
 * All 3x3 matrices are row-major. AnalogBalance omitted in DNG -> {1,1,1};
 * CameraCalibration absent -> identity. fm2/cc2 may be NULL if absent.
 * A dual-illuminant FM/CC *different* between anchors is currently unsupported.
 * The shader adapter is independent of any phone brand or sensor model.
 * Transactional failure: matrix and receipt are unchanged.
 */
int hb_dng_pcs_build(const double fm1[9], const double fm2[9],
                     const double cc1[9], const double cc2[9],
                     const double ab[3], const double as_shot_neutral[3],
                     double out_cam_to_xyz_d50[9], hb_dng_pcs_receipt *receipt);
/* Apply to already demosaiced LINEAR camera samples (not Bayer mosaic).
 * No exposure adjustment, gamma, range clamp, colour look or tone mapping.
 * Negative and over-unity finite samples are intentionally preserved.
 * Require source/destination disjoint; fail before any output mutation.
 */
int hb_dng_pcs_apply(const double transform[9], const double *rgb_camera,
                     size_t num_pixels, double *xyz_d50);
#ifdef __cplusplus
}
#endif
#endif
