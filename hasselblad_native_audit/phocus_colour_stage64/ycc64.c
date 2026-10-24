/* Native-instruction-derived *candidate* standalone directional YCC function.
 * No vendor executable bytes, private profile, DNG pixels or scene fitting.
 * Original CPU instruction parity and connected demosaic tests pending.
 */
#include "ycc64.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static int32_t s32(uint32_t x){int32_t y;memcpy(&y,&x,4);return y;}
static int16_t s16(uint16_t x){int16_t y;memcpy(&y,&x,2);return y;}
static uint16_t low16(uint32_t x){return (uint16_t)x;}
static uint32_t diff(unsigned a,unsigned b){return a>b ? a-b:b-a;}
static uint32_t sdifference(int a,int b){return (uint32_t)(a>b?a-b:b-a);}
static int32_t divide_signed(int32_t a,int32_t b){
    /* AArch64 SDIV defines zero-divisor output as zero. The native mask is
     * allowed to have an independently encoded zero selection count. */
    if (!b)return 0;
    if (a==INT32_MIN&&b==-1)return INT32_MIN;
    return a/b;
}
static int32_t asr14(uint32_t u){
    int32_t v=s32(u);
    /* Explicit arithmetic-right-shift / floor division for negative values. */
    return v>=0 ? v/16384 : -(int32_t)(((int64_t)-v+16383)/16384);
}
static uint32_t denom6(uint32_t x){
    /* Original ARM64 uses unsigned reciprocal multiplication, not floating
     * division. Within the supported three-component diff range, this
     * agrees with exact integer division by six. */
    return (uint32_t)(((uint64_t)x*UINT64_C(0xaaaaaaab))>>34);
}
static uint32_t selected(uint32_t mask,unsigned bit){return (mask>>bit)&1u;}
static uint32_t product32(int32_t a,int32_t b){
    return (uint32_t)((uint64_t)(uint32_t)a*(uint64_t)(uint32_t)b);
}
static uint32_t weighted2(int32_t a,int32_t b,int32_t wa,int32_t wb){
    return product32(a,wa)+product32(b,wb); /* intentional W32 wrapping */
}
static void pair_values(uint16_t centre_y,int16_t centre_a,int16_t centre_b,
                        uint16_t yl,uint16_t yr,int16_t al,int16_t ar,
                        int16_t bl,int16_t br,
                        uint32_t *factor_out,int32_t *a_out,int32_t *b_out){
    const uint32_t left_distance=diff(centre_y,yl)+sdifference(centre_a,al)+sdifference(centre_b,bl);
    const uint32_t right_distance=diff(centre_y,yr)+sdifference(centre_a,ar)+sdifference(centre_b,br);
    const uint32_t gl=denom6(left_distance),gr=denom6(right_distance);
    const uint32_t gsum=gl+gr;
    uint32_t y;
    int32_t a,b;
    if (!gsum) {
        y=(uint32_t)(yl+yr)>>1;
        /* Signed average rounded toward zero, not negative arithmetic >>1. */
        a=divide_signed((int32_t)al+(int32_t)ar,2);
        b=divide_signed((int32_t)bl+(int32_t)br,2);
    } else {
        y=weighted2(yl,yr,(int32_t)gr,(int32_t)gl)/gsum;
        a=divide_signed(s32(weighted2(al,ar,(int32_t)gr,(int32_t)gl)),(int32_t)gsum);
        b=divide_signed(s32(weighted2(bl,br,(int32_t)gr,(int32_t)gl)),(int32_t)gsum);
    }
    const uint32_t delta=diff(centre_y,y);
    const uint32_t divisor=(uint32_t)centre_y+y;
    uint32_t factor=divisor? (delta<<15)/divisor:0;
    if(factor>16384)factor=16384;
    const int32_t other=16384-(int32_t)factor;
    *factor_out=factor;
    *a_out=asr14(weighted2(a,centre_a,(int32_t)factor,other));
    *b_out=asr14(weighted2(b,centre_b,(int32_t)factor,other));
}

int hb_directional_ycc64(uint32_t mask,
                         const uint16_t *centre_y,
                         const int16_t *centre_c1, const int16_t *centre_c2,
                         const uint16_t *y,
                         const int16_t *a, const int16_t *b,
                         uint16_t *out_y,int16_t *out_c1,int16_t *out_c2,
                         int16_t *out_level,int stride){
    if(!centre_y||!centre_c1||!centre_c2||!y||!a||!b||
       !out_y||!out_c1||!out_c2||!out_level||stride<3)return -1;
    const uint16_t y0=*centre_y;
    const int16_t a0=*centre_c1,b0=*centre_c2;
    *out_y=y0; *out_c1=a0; *out_c2=b0; *out_level=0;
    if(!y0)return 0;
    const ptrdiff_t off[4]={1,stride,stride-1,stride+1};
    uint32_t factors[4];int32_t apos[4],bpos[4];
    for(unsigned i=0;i<4;++i){
        const ptrdiff_t o=off[i];
        pair_values(y0,a0,b0,y[-o],y[o],a[-o],a[o],b[-o],b[o],
                    &factors[i],&apos[i],&bpos[i]);
    }
    static const unsigned selected_pairs[4][2]={{0,2},{1,3},{5,7},{4,6}};
    uint32_t sums[3]={0,0,0};
    for(unsigned i=0;i<4;++i){
        for(unsigned j=0;j<2;++j){
            if(selected(mask,selected_pairs[i][j])){
                sums[0]+=factors[i];
                sums[1]+=(uint32_t)apos[i];
                sums[2]+=(uint32_t)bpos[i];
            }
        }
    }
    const int32_t count=(int32_t)((mask>>8)&15);
    const int32_t weight_mean=divide_signed(s32(sums[0]),count);
    const int32_t a_mean=divide_signed(s32(sums[1]),count);
    const int32_t b_mean=divide_signed(s32(sums[2]),count);
    uint32_t minfactor=factors[0];
    for(unsigned i=1;i<4;++i)if(factors[i]<minfactor)minfactor=factors[i];
    const uint32_t correction=(uint32_t)((minfactor*(uint32_t)y0)>>14);
    const int32_t attenuation=16384-(int32_t)correction;
    const uint32_t adj=attenuation<0?0u:attenuation>16384?16384u:(uint32_t)attenuation;
    const uint32_t a_result=(product32((int32_t)adj,a_mean)>>14);
    const uint32_t b_result=(product32((int32_t)adj,b_mean)>>14);
    *out_level=s16(low16((uint32_t)weight_mean));
    *out_c1=s16(low16(a_result));
    *out_c2=s16(low16(b_result));
    return 0;
}
