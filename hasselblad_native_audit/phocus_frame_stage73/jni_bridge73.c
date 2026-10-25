#include "frame73.h"
#include <jni.h>
#include <stdint.h>
#include <stdlib.h>
#include <limits.h>
/* JNI smoke interface for pre-ColorNoise linear RGB16 + direction mask ONLY.
 * No Android camera capture or display code is changed by this source.
 * Both sides are Java short[] containers; reinterpret codes as unsigned bits.
 */
JNIEXPORT jint JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladPreNoise73_nativeRender(
    JNIEnv *env,jclass cls,jshortArray input,jint out_w,jint out_h,
    jint source_stride,jint cfa,jshortArray result){
    (void)cls;
    if(!input||!result)return HB73_BAD_ARGUMENT;
    if((*env)->IsSameObject(env,input,result))return HB73_BAD_ARGUMENT;
    HB73Plan plan;
    int rc=hb73_plan(out_w,out_h,&plan);
    if(rc)return rc;
    if(source_stride<plan.source_width||source_stride>4096)return HB73_BAD_ARGUMENT;
    size_t n=(size_t)source_stride*plan.source_height;
    size_t o=(size_t)out_w*out_h*4;
    if(n>INT_MAX||o>INT_MAX)return HB73_BAD_ARGUMENT;
    if((*env)->GetArrayLength(env,input)<(jsize)n||
       (*env)->GetArrayLength(env,result)<(jsize)o)return HB73_BAD_ARGUMENT;
    uint16_t *in=malloc(n*sizeof(uint16_t)),*out=malloc(o*sizeof(uint16_t));
    if(!in||!out){free(in);free(out);return HB73_ALLOCATION_FAILED;}
    (*env)->GetShortArrayRegion(env,input,0,(jsize)n,(jshort*)in);
    if((*env)->ExceptionCheck(env)){
        free(in);free(out);return HB73_BAD_ARGUMENT;
    }
    const HB73Settings settings={cfa,0xffffu,1.0,32,200,0};
    rc=hb73_render_pre_noise(&plan,&settings,in,n,source_stride,out,o,NULL);
    if(rc==HB73_OK)(*env)->SetShortArrayRegion(env,result,0,(jsize)o,(const jshort*)out);
    free(in);free(out);
    return rc;
}
