/* SPDX-License-Identifier: MIT
 * Bounded mathematical reconstruction of Adobe DNG forward-matrix branch.
 * DNG SDK: dng_camera_profile::NormalizeForwardMatrix and
 * dng_color_spec::SetWhiteXY, plus camera-neutral derivation.
 * Not an exact SDK replay of NeutralToXY or dual-illuminant interpolation.
 */
#include "hb_dng_pcs_bridge.h"
#include <math.h>
#include <stdint.h>
#include <string.h>
static int finite_n(const double *p,size_t n) {
    if (!p) return 0;
    for (size_t i=0;i<n;++i) if (!isfinite(p[i])) return 0;
    return 1;
}
static int overlap(const void *a,size_t an,const void *b,size_t bn) {
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=y ? y-x<an : x-y<bn;
}
static int inverse3(const double a[9], double m[9]) {
    double c[9]={
       a[4]*a[8]-a[5]*a[7], a[2]*a[7]-a[1]*a[8], a[1]*a[5]-a[2]*a[4],
       a[5]*a[6]-a[3]*a[8], a[0]*a[8]-a[2]*a[6], a[2]*a[3]-a[0]*a[5],
       a[3]*a[7]-a[4]*a[6], a[1]*a[6]-a[0]*a[7], a[0]*a[4]-a[1]*a[3]};
    double det=a[0]*c[0]+a[1]*c[3]+a[2]*c[6];
    if (!isfinite(det) || fabs(det)<1e-10) return 0;
    for (unsigned i=0;i<9;i++){m[i]=c[i]/det;if(!isfinite(m[i]))return 0;}
    return 1;
}
static void mat_vec(const double a[9],const double x[3],double y[3]) {
    for(unsigned i=0;i<3;++i)
        y[i]=a[3*i]*x[0]+a[3*i+1]*x[1]+a[3*i+2]*x[2];
}
int hb_dng_pcs_build(const double fm1[9],const double fm2[9],
                     const double cc1[9],const double cc2[9],
                     const double ab[3],const double neutral[3],
                     double out[9],hb_dng_pcs_receipt *receipt) {
    static const double D50[3]={0.9642,1.0,0.8249};
    if(!fm1||!ab||!neutral||!out||!receipt ||
       !finite_n(fm1,9)||!finite_n(ab,3)||!finite_n(neutral,3)||
       (fm2&&!finite_n(fm2,9))||(cc1&&!finite_n(cc1,9))||(cc2&&!finite_n(cc2,9)))
        return HB_DNG_PCS_INVALID;
    if((fm2 && memcmp(fm1,fm2,9*sizeof(double))!=0) ||
       (cc1 && cc2 && memcmp(cc1,cc2,9*sizeof(double))!=0) ||
       (!cc1 && cc2)) return HB_DNG_PCS_UNSUPPORTED_INTERPOLATION;
    double maxneutral=fmax(neutral[0],fmax(neutral[1],neutral[2]));
    if (!(maxneutral>0.0) || !isfinite(maxneutral)) return HB_DNG_PCS_INVALID;
    for(unsigned i=0;i<3;i++)if(!(ab[i]>0.0)||!(neutral[i]>0.0))return HB_DNG_PCS_INVALID;
    /* Original DNG SDK normalizes ForwardMatrix so F*[1,1,1]=PCS D50. */
    double fm[9];
    for(unsigned row=0;row<3;row++){
        double sum=fm1[3*row]+fm1[3*row+1]+fm1[3*row+2];
        if(!isfinite(sum)||fabs(sum)<1e-12)return HB_DNG_PCS_SINGULAR;
        for(unsigned col=0;col<3;col++)fm[3*row+col]=fm1[3*row+col]*D50[row]/sum;
    }
    const double id[9]={1,0,0,0,1,0,0,0,1};
    const double *cc=cc1?cc1:id;
    double abcc[9];
    for(unsigned row=0;row<3;row++)for(unsigned col=0;col<3;col++)
        abcc[3*row+col]=ab[row]*cc[3*row+col];
    double inv_abcc[9];if(!inverse3(abcc,inv_abcc))return HB_DNG_PCS_SINGULAR;
    double white[3]={neutral[0]/maxneutral,neutral[1]/maxneutral,neutral[2]/maxneutral};
    double refwhite[3];mat_vec(inv_abcc,white,refwhite);
    for(unsigned i=0;i<3;i++)if(!(refwhite[i]>1e-12)||!isfinite(refwhite[i]))return HB_DNG_PCS_INVALID;
    /* CameraToPCS = normalized FM * inv(diag(reference camera white)) *
     * inv(AnalogBalance * CameraCalibration)  (Adobe dng_color_spec.cpp).
     */
    double temp[9];
    for(unsigned row=0;row<3;row++)for(unsigned col=0;col<3;col++){
       double sum=0.0;
       for(unsigned k=0;k<3;k++)sum+=fm[3*row+k]/refwhite[k]*inv_abcc[3*k+col];
       temp[3*row+col]=sum;
       if(!isfinite(sum))return HB_DNG_PCS_INVALID;
    }
    double xyzw[3];mat_vec(temp,white,xyzw);
    for(unsigned row=0;row<3;row++)if(fabs(xyzw[row]-D50[row])>1e-9)return HB_DNG_PCS_INVALID;
    /* No overlapping metadata/reference buffers. */
    if(overlap(out,sizeof(temp),fm1,9*sizeof(double)) ||
       (fm2&&overlap(out,sizeof(temp),fm2,9*sizeof(double))) ||
       (cc1&&overlap(out,sizeof(temp),cc1,9*sizeof(double))) ||
       (cc2&&overlap(out,sizeof(temp),cc2,9*sizeof(double))) ||
       overlap(out,sizeof(temp),ab,3*sizeof(double))||
       overlap(out,sizeof(temp),neutral,3*sizeof(double))||
       overlap(out,sizeof(temp),receipt,sizeof(*receipt)))return HB_DNG_PCS_OVERLAP;
    hb_dng_pcs_receipt r={HB_DNG_PCS_BRIDGE_SCHEMA,1,1,1,1,0,0,0};
    memcpy(out,temp,sizeof(temp));*receipt=r;
    return HB_DNG_PCS_OK;
}
int hb_dng_pcs_apply(const double mat[9],const double *rgb,size_t n,double *xyz) {
    if(!mat||!rgb||!xyz||n==0||n>HB_DNG_PCS_MAX_PROBE_PIXELS ||
       !finite_n(mat,9)||!finite_n(rgb,3*n))return HB_DNG_PCS_INVALID;
    if(overlap(rgb,3*n*sizeof(double),xyz,3*n*sizeof(double))||
       overlap(mat,9*sizeof(double),xyz,3*n*sizeof(double)))return HB_DNG_PCS_OVERLAP;
    /* Every input is validated first; no clipping of negatives/highlights. */
    for(size_t j=0;j<n;j++)for(unsigned r=0;r<3;r++){
       double x=mat[3*r]*rgb[j*3]+mat[3*r+1]*rgb[j*3+1]+mat[3*r+2]*rgb[j*3+2];
       if(!isfinite(x))return HB_DNG_PCS_INVALID;
    }
    for(size_t j=0;j<n;j++)mat_vec(mat,rgb+j*3,xyz+j*3);
    return HB_DNG_PCS_OK;
}
