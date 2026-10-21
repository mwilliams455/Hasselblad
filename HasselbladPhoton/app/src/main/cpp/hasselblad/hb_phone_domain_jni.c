/* SPDX-License-Identifier: MIT */
#include <jni.h>
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
#include "hb_phone_domain.h"

/* Wire v1: 8 signed 64-bit header slots, then 7 slots per grid point:
 * K, tint, exclusion, temperature-status, red, green, blue.
 * Integral jlong transfer is exact; no sensor matrices, HAL results or RAW
 * pixels are retained in native state or exported as constants. */
enum { WIRE_HEADER = 8, WIRE_FIELDS = 7 };
static jlongArray reject(JNIEnv *env, const char *why) {
    jclass error = (*env)->FindClass(env, "java/lang/IllegalArgumentException");
    if (error != NULL) (*env)->ThrowNew(env, error, why);
    return NULL;
}
static jlongArray memory_error(JNIEnv *env) {
    jclass error = (*env)->FindClass(env, "java/lang/OutOfMemoryError");
    if (error != NULL) (*env)->ThrowNew(env, error, "Domain diagnostic allocation failed");
    return NULL;
}
JNIEXPORT jlongArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladDomainDiagnostics_nativeEvaluate(
    JNIEnv *env, jclass clazz, jintArray illuminants, jfloatArray matrices, jintArray request) {
    (void)clazz;
    if (!illuminants || !matrices || !request ||
        (*env)->GetArrayLength(env, illuminants) != 2 ||
        (*env)->GetArrayLength(env, matrices) != 36 ||
        (*env)->GetArrayLength(env, request) != 6)
        return reject(env, "Domain diagnostic requires two A/D65 illuminants, 36 matrices and six grid fields");
    jint kelvins[2], grid[6];
    jfloat values[36];
    (*env)->GetIntArrayRegion(env, illuminants, 0, 2, kelvins);
    (*env)->GetIntArrayRegion(env, request, 0, 6, grid);
    (*env)->GetFloatArrayRegion(env, matrices, 0, 36, values);
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (!((kelvins[0]==2856 && kelvins[1]==6504) ||
          (kelvins[0]==6504 && kelvins[1]==2856)))
        return reject(env, "Only the original A/D65 Camera2 anchor pair is supported");
    hb_phone_temperature_input input = {0};
    for (int i=0; i<2; ++i) {
        input.anchor[i].kelvin = (uint32_t)kelvins[i];
        for (int j=0; j<9; ++j) {
            float c=values[18*i+j], a=values[18*i+9+j];
            if (!isfinite(c) || !isfinite(a) || fabsf(c)>16 || fabsf(a)>16)
                return reject(env, "Camera2 matrix coefficient out of bounded range");
            input.anchor[i].color[j]=c;
            input.anchor[i].calibration[j]=a;
        }
    }
    if (grid[0]<1667 || grid[1]>100000 || grid[0]>grid[1] || grid[2]<=0 ||
        grid[3]<-100 || grid[4]>100 || grid[3]>grid[4] || grid[5]<=0)
        return reject(env, "Unsupported Domain1 grid");
    hb_phone_domain_request bounds = {
        (uint32_t)grid[0], (uint32_t)grid[1], (uint32_t)grid[2],
        grid[3], grid[4], (uint32_t)grid[5]
    };
    hb_phone_domain_result *result = calloc(1, sizeof(*result));
    if (!result) return memory_error(env);
    int status=hb_phone_domain_evaluate(&input,&bounds,result);
    if (status != HB_PHONE_DOMAIN_OK) {
        free(result);
        return reject(env, status==HB_PHONE_DOMAIN_RANGE ?
                     "Invalid grid geometry, counts or exact endpoints" :
                     status==HB_PHONE_DOMAIN_MODEL ?
                     "Unusable original Camera2 temperature matrices" :
                     status==HB_PHONE_DOMAIN_MEMORY ?
                     "Domain1 native allocation failed" :
                     "Domain1 native conversion rejected");
    }
    if (result->schema_version!=HB_PHONE_DOMAIN_SCHEMA ||
        result->point_count>HB_PHONE_DOMAIN_MAX_POINTS ||
        result->point_count!=result->kelvin_count*result->tint_count ||
        result->representable+result->temperature_clipped+
            result->scene_signed_gain+result->adjacent_duplicate!=result->point_count) {
        free(result);
        return reject(env,"Domain1 ABI returned an inconsistent result");
    }
    size_t size = WIRE_HEADER + (size_t)result->point_count * WIRE_FIELDS;
    jlong *wire = calloc(size, sizeof(*wire));
    if (!wire) {free(result);return memory_error(env);}
    wire[0]=result->schema_version; wire[1]=result->kelvin_count;
    wire[2]=result->tint_count; wire[3]=result->point_count;
    wire[4]=result->representable; wire[5]=result->temperature_clipped;
    wire[6]=result->scene_signed_gain; wire[7]=result->adjacent_duplicate;
    for (uint32_t i=0; i<result->point_count; ++i) {
        const hb_phone_domain_point *p=&result->points[i];
        size_t off = WIRE_HEADER + (size_t)i*WIRE_FIELDS;
        wire[off]=p->kelvin; wire[off+1]=p->tint;
        wire[off+2]=p->exclusion; wire[off+3]=p->temperature_status;
        wire[off+4]=p->gain_q12[0]; wire[off+5]=p->gain_q12[1];
        wire[off+6]=p->gain_q12[2];
    }
    free(result);
    jlongArray output=(*env)->NewLongArray(env,(jsize)size);
    if (output!=NULL) (*env)->SetLongArrayRegion(env,output,0,(jsize)size,wire);
    free(wire);
    return output;
}
