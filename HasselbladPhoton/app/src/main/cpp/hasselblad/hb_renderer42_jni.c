/* SPDX-License-Identifier: MIT */
#include <jni.h>
#include <stdlib.h>
#include <string.h>
#include "hb42_colour.h"
#include "highlight53.h"

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

#include "hb_dng_pcs_bridge.h"
#include "hb_colour_stage19.h"
static int read_matrix(JNIEnv *e,jdoubleArray a,double *out,jsize size,int optional) {
    if(!a)return optional;
    if((*e)->GetArrayLength(e,a)!=size)return 0;
    (*e)->GetDoubleArrayRegion(e,a,0,size,out);
    return !(*e)->ExceptionCheck(e);
}
static jdoubleArray matrix_result(JNIEnv *e,int ok,const double m[9]) {
    if(!ok) {
        if(!(*e)->ExceptionCheck(e)) {
            jclass type=(*e)->FindClass(e,"java/lang/IllegalArgumentException");
            if(type)(*e)->ThrowNew(e,type,"Unsupported or invalid DNG colour calibration");
        }
        return NULL;
    }
    jdoubleArray result=(*e)->NewDoubleArray(e,9);
    if(result)(*e)->SetDoubleArrayRegion(e,result,0,9,m);
    return result;
}
JNIEXPORT jdoubleArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladRenderer42_cameraToD50(
        JNIEnv *e,jclass cls,jdoubleArray fm1,jdoubleArray fm2,jdoubleArray cc1,
        jdoubleArray cc2,jdoubleArray analog,jdoubleArray neutral) {
    (void)cls;
    double f1[9],f2[9],c1[9],c2[9],ab[3]={1,1,1},n[3],out[9];
    int ok=read_matrix(e,fm1,f1,9,0)&&read_matrix(e,fm2,f2,9,1)&&
        read_matrix(e,cc1,c1,9,1)&&read_matrix(e,cc2,c2,9,1)&&
        read_matrix(e,analog,ab,3,1)&&read_matrix(e,neutral,n,3,0);
    hb_dng_pcs_receipt receipt;
    if(ok)ok=hb_dng_pcs_build(f1,fm2?f2:NULL,cc1?c1:NULL,cc2?c2:NULL,ab,n,out,&receipt)==HB_DNG_PCS_OK;
    return matrix_result(e,ok,out);
}
JNIEXPORT jdoubleArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladRenderer42_xyzToSrgb(JNIEnv *e,jclass cls) {
    (void)cls;double out[9];hb19_output_receipt receipt;
    return matrix_result(e,hb19_build_output_matrix(HB19_SRGB,out,&receipt)==HB19_OK,out);
}

JNIEXPORT jshortArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladRenderer42_reconstructHighlights(
        JNIEnv *e,jclass cls,jshortArray input,jdoubleArray ratios,jboolean allow_limit) {
    (void)cls;
    const char *error="Invalid prepared-RGB highlight input";
    uint16_t *src=NULL,*dst=NULL;
    jshortArray result=NULL;
    if(!input||!ratios||(*e)->GetArrayLength(e,ratios)!=3)goto done;
    jsize n=(*e)->GetArrayLength(e,input);
    if(n<=0||n%3||n>1048576*3)goto done;
    double gains[3];const uint16_t limits[3]={65535,65535,65535};
    (*e)->GetDoubleArrayRegion(e,ratios,0,3,gains);
    if((*e)->ExceptionCheck(e))goto done;
    hb_highlight53 p;
    int status=hb_highlight53_prepare(&p,gains,limits,allow_limit==JNI_TRUE);
    if(status<0) {
        error=status==-2?"Equal lower gains require the explicit analytic limit":
            "Invalid or numerically degenerate highlight gains";
        goto done;
    }
    src=malloc((size_t)n*sizeof(uint16_t));dst=malloc((size_t)n*sizeof(uint16_t));
    if(!src||!dst){error="Highlight preview allocation failed";goto done;}
    (*e)->GetShortArrayRegion(e,input,0,n,(jshort*)src);
    if((*e)->ExceptionCheck(e))goto done;
    if(hb_highlight53_rgb16(&p,src,dst,(size_t)n/3)!=0)goto done;
    result=(*e)->NewShortArray(e,n);
    if(result)(*e)->SetShortArrayRegion(e,result,0,n,(jshort*)dst);
done:
    free(src);free(dst);
    if(!result&&!(*e)->ExceptionCheck(e)) {
        jclass type=(*e)->FindClass(e,"java/lang/IllegalArgumentException");
        if(type)(*e)->ThrowNew(e,type,error);
    }
    return result;
}
