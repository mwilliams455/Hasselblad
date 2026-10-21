/* SPDX-License-Identifier: MIT */
#include <jni.h>
#include <math.h>
#include <stdlib.h>
#include "hb_phone_scene.h"

/* Private Java wire format v1: six header doubles, then six 22-double rows.
 * No pointers or vendor ABI objects cross JNI. RAW is borrowed synchronously. */
JNIEXPORT jdoubleArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladSceneDiagnostics_nativeSweep(
    JNIEnv *env, jclass cls, jobject buffer, jintArray geometry,
    jdoubleArray black, jfloatArray matrices) {
    (void)cls;
    if (!buffer || !geometry || !black || !matrices ||
        (*env)->GetArrayLength(env, geometry) != 7 ||
        (*env)->GetArrayLength(env, black) != 4 ||
        (*env)->GetArrayLength(env, matrices) != 36) goto invalid;
    jint g[7]; jdouble b[4]; jfloat m[36];
    (*env)->GetIntArrayRegion(env, geometry, 0, 7, g);
    (*env)->GetDoubleArrayRegion(env, black, 0, 4, b);
    (*env)->GetFloatArrayRegion(env, matrices, 0, 36, m);
    if ((*env)->ExceptionCheck(env)) return NULL;
    uint8_t *raw = (*env)->GetDirectBufferAddress(env, buffer);
    jlong capacity = (*env)->GetDirectBufferCapacity(env, buffer);
    if (!raw || g[0] < 64 || g[1] < 64 || (g[0]&1) || (g[1]&1) ||
        (uint64_t)g[0]*(uint64_t)g[1] > HB_AWB_MAX_FRAME_PIXELS ||
        g[2] != (int64_t)g[0]*2 || capacity != (int64_t)g[2]*g[1] ||
        g[3] < 0 || g[3] > 3 || g[4] < 1 || g[4] > 65535 ||
        !((g[5] == 2856 && g[6] == 6504) || (g[5] == 6504 && g[6] == 2856))) goto invalid;
    hb_awb_frame_input frame = {0};
    frame.width = frame.right = (uint32_t)g[0];
    frame.height = frame.bottom = (uint32_t)g[1];
    frame.row_stride_bytes = (uint32_t)g[2]; frame.pixel_stride_bytes = 2;
    frame.cfa = (enum hb_awb_cfa)g[3]; frame.white_code = (uint16_t)g[4];
    for (int i=0;i<4;i++) {
        if (!isfinite(b[i]) || b[i]<0 || b[i]>=g[4] || b[i]!=b[0] || b[i]*65536.0!=floor(b[i]*65536.0)) goto invalid;
        frame.black_q16[i] = (int64_t)(b[i]*65536.0);
    }
    hb_phone_temperature_input model = {0};
    for (int a=0;a<2;a++) {
        model.anchor[a].kelvin = (uint32_t)g[5+a];
        for (int i=0;i<9;i++) {
            if (!isfinite(m[a*18+i]) || !isfinite(m[a*18+9+i])) goto invalid;
            model.anchor[a].color[i] = m[a*18+i];
            model.anchor[a].calibration[i] = m[a*18+9+i];
        }
    }
    hb_phone_raw_grid *grid = calloc(1, sizeof(*grid));
    hb_phone_scene_result *result = calloc(1, sizeof(*result));
    if (!grid || !result) {
        free(grid); free(result);
        jclass error = (*env)->FindClass(env, "java/lang/OutOfMemoryError");
        if (error) (*env)->ThrowNew(env, error, "AWB diagnostic workspace allocation failed");
        return NULL;
    }
    double wire[138] = {1};
    wire[1] = hb_phone_raw_build(raw, (size_t)capacity, &frame, HB_PHONE_UNTOUCHED_RAW16_LE, grid);
    if (wire[1] == HB_PHONE_OK) {
        wire[2]=grid->ratio_blocks; wire[3]=grid->nonpositive_blocks;
        wire[4]=grid->saturated_blocks; wire[5]=grid->range_blocks;
        for (int p=0;p<6;p++) {
            /* Deliberate acceptance sweep, not a selected or calibrated policy. */
            hb_phone_scene_policy policy = {0, 128u<<p, 2, 16, .005, .9};
            hb_phone_scene *scene = NULL;
            double *row = wire+6+22*p;
            row[0]=policy.radius_q12;
            int status = hb_phone_scene_create(&model, &policy, &scene);
            if (!status) status = hb_phone_scene_run(scene, grid, result);
            hb_phone_scene_destroy(scene);
            row[1]=status;
            if (status) continue;
            row[2]=result->decision; row[3]=result->native_status;
            row[4]=result->raw_valid; row[5]=result->admitted;
            row[6]=result->classified; row[7]=result->retained;
            for (int i=0;i<3;i++) {row[8+i]=result->gain_q12[i];row[11+i]=result->neutral[i];}
            row[14]=result->temperature.kelvin; row[15]=result->temperature.tint;
            row[16]=result->temperature.ratio_residual;
            for (int i=0;i<1024;i++) {
                uint32_t reason=result->blocks[i].reason;
                if (reason>=1 && reason<=3) row[16+reason]++;
            }
            row[20]=result->admitted-result->classified;
            row[21]=result->classified-result->retained;
        }
    }
    free(result); free(grid);
    jdoubleArray output = (*env)->NewDoubleArray(env, 138);
    if (output) (*env)->SetDoubleArrayRegion(env, output, 0, 138, wire);
    return output;
invalid:;
    jclass error = (*env)->FindClass(env, "java/lang/IllegalArgumentException");
    if (error) (*env)->ThrowNew(env, error, "Unsupported original RAW/metadata diagnostic input");
    return NULL;
}
