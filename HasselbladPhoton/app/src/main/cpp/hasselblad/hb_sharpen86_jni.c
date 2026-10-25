#include <jni.h>
#include <stdint.h>
#include <stdlib.h>
#include "sharpen85.h"
JNIEXPORT jshortArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladSharpen86_window(
        JNIEnv *e,jclass cls,jshortArray input,jint width,jint rows) {
    (void)cls;
    uint16_t *src=NULL,*dst=NULL;jshortArray result=NULL;
    const char *error="Invalid sharpening window";
    if(!input||width<1||width>8192||rows<1||rows>64)goto done;
    jsize n=width*(rows+2)*3;
    if((*e)->GetArrayLength(e,input)!=n)goto done;
    src=malloc((size_t)n*sizeof(*src));dst=malloc((size_t)n*sizeof(*dst));
    if(!src||!dst){error="Cannot allocate sharpening band";goto done;}
    (*e)->GetShortArrayRegion(e,input,0,n,(jshort*)src);
    if((*e)->ExceptionCheck(e))goto done;
    for(jsize i=0;i<n;++i)src[i]>>=2;
    if(hb85_sharpen14(src,dst,(size_t)width,(size_t)rows+2,100,1.0,0,10)!=0)goto done;
    jsize count=width*rows*3,offset=width*3;
    for(jsize i=0;i<count;++i)dst[offset+i]=(uint16_t)(dst[offset+i]<<2);
    result=(*e)->NewShortArray(e,count);
    if(result)(*e)->SetShortArrayRegion(e,result,0,count,(jshort*)(dst+offset));
done:
    free(src);free(dst);
    if(!result&&!(*e)->ExceptionCheck(e)){
        jclass type=(*e)->FindClass(e,"java/lang/IllegalArgumentException");
        if(type)(*e)->ThrowNew(e,type,error);
    }
    return result;
}
