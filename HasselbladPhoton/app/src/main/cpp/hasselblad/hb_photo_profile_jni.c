/* SPDX-License-Identifier: MIT
 * Standalone bounded Stage8 JNI bridge. No camera, sensor, graphics, file or
 * vendor library API. Return NULL for invalid geometry/gamut; never render.
 */
#include <jni.h>
#include <stdint.h>
#include <stdlib.h>
#include "hb_main_lut_profile.h"

JNIEXPORT jintArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladProfilePreparationCheck_nativePrepare(
        JNIEnv *env, jclass clazz, jintArray input, jint cct, jint gamut) {
    (void)clazz;
    if(input==NULL) return NULL;
    jsize count=(*env)->GetArrayLength(env,input);
    if(count!=56 && count!=49152) return NULL;
    size_t words=(size_t)count/8u;
    if(words!=7 && words!=HB_MAIN_LUT_CAMERA_WORDS_PER_PROFILE) return NULL;
    if(gamut!=0 && gamut!=1) return NULL;
    uint32_t *src=(uint32_t*)calloc((size_t)count,sizeof(*src));
    uint32_t *dst=(uint32_t*)calloc(words,sizeof(*dst));
    if(!src || !dst) {free(src);free(dst);return NULL;}
    (*env)->GetIntArrayRegion(env,input,0,count,(jint*)src);
    if((*env)->ExceptionCheck(env)) {free(src);free(dst);return NULL;}
    hb_main_lut_receipt receipt;
    int status=hb_main_lut_prepare(src,(size_t)count,words,
                                   (int32_t)cct,(int32_t)gamut,dst,words,&receipt);
    free(src);
    if(status!=HB_MAIN_LUT_OK || receipt.photographic_render_authorized ||
       receipt.pixel_sampler_verified || receipt.words_written!=words) {
        free(dst);return NULL;
    }
    jintArray result=(*env)->NewIntArray(env,(jsize)words);
    if(result!=NULL) (*env)->SetIntArrayRegion(env,result,0,(jsize)words,(const jint*)dst);
    free(dst);
    return result;
}
