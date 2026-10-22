/* SPDX-License-Identifier: MIT
 * Stage26 opt-in diagnostic JNI: Stage24 DNG PCS -> linear RGB ONLY.
 * Accepts already-demosaiced camera-native linear RGB and caller-validated DNG
 * matrices. It does NOT decode DNG, access Camera2, generate/save JPEG, guess
 * WB, load Hasselblad tables or invoke the Stage21 hypothetical MAIN sampler.
 * The output is scene-linear f64, NOT a display-ready/rendered photograph.
 */
#include <jni.h>
#include <stdint.h>
#include "hb24_renderer.h"

#define HB26_BAD_JNI_INPUT 100
#define HB26_JNI_EXCEPTION 101
#define HB26_UNVERIFIED_RESULT 102

static int required_size(JNIEnv *env, jdoubleArray value, jsize count) {
    return value != NULL && (*env)->GetArrayLength(env, value) == count;
}
static int optional_size(JNIEnv *env, jdoubleArray value, jsize count) {
    return value == NULL || (*env)->GetArrayLength(env, value) == count;
}
static int aliases(JNIEnv *env, jdoubleArray output, jdoubleArray other) {
    return other != NULL && (*env)->IsSameObject(env, output, other);
}
static int copy_array(JNIEnv *env, jdoubleArray src, jsize count, double *dst) {
    (*env)->GetDoubleArrayRegion(env, src, 0, count, dst);
    return !(*env)->ExceptionCheck(env);
}

/* Returns 0 for a successful Stage24 PCS-only native tile, original Stage24
 * failure codes 1..6, or bridge statuses 100..102. The output remains
 * unchanged for all ordinary validation and math failures.
 *
 * Two independent validations still precede real-image use:
 * (1) the caller must prove each matrix/neutral belongs to the SAME RAW frame;
 * (2) DNG opcodes, black levels, shading and demosaic must be resolved upstream.
 * This JNI boundary does not waive those requirements.
 */
JNIEXPORT jint JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladColourReferenceCheck_nativeLinearTile(
        JNIEnv *env, jclass clazz,
        jdoubleArray fm1, jdoubleArray fm2,
        jdoubleArray cc1, jdoubleArray cc2,
        jdoubleArray analog_balance, jdoubleArray neutral,
        jint gamut, jdoubleArray camera_rgb, jint pixels,
        jdoubleArray out_linear_rgb) {
    (void)clazz;
    if (pixels < 1 || pixels > (jint)HB24_MAX_PIXELS) return HB26_BAD_JNI_INPUT;
    jsize channels = pixels * 3;
    if (!required_size(env, fm1, 9) ||
        !optional_size(env, fm2, 9) ||
        !optional_size(env, cc1, 9) ||
        !optional_size(env, cc2, 9) ||
        !optional_size(env, analog_balance, 3) ||
        !required_size(env, neutral, 3) ||
        !required_size(env, camera_rgb, channels) ||
        !required_size(env, out_linear_rgb, channels) ||
        (gamut != HB19_SRGB && gamut != HB19_DISPLAY_P3))
        return HB26_BAD_JNI_INPUT;

    if (aliases(env, out_linear_rgb, fm1) ||
        aliases(env, out_linear_rgb, fm2) ||
        aliases(env, out_linear_rgb, cc1) ||
        aliases(env, out_linear_rgb, cc2) ||
        aliases(env, out_linear_rgb, analog_balance) ||
        aliases(env, out_linear_rgb, neutral) ||
        aliases(env, out_linear_rgb, camera_rgb))
        return HB26_BAD_JNI_INPUT;

    double m1[9],m2[9],c1[9],c2[9],ab[3],n[3];
    double camera[HB24_MAX_PIXELS * 3];
    double converted[HB24_MAX_PIXELS * 3];
    if (!copy_array(env,fm1,9,m1) ||
        (fm2 != NULL && !copy_array(env,fm2,9,m2)) ||
        (cc1 != NULL && !copy_array(env,cc1,9,c1)) ||
        (cc2 != NULL && !copy_array(env,cc2,9,c2)) ||
        (analog_balance != NULL && !copy_array(env,analog_balance,3,ab)) ||
        !copy_array(env,neutral,3,n) ||
        !copy_array(env,camera_rgb,channels,camera))
        return HB26_JNI_EXCEPTION;

    hb24_context context={0};
    hb24_receipt built={0},processed={0};
    int status=hb24_build(m1, fm2 != NULL ? m2 : NULL,
        cc1 != NULL ? c1 : NULL, cc2 != NULL ? c2 : NULL,
        analog_balance != NULL ? ab : NULL,
        n,(int)gamut,&context,&built);
    if (status != HB24_OK) return (jint)status;
    status=hb24_process(&context,camera,(size_t)pixels,converted,HB24_PCS_ONLY,
                        NULL,0,NULL,NULL,0,&processed);
    if (status != HB24_OK) return (jint)status;
    if (built.photographic_render_authorized ||
        processed.photographic_render_authorized ||
        processed.true_hasselblad_ccm_pixel_proven ||
        processed.true_hasselblad_gamma_pixel_proven ||
        processed.true_hasselblad_lut_pixel_proven ||
        processed.true_hasselblad_wb_calibrated ||
        processed.uses_stage21_MAIN_hypothesis ||
        processed.existing_phone_renderer_modified ||
        !processed.output_linear_light ||
        processed.pixel_count != (uint32_t)pixels)
        return HB26_UNVERIFIED_RESULT;

    /* Commit in one bounded operation only after all native checks pass. */
    (*env)->SetDoubleArrayRegion(env,out_linear_rgb,0,channels,converted);
    return (*env)->ExceptionCheck(env) ? HB26_JNI_EXCEPTION : HB24_OK;
}
