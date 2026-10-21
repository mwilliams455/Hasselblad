/* SPDX-License-Identifier: MIT */
#include "hb_phone_temperature.h"
#include "../awb_original_runtime_20261021/hb_temperature.h"
#include "../awb_original_runtime_20261021/hb_user_controls.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* Public numerical data: Wyszecki & Stiles, Color Science, 2nd ed., p.228,
 * as published in Adobe DNG SDK 1.4 dng_temperature.cpp, AOSP blob
 * 47318abb306a231e04140ff57caee2d8a3b77b6c. Explicit SDK variant: u325=.24702.
 * No firmware/model payload supplies this table. See README provenance. */
static const float isotemperature[31][4] = {
    {0,.18006f,.26352f,-.24341f}, {10,.18066f,.26589f,-.25479f},
    {20,.18133f,.26846f,-.26876f}, {30,.18208f,.27119f,-.28539f},
    {40,.18293f,.27407f,-.30470f}, {50,.18388f,.27709f,-.32675f},
    {60,.18494f,.28021f,-.35156f}, {70,.18611f,.28342f,-.37915f},
    {80,.18740f,.28668f,-.40955f}, {90,.18880f,.28997f,-.44278f},
    {100,.19032f,.29326f,-.47888f}, {125,.19462f,.30141f,-.58204f},
    {150,.19962f,.30921f,-.70471f}, {175,.20525f,.31647f,-.84901f},
    {200,.21142f,.32312f,-1.0182f}, {225,.21807f,.32909f,-1.2168f},
    {250,.22511f,.33439f,-1.4512f}, {275,.23247f,.33904f,-1.7298f},
    {300,.24010f,.34308f,-2.0637f}, {325,.24702f,.34655f,-2.4681f},
    {350,.25591f,.34951f,-2.9641f}, {375,.26400f,.35200f,-3.5814f},
    {400,.27218f,.35407f,-4.3633f}, {425,.28039f,.35577f,-5.3762f},
    {450,.28863f,.35714f,-6.7262f}, {475,.29685f,.35823f,-8.5955f},
    {500,.30505f,.35907f,-11.324f}, {525,.31320f,.35968f,-15.628f},
    {550,.32129f,.36011f,-23.325f}, {575,.32931f,.36038f,-40.770f},
    {600,.33724f,.36051f,-116.45f}
};
static const hb_temperature_model model = { &isotemperature[0][0] };

struct hb_phone_temperature {
    /* Only the owned temperature leaves may see these ABI buffers. The zero
     * initialized marker deliberately remains zero. No scene tables exist. */
    unsigned char ctx[920560];
    unsigned char cfg[1502800];
};

