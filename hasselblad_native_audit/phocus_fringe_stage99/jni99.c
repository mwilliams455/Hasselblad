#include <jni.h>
#include <stdlib.h>
#include "chroma99.h"
JNIEXPORT jint JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladFrame99_filterNative(
    JNIEnv *e,jclass cls,jshortArray input,jbyteArray flags,jint width,jint height,jshortArray output,jdouble nr,jdouble nb){
    (void)cls;
    if(!input||!flags||!output||(*e)->IsSameObject(e,input,output)||width<31||height<31||width>8222||height>8222)return -1;
    size_t sites=(size_t)width*height,n=sites*3,need=(size_t)(width-30)*(height-30)*3;
    if((size_t)(*e)->GetArrayLength(e,input)!=n||(size_t)(*e)->GetArrayLength(e,flags)!=sites||(size_t)(*e)->GetArrayLength(e,output)!=need)return -1;
    uint16_t *src=malloc(n*2),*dst=malloc(need*2);uint8_t *mask=malloc(sites);
    if(!src||!dst||!mask){free(src);free(dst);free(mask);return -3;}
    (*e)->GetShortArrayRegion(e,input,0,(jsize)n,(jshort*)src);
    (*e)->GetByteArrayRegion(e,flags,0,(jsize)sites,(jbyte*)mask);
    int status=-1;
    if(!(*e)->ExceptionCheck(e)){
        status=hb99_chroma_roi(src,n,mask,sites,width,height,nr,nb,dst,need);
        if(!status)(*e)->SetShortArrayRegion(e,output,0,(jsize)need,(const jshort*)dst);
    }
    free(src);free(dst);free(mask);return status;
}
