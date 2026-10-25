#include <jni.h>
#include <stdlib.h>
#include "frame76.h"
JNIEXPORT jint JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladFrame76_renderBandNative(
        JNIEnv *e,jclass cls,jshortArray input,jint width,jint row_offset,jint rows,jshortArray output) {
    (void)cls;
    if(!input||!output||(*e)->IsSameObject(e,input,output)||width<128||width>8192||
       row_offset<0||row_offset>63||rows<1||rows>64-row_offset)return -1;
    const size_t source=(size_t)width*128,n=(size_t)((width-64)&~1)*rows*3;
    if((size_t)(*e)->GetArrayLength(e,input)!=source||
       (size_t)(*e)->GetArrayLength(e,output)!=n)return -1;
    uint16_t *src=malloc(source*2),*dst=malloc(n*2);
    if(!src||!dst){free(src);free(dst);return -3;}
    (*e)->GetShortArrayRegion(e,input,0,(jsize)source,(jshort*)src);
    int status=-1;
    if(!(*e)->ExceptionCheck(e)) {
        status=hb76_render_band(src,source,width,row_offset,rows,dst,n);
        if(status==0)(*e)->SetShortArrayRegion(e,output,0,(jsize)n,(const jshort*)dst);
    }
    free(src);free(dst);return status;
}