static double det(const double m[9]) {
    return m[0]*(m[4]*m[8]-m[5]*m[7])
         - m[1]*(m[3]*m[8]-m[5]*m[6])
         + m[2]*(m[3]*m[7]-m[4]*m[6]);
}
static int finite_matrix(const float m[9]) {
    for (unsigned i=0;i<9;++i) if (!isfinite(m[i]) || fabsf(m[i])>16) return 0;
    return 1;
}
static double polynomial(const double p[4], double x) {
    return ((p[3]*x+p[2])*x+p[1])*x+p[0];
}
static int safe_segment(const float low[9], const float high[9]) {
    /* det(A+tB) is cubic. Check both endpoints AND all interior extrema;
     * endpoint-only or grid-only checks can miss a singular interpolation. */
    double a[9],b[9],p[4]={0,0,0,0};
    for (unsigned i=0;i<9;++i) { a[i]=low[i];b[i]=(double)high[i]-a[i]; }
    for (unsigned mask=0;mask<8;++mask) {
        double m[9]; unsigned degree=0;
        for (unsigned col=0;col<3;++col) {
            int use_b=(mask>>col)&1; degree+=(unsigned)use_b;
            for (unsigned row=0;row<3;++row) m[row*3+col]=use_b?b[row*3+col]:a[row*3+col];
        }
        p[degree]+=det(m);
    }
    /* Positive orientation and margin above the leaf's 1e-5 singular guard.
     * |coeff|<=16 is a deliberately bounded metadata capability, not a
     * universal acceptance test for every camera profile. */
    if (!(polynomial(p,0)>1e-4) || !(polynomial(p,1)>1e-4)) return 0;
    double roots[2]; unsigned n=0;
    double aa=3*p[3],bb=2*p[2],cc=p[1];
    if (aa==0) { if (bb!=0) roots[n++]=-cc/bb; }
    else {
        double disc=bb*bb-4*aa*cc;
        if (disc>=0) {
            double q=-0.5*(bb+copysign(sqrt(disc),bb));
            if (q==0) roots[n++]=-bb/(2*aa);
            else { roots[n++]=q/aa; roots[n++]=cc/q; }
        }
    }
    for (unsigned i=0;i<n;++i)
        if (roots[i]>0 && roots[i]<1 && !(polynomial(p,roots[i])>1e-4)) return 0;
    return 1;
}
int hb_phone_temperature_create(const hb_phone_temperature_input *in, hb_phone_temperature **out) {
    if (!in || !out) return HB_PHONE_TEMP_ARGUMENT;
    unsigned order[2]={0,1};
    if (in->anchor[0].kelvin>in->anchor[1].kelvin) { order[0]=1;order[1]=0; }
    if (in->anchor[order[0]].kelvin<1667 || in->anchor[order[1]].kelvin>100000 ||
        in->anchor[0].kelvin==in->anchor[1].kelvin) return HB_PHONE_TEMP_RANGE;
    float product[2][9];
    for (unsigned k=0;k<2;++k) {
        const hb_phone_temperature_anchor *a=&in->anchor[order[k]];
        if (!finite_matrix(a->color) || !finite_matrix(a->calibration)) return HB_PHONE_TEMP_MATRIX;
        for (unsigned r=0;r<3;++r) for (unsigned c=0;c<3;++c) {
            float v=a->calibration[3*r]*a->color[c];
            float q=a->calibration[3*r+1]*a->color[3+c]; v=v+q;
            q=a->calibration[3*r+2]*a->color[6+c]; product[k][3*r+c]=v+q;
        }
        if (!finite_matrix(product[k])) return HB_PHONE_TEMP_MATRIX;
    }
    if (!safe_segment(product[0],product[1])) return HB_PHONE_TEMP_MATRIX;
    hb_phone_temperature *w=calloc(1,sizeof(*w));
    if (!w) return HB_PHONE_TEMP_MEMORY;
    w->cfg[0x1332bc]=2;
    for (unsigned k=0;k<2;++k) {
        unsigned char *row=w->cfg+0x1332c0+40*k;
        memcpy(row,&in->anchor[order[k]].kelvin,4);memcpy(row+4,product[k],36);
    }
    *out=w; return HB_PHONE_TEMP_OK;
}
void hb_phone_temperature_destroy(hb_phone_temperature *w) { free(w); }
int hb_phone_temperature_matrix(const hb_phone_temperature *w, float kelvin, float out[9]) {
    if (!w || !out) return HB_PHONE_TEMP_ARGUMENT;
    if (!isfinite(kelvin) || kelvin<1667 || kelvin>100000) return HB_PHONE_TEMP_RANGE;
    float temp[9];
    if (hb_temperature_matrix(w->cfg,0,0,kelvin,temp)) return HB_PHONE_TEMP_NATIVE;
    memcpy(out,temp,sizeof(temp)); return HB_PHONE_TEMP_OK;
}
int hb_phone_temperature_to_gain(const hb_phone_temperature *w, uint32_t kelvin,
                                  float tint, hb_phone_temperature_gains *out) {
    if (!w || !out) return HB_PHONE_TEMP_ARGUMENT;
    if (kelvin<1667 || kelvin>100000 || !isfinite(tint) || fabsf(tint)>150) return HB_PHONE_TEMP_RANGE;
    hb_phone_temperature_gains temp;
    if (hb_user_ct_tint_to_gain(w->ctx,w->cfg,&model,kelvin,tint,4096,
            temp.gain_q12,temp.gain_q12+1,temp.gain_q12+2)) return HB_PHONE_TEMP_NATIVE;
    for (unsigned i=0;i<3;++i)
        if (temp.gain_q12[i]<4096 || temp.gain_q12[i]>=40960) return HB_PHONE_TEMP_CLIPPED;
    *out=temp; return HB_PHONE_TEMP_OK;
}
int hb_phone_temperature_from_gain(const hb_phone_temperature *w, const uint32_t gain[3],
                                    hb_phone_temperature_estimate *out) {
    if (!w || !gain || !out) return HB_PHONE_TEMP_ARGUMENT;
    uint32_t low=gain[0],high=gain[0];
    for (unsigned i=0;i<3;++i) {
        if (!gain[i] || gain[i]>65535) return HB_PHONE_TEMP_RANGE;
        if (gain[i]<low) low=gain[i];
        if (gain[i]>high) high=gain[i];
    }
    if ((double)high/(double)low>=10) return HB_PHONE_TEMP_CLIPPED;
    hb_phone_temperature_estimate temp={0,0,0};
    if (hb_temperature_calibrated(w->ctx,w->cfg,&model,gain[0],gain[1],gain[2],
                                  &temp.kelvin,&temp.tint)) return HB_PHONE_TEMP_NATIVE;
    if (!isfinite(temp.kelvin) || temp.kelvin<1667 || temp.kelvin>100000 ||
        !isfinite(temp.tint) || fabsf(temp.tint)>150) return HB_PHONE_TEMP_RANGE;
    hb_phone_temperature_gains rebuilt;
    int st=hb_phone_temperature_to_gain(w,(uint32_t)floorf(temp.kelvin+0.5f),temp.tint,&rebuilt);
    if (st) return st;
    for (unsigned i=0;i<3;++i) {
        double expected=(double)gain[i]/gain[1];
        double actual=(double)rebuilt.gain_q12[i]/rebuilt.gain_q12[1];
        float error=(float)fabs(actual/expected-1);
        if (error>temp.ratio_residual) temp.ratio_residual=error;
    }
    if (temp.ratio_residual>0.003f) return HB_PHONE_TEMP_RESIDUAL;
    *out=temp;return HB_PHONE_TEMP_OK;
}
