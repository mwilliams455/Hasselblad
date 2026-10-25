#include <jni.h>
#include "frame74.h"

JNIEXPORT jint JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladFinalRaw74_renderLinearRgb16Native(
    JNIEnv *env, jclass cls, jshortArray input_array, jint input_stride,
    jint width, jint height, jint cfa, jshortArray output_array){
    (void)cls;
    if(!input_array||!output_array)return -1;
    if((*env)->IsSameObject(env,input_array,output_array))return -1;
    HB73Plan plan;
    int status=hb73_plan(width,height,&plan);
    if(status!=0)return status;
    if(input_stride<plan.source_width||input_stride>4096||cfa!=HB73_RGGB)return -2;
    const size_t input_sites=(size_t)plan.source_height*(size_t)input_stride;
    const size_t rgb_sites=(size_t)width*(size_t)height*3;
    if(input_sites>(size_t)INT32_MAX||rgb_sites>(size_t)INT32_MAX||
       (size_t)(*env)->GetArrayLength(env,input_array)<input_sites||
       (size_t)(*env)->GetArrayLength(env,output_array)<rgb_sites)return -1;
    jshort *input=(*env)->GetShortArrayElements(env,input_array,NULL);
    if(!input)return -3;
    jshort *output=(*env)->GetShortArrayElements(env,output_array,NULL);
    if(!output){(*env)->ReleaseShortArrayElements(env,input_array,input,JNI_ABORT);return -3;}
    HB73Settings settings={HB73_RGGB,0xffffu,1.0,32,200,0};
    status=hb74_render_final_bounded(&plan,&settings,(const uint16_t *)input,
        input_sites,input_stride,(uint16_t *)output,rgb_sites,NULL);
    (*env)->ReleaseShortArrayElements(env,input_array,input,JNI_ABORT);
    (*env)->ReleaseShortArrayElements(env,output_array,output,status==0?0:JNI_ABORT);
    return status;
}
