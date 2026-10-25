#include "noise65.h"
#include "../phocus_colour_stage64/ycc64.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define H 40
#define S 48
#define N (H*S)
static uint16_t r[N],g[N],b[N],y[N],mask[N],sy[N],oy[N];
static int16_t a[N],bb[N],ma[N],mb[N],oa[N],ob[N],aux[N];

static void fill_arrays(uint16_t v) {
    for(int i=0;i<N;++i) {
        r[i]=v;g[i]=v;b[i]=v;
        y[i]=1234; a[i]=123;bb[i]=321;
        mask[i]=0;sy[i]=1717;ma[i]=1727;mb[i]=1737;
        oy[i]=1818;oa[i]=1919;ob[i]=2020;aux[i]=2121;
    }
}
static HBNoiseContext65 context(int width,int height,int strength,uint16_t flags) {
    return (HBNoiseContext65){.width=width,.height=height,.stride=S,
     .flags=flags,.optimized_view=0,.strength=strength,.red=r,.green=g,.blue=b,
     .y=y,.c1=a,.c2=bb,.direction_mask=mask,.smooth_y=sy,.median_c1=ma,
     .median_c2=mb,.out_y=oy,.out_c1=oa,.out_c2=ob,.out_aux=aux};
}
int main(void) {
    HBNoiseCounters65 count;
    fill_arrays(10000);
    HBNoiseContext65 c=context(40,H,0,0x20);
    assert(hb_color_noise65(&c,&count)==0);
    assert(count.converted_sites==24*24 && count.clamped_sites==24*24);
    for(int yy=8;yy<H-8;++yy) for(int xx=8;xx<40-8;++xx){
        int p=yy*S+xx;
        assert(y[p]==10000 && a[p]==0 && bb[p]==0);
    }
    assert(y[0]==1234 && a[0]==123 && bb[0]==321);
    fill_arrays(0);
    c=context(40,H,0,0x20);
    r[19*S+21]=65535;
    assert(hb_color_noise65(&c,&count)==0);
    assert(y[19*S+21]<=16383);
    assert(a[19*S+21]==32767 && bb[19*S+21]==0);
    /* No inadvertent writes in an insufficient-width native path. */
    fill_arrays(5000); c=context(16,H,0,0x20);
    assert(hb_color_noise65(&c,&count)==0);
    assert(count.converted_sites==0 && y[8*S+8]==1234);
    /* Native CPU conversion uses x=8 at 17x17, but the following clamp
     * touches x=0, not x=8. This is a direct Stage70 CPU discrimination. */
    fill_arrays(0); c=context(17,17,0,0x20);
    for(int j=0;j<N;++j) { r[j]=65535; g[j]=b[j]=0; y[j]=65535; }
    assert(hb_color_noise65(&c,&count)==0);
    assert(y[8*S+8]==16383 && y[8*S]==65535);
    /* Verify directional helper's fourth output belongs in the auxiliary
     * plane, not the second chroma plane. These outputs must differ. */
    fill_arrays(0); c=context(40,H,0,0x40);
    for(int j=0;j<N;++j) {
        y[j]=(uint16_t)(10000+(j*113)%17000);
        a[j]=(int16_t)(-7000+(j*71)%12000);
        bb[j]=(int16_t)(-3000+(j*53)%9000);
    }
    mask[12*S+12]=0x8ff;
    assert(hb_color_noise_rows65(&c,&count)==0);
    int q=12*S+12;uint16_t predicted_y=0;
    int16_t predicted_c1=0,predicted_c2=0,predicted_aux=0;
    assert(hb_directional_ycc64(mask[q],y+q,a+q,bb+q,
        sy+q,ma+q,mb+q,&predicted_y,&predicted_c1,
        &predicted_c2,&predicted_aux,S)==0);
    assert(predicted_c2!=predicted_aux);
    assert(hb_color_noise_correct65(&c,&count)==0);
    assert(aux[q]==predicted_aux && oy[q]==predicted_y);
    /* Stage61 row median semantics and zero borders retained. */
    fill_arrays(10000); c=context(40,H,0,0x40);
    assert(hb_color_noise65(&c,&count)==0);
    assert(count.smoothing_rows==H-2 && count.median_rows==(H-2)*2);
    assert(count.correction_sites==16*16 && count.nonzero_mask_sites==0);
    assert(oy[12*S+12]==1234 && aux[12*S+12]==0);
    assert(oa[12*S+12]==123 && ob[12*S+12]==321);
    assert(sy[S]==0 && ma[S]==123 && mb[S]==321);
    /* Positive-strength flag6 branch unsupported; no buffer mutations. */
    fill_arrays(10000); c=context(40,H,1,0x60);
    assert(hb_color_noise65(&c,&count)==-2);
    assert(y[19*S+21]==1234 && oa[19*S+21]==1919);
    /* Directional YCC path executes with nonzero mask. */
    fill_arrays(10000); c=context(40,H,0,0x60);
    mask[12*S+12]=0x8ff;
    assert(hb_color_noise65(&c,&count)==0);
    assert(count.nonzero_mask_sites==1);
    assert(count.correction_sites==16*16);
    assert(oy[12*S+12]==10000);
    puts("STAGE65_BOUNDED_COLOR_NOISE_C11_PASS");
    return 0;
}
