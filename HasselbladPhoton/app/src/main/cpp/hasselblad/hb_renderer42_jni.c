/* SPDX-License-Identifier: MIT */
#include <jni.h>
#include <stdlib.h>
#include <string.h>
#include "hb42_colour.h"

JNIEXPORT jshortArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladRenderer42_render(
        JNIEnv *e,jclass cls,jshortArray input,jdoubleArray parameters,
        jdoubleArray grid,jfloatArray curve,jint width,jint height,jint owner) {
    (void)cls;
    const char *error="Invalid Stage42 render input";
    uint16_t *src=NULL,*dst=NULL;double *g=NULL;float *f=NULL;
    jshortArray result=NULL;
    if(!input||!parameters||!grid||!curve)goto done;
    jsize n=(*e)->GetArrayLength(e,input);
    if(n<=0||n%3||n>1048576*3||width<2||width>256||height<2||height>256||
       (*e)->GetArrayLength(e,parameters)!=38||
       (*e)->GetArrayLength(e,grid)!=width*height*2||
       (*e)->GetArrayLength(e,curve)!=65536)goto done;
    src=malloc((size_t)n*2);dst=malloc((size_t)n*2);
    g=malloc((size_t)width*height*2*sizeof(double));f=malloc(65536*sizeof(float));
    if(!src||!dst||!g||!f){error="Stage42 allocation failed";goto done;}
    double v[38];
    (*e)->GetDoubleArrayRegion(e,parameters,0,38,v);
    (*e)->GetDoubleArrayRegion(e,grid,0,width*height*2,g);
    (*e)->GetFloatArrayRegion(e,curve,0,65536,f);
    (*e)->GetShortArrayRegion(e,input,0,n,(jshort*)src);
    if((*e)->ExceptionCheck(e))goto done;
    hb42_params p={0};
    memcpy(p.first,v,9*sizeof(double));memcpy(p.second,v+9,9*sizeof(double));
    memcpy(p.shadow,v+18,4*sizeof(double));memcpy(p.wb,v+22,3*sizeof(double));
    p.exposure=v[25];p.bias_x=v[26];p.bias_y=v[27];p.wb_owner=(uint32_t)owner;
    p.width=(uint32_t)width;p.height=(uint32_t)height;
    p.grid=g;p.grid_count=(size_t)width*height*2;p.curve=f;p.curve_count=65536;
    if(hb42_render(&p,src,(size_t)n/3,dst)!=HB42_OK)goto done;
    result=(*e)->NewShortArray(e,n);
    if(result)(*e)->SetShortArrayRegion(e,result,0,n,(jshort*)dst);
done:
    free(src);free(dst);free(g);free(f);
    if(!result&&!(*e)->ExceptionCheck(e)) {
        jclass type=(*e)->FindClass(e,"java/lang/IllegalArgumentException");
        if(type)(*e)->ThrowNew(e,type,error);
    }
    return result;
}
