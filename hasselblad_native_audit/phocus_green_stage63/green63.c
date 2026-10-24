#include "green63.h"
#include <math.h>
#include <stddef.h>

static int32_t s32(uint32_t u) {
    return u <= INT32_MAX ? (int32_t)u : -1-(int32_t)(UINT32_MAX-u);
}
static int32_t s16(uint32_t u) {
    u &= UINT32_C(65535);
    return u < UINT32_C(32768) ? (int32_t)u : (int32_t)u-65536;
}
static int32_t max32(int32_t a, int32_t b) { return a > b ? a : b; }
static int32_t min32(int32_t a, int32_t b) { return a < b ? a : b; }
static uint32_t distance(uint32_t a, uint32_t b) { return a > b ? a-b : b-a; }

/* AArch64 signed float-to-int conversion saturates rather than invoking the
 * undefined C conversion outside the signed range. Our scale contract excludes
 * NaNs, but arithmetic overflow can still produce positive infinity.
 */
static int32_t trunc_sat(float value) {
    if (isnan(value)) return 0;
    if (value >= 2147483648.0f) return INT32_MAX;
    if (value <= -2147483648.0f) return INT32_MIN;
    return (int32_t)value;
}

static float bounded_scale(float value, float a, float b) {
    float high = a > b ? a : b;
    float low = a < b ? a : b;
    high = high < 1.0f ? 1.0f : high;
    low = low > 1.0f ? 1.0f : low;
    value = value > low ? value : low;
    return value < high ? value : high;
}

void hb_green_at_colour63(const uint16_t *raw, const float *horizontal,
    const float *vertical, const float *scale, int stride,
    const int16_t first[8], const int16_t second[8],
    int16_t first_floor, int16_t second_floor,
    int32_t *green, int32_t *mask, int16_t *maximum_gradient) {
    const ptrdiff_t s = stride;
    int32_t amin=first[0], amax=first[0], bmin=second[0], bmax=second[0];
    unsigned minimum_first_seven=0;
    for (unsigned i=1; i<8; ++i) {
        if (i<7 && first[i]<first[minimum_first_seven]) minimum_first_seven=i;
        amin=min32(amin,first[i]); amax=max32(amax,first[i]);
        bmin=min32(bmin,second[i]); bmax=max32(bmax,second[i]);
    }
    *maximum_gradient=(int16_t)max32(amax,bmax);
    int32_t half_min=amin>=0 ? amin/2 : -((-amin+1)/2);
    int32_t range=s16(((uint32_t)amax>>1)-(uint32_t)half_min);
    uint32_t threshold=((uint32_t)amin&UINT32_C(65534))+(uint32_t)half_min
        -((uint32_t)range>>4)+((uint32_t)range>>2)+8;
    int32_t ta=max32(s16(threshold),first_floor);
    int32_t tb=max32(s16(((uint32_t)bmin&UINT32_C(65534))+((uint32_t)bmax>>1)+8),second_floor);

    const uint32_t nw=raw[-s-1], ne=raw[-s+1], sw=raw[s-1], se=raw[s+1];
    float center=scale[0];
    float main=bounded_scale(center,scale[-2*s-2],scale[2*s+2]);
    float cross=bounded_scale(center,scale[-2*s+2],scale[2*s-2]);
    uint32_t mean_cross=(sw+ne)/2, mean_main=(se+nw)/2;
    uint32_t cross_delta=distance(se,mean_cross)<distance(nw,mean_cross)
        ? distance(se,mean_cross):distance(nw,mean_cross);
    uint32_t main_delta=distance(ne,mean_main)<distance(sw,mean_main)
        ? distance(ne,mean_main):distance(sw,mean_main);
    if ((sw+ne)/8>cross_delta) main=center;
    if ((se+nw)/8>main_delta) cross=center;
    const float sample=(float)raw[0];
    main=main*sample; cross=cross*sample;
    int32_t candidates[8]={
        trunc_sat(vertical[-s]*sample), trunc_sat(horizontal[1]*sample),
        trunc_sat(vertical[s]*sample), trunc_sat(horizontal[-1]*sample),
        trunc_sat(fmaf((float)ne,bounded_scale(scale[-s+1],scale[s+1],scale[-s-1]),main)*0.5f),
        trunc_sat(fmaf((float)se,bounded_scale(scale[s+1],scale[-s+1],scale[s-1]),cross)*0.5f),
        trunc_sat(fmaf((float)sw,bounded_scale(scale[s-1],scale[s+1],scale[-s-1]),main)*0.5f),
        trunc_sat(fmaf((float)nw,bounded_scale(scale[-s-1],scale[-s+1],scale[s-1]),cross)*0.5f)
    };
    unsigned selected[8], count=0, cardinal_count=0;
    int32_t low=65535, high=0, selected_max_gradient=0;
    for (unsigned i=0; i<8; ++i) {
        selected[i]=(first[i]<ta && second[i]<tb);
        if (selected[i]) {
            ++count;
            if (i<4) ++cardinal_count;
            low=min32(low,candidates[i]); high=max32(high,candidates[i]);
            selected_max_gradient=max32(selected_max_gradient,first[i]);
        }
    }

    int use_nearest=0;
    if (first[7]>=first[minimum_first_seven] && minimum_first_seven<4 &&
        count>=3 && count<=5 && selected_max_gradient<amin*2 && cardinal_count==4) {
        uint32_t total=0;
        for (unsigned i=0; i<4; ++i) total+=(uint32_t)candidates[i];
        int32_t mean=s32(total)/4;
        uint32_t vertical_product=((uint32_t)mean-(uint32_t)candidates[0])
            *((uint32_t)mean-(uint32_t)candidates[2]);
        uint32_t horizontal_product=((uint32_t)mean-(uint32_t)candidates[1])
            *((uint32_t)mean-(uint32_t)candidates[3]);
        if (s32(vertical_product)>=0 && s32(horizontal_product)>=0) {
            int32_t sum=s32((uint32_t)low+(uint32_t)high);
            int32_t spread=s32((uint32_t)high-(uint32_t)low);
            use_nearest=(double)sum*0.25650557620817854 < (double)spread;
        }
    }
    int32_t value=0;
    int average=1;
    if (use_nearest) {
        uint32_t closest=65535;
        unsigned direction=0;
        for (unsigned i=0; i<4; ++i) {
            uint32_t delta=distance((uint32_t)candidates[i],raw[0]);
            if (delta<closest) { closest=delta; direction=i; }
        }
        value=candidates[direction];
        if (closest!=0) {
            for (unsigned i=0; i<8; ++i) selected[i]=(i==direction);
        }
        /* The original sentinel case averages the singleton using the prior
         * selected count, then emits a singleton mask. Preserve that order. */
        average=(closest==65535);
    }
    if (average) {
        if (!count) {
            value=(int32_t)(((uint32_t)raw[-s]+raw[s]+raw[-1]+raw[1])/4);
        } else {
            uint32_t total=0;
            for (unsigned i=0; i<8; ++i) if (selected[i]) total+=(uint32_t)candidates[i];
            value=max32(s32(total)/(int32_t)count,0);
        }
    }
    *green=min32(value,65534);
    unsigned bits=0;
    count=0;
    for (unsigned i=0; i<8; ++i) if (selected[i]) { bits|=1u<<i; ++count; }
    *mask=count ? (int32_t)(bits|(count<<8)) : 0x8ff;
}
