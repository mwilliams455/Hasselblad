#include "finish88.h"
#include "post55.h"
#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

static pthread_once_t curve_once=PTHREAD_ONCE_INIT;
static uint16_t curve[65536];
static pthread_mutex_t decode_lock=PTHREAD_MUTEX_INITIALIZER;
static float cached_decode[65536];
static double cached_exponent;
static int decode_valid;
#ifdef HB88_TESTING
static unsigned long decode_build_count,curve_build_count;
#endif

static void prepare_curve(void) {
    /* Valid destination; the original builder cannot fail in this case. */
    (void)hb55_default_curve(curve);
#ifdef HB88_TESTING
    curve_build_count++;
#endif
}

int hb88_gradate(const uint16_t *input,size_t pixels,uint16_t *output) {
    if(!input||!output||pixels>SIZE_MAX/3)return -1;
    if(pthread_once(&curve_once,prepare_curve)!=0)return -2;
    return hb55_gradate(curve,input,pixels,output);
}

/* One cache entry bounds retained memory regardless of how many profiles exist.
 * Each caller owns its copy, so no lock is held during pixel processing. */
static int decode_copy(double exponent,float *destination) {
    if(pthread_mutex_lock(&decode_lock)!=0)return -2;
    if(!decode_valid||cached_exponent!=exponent) {
        for(size_t i=0;i<65536;i++)cached_decode[i]=(float)pow((double)((float)i/65535.f),exponent);
        cached_exponent=exponent;decode_valid=1;
#ifdef HB88_TESTING
        decode_build_count++;
#endif
    }
    memcpy(destination,cached_decode,sizeof(cached_decode));
    (void)pthread_mutex_unlock(&decode_lock);
    return 0;
}

int hb88_output_rgb16(const uint16_t *input,size_t pixels,const double matrix[9],
                     double exponent,uint16_t *output) {
    if(!input||!matrix||!output||pixels>SIZE_MAX/3||!isfinite(exponent)||exponent<=0||exponent>8)return -1;
    for(int i=0;i<9;i++)if(!isfinite(matrix[i])||fabs(matrix[i])>1e6)return -1;
    float *decode=malloc(65536*sizeof(float));if(!decode)return -2;
    int status=decode_copy(exponent,decode);
    if(status!=0){free(decode);return status;}
    /* Pixel arithmetic, operation order and casts are identical to Stage55. */
    for(size_t k=0;k<pixels;k++) {
        double rgb[3];for(size_t c=0;c<3;c++)rgb[c]=decode[input[3*k+c]];
        for(size_t c=0;c<3;c++) {
            float linear=(float)((rgb[0]*matrix[3*c]+rgb[1]*matrix[3*c+1])+rgb[2]*matrix[3*c+2]);
            float encoded=(float)(linear<=.0031308?(double)linear*12.92:
                                  1.055*pow((double)linear,1/2.4)-.055);
            float scaled=encoded*65535.f;
            output[3*k+c]=(uint16_t)fmin(65535,fmax(0,floor((double)scaled+.5)));
        }
    }
    free(decode);return 0;
}

#ifdef HB88_TESTING
unsigned long hb88_decode_builds(void) {
    unsigned long count;(void)pthread_mutex_lock(&decode_lock);count=decode_build_count;
    (void)pthread_mutex_unlock(&decode_lock);return count;
}
unsigned long hb88_curve_builds(void) {
    (void)pthread_once(&curve_once,prepare_curve);return curve_build_count;
}
#endif
