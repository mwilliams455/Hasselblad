#include "highlight53.h"
#include <math.h>
#include <string.h>

static double project(double x, double y, const double p[3]) {
    return ((x/p[0]+y-p[1])/(p[0]+1/p[0]))/p[2];
}

int hb_highlight53_prepare(hb_highlight53 *out, const double gains[3],
                          const uint16_t truncation[3], int allow_equal_gain_limit) {
    if (!out || !gains || !truncation) return -1;
    hb_highlight53 p;
    memset(&p, 0, sizeof(p));
    double top = 0;
    for (int i=0; i<3; ++i) {
        if (!isfinite(gains[i]) || gains[i]<=0 || !truncation[i]) return -1;
        top=fmax(top,gains[i]); p.order[i]=i;
    }
    if (top<=1e-9) return -1;
    for (int i=0; i<3; ++i) for (int j=i+1; j<3; ++j) {
        int a=p.order[i], b=p.order[j];
        if (gains[b]>gains[a] || (gains[b]==gains[a] && b>a)) {
            p.order[i]=b; p.order[j]=a;
        }
    }
    for (int i=0; i<3; ++i) {
        p.undo[p.order[i]]=i;
        p.weights[i]=gains[p.order[i]]/top;
        if (p.weights[i]<=0) return -1;
        p.limits[i]=truncation[p.order[i]]/65535.;
    }
    if (p.weights[1]==p.weights[2]) {
        if (!allow_equal_gain_limit) return -2;
        p.limit_mode=1; *out=p; return 1;
    }
    double b=p.weights[1], c=p.weights[2];
    double slope=(1-c/b)/(1-c), offset=c/b-slope*c, inv=1/slope;
    double norm=(inv*c+c/b-offset)/(slope+inv);
    double low=fmax((1-inv+inv*c+c/b)*.5,.0001);
    p.projection[0]=slope; p.projection[1]=offset; p.projection[2]=norm;
    p.red_projection[0]=1; p.red_projection[1]=0; p.red_projection[2]=low;
    double a=fmin(1,b/p.weights[0]);
    p.middle[0]=(1-inv+inv*a+1)*.5/low;
    p.middle[1]=p.middle[2]=project(a,1,p.projection);
    p.full[0]=1/low;
    p.full[1]=p.full[2]=project(1,1,p.projection);
    for (int i=0; i<3; ++i) {
        if (!isfinite(p.middle[i]) || !isfinite(p.full[i]) || !isfinite(p.projection[i])) return -1;
        /* A negative middle anchor is valid: only its upper segment is used.
         * Exactly one instead makes the reachable lower segment singular. */
        if (p.middle[i]==1) return -1;
    }
    *out=p; return 0;
}

static void boundary(const hb_highlight53 *p, const double v[3], double out[3]) {
    if (p->limit_mode) {
        out[0]=v[0];
        out[1]=v[1]*fmax(p->weights[1],v[0]);
        out[2]=v[2]*fmax(p->weights[1],v[0]);
        return;
    }
    for (int i=0; i<3; ++i) out[i]=v[i]*p->weights[i];
    int channel=-1;
    for (int i=0; i<3; ++i) if (v[i]>=1) channel=i;
    if (channel<0) return;
    double pos=channel==0 ? project(v[1],v[2],p->red_projection) :
                           project(v[0],v[channel==1 ? 2 : 1],p->projection);
    pos=fmax(1,pos);
    double mid=p->middle[channel], full=p->full[channel];
    double center=p->weights[1]/p->weights[2], gain_b=1, gain_c;
    if (pos>mid) {
        double mix=(pos-mid)/(full-mid);
        gain_b=1+(1/p->weights[1]-1)*mix;
        gain_c=center+(1/p->weights[2]-center)*mix;
    } else {
        gain_c=1+(center-1)*(pos-1)/(mid-1);
    }
    out[1]*=gain_b; out[2]*=gain_c;
}

static void convert(const hb_highlight53 *p, const double rgb[3], double out[3]) {
    double v[3], result[3]; int inside=1;
    for (int i=0; i<3; ++i) {
        v[i]=fmin(rgb[p->order[i]]*(1/p->limits[i]),1);
        if (v[i]>=1) inside=0;
    }
    if (!inside) boundary(p,v,result);
    else {
        double weights[3], sum=0;
        for (int i=0; i<3; ++i) {
            double w=v[i]*v[i]; w*=w; w*=w; weights[i]=w; sum+=w;
            result[i]=v[i]*p->weights[i];
        }
        if (sum>0) for (int j=0; j<3; ++j) {
            double edge[3]={v[0],v[1],v[2]}, corrected[3]; edge[j]=1;
            boundary(p,edge,corrected);
            for (int i=0; i<3; ++i) result[i]+=(corrected[i]-edge[i]*p->weights[i])*weights[j]/sum;
        }
    }
    for (int i=0; i<3; ++i) out[p->order[i]]=fmin(result[i]/(1/p->limits[i]),p->limits[i]);
}

int hb_highlight53_rgb16(const hb_highlight53 *p, const uint16_t *in,
                        uint16_t *out, size_t pixels) {
    if (!p || !in || !out || pixels>SIZE_MAX/3) return -1;
    for (size_t k=0; k<pixels; ++k) {
        double v[3], result[3];
        for (int i=0; i<3; ++i) v[i]=in[3*k+(size_t)i]/65535.;
        convert(p,v,result);
        for (int i=0; i<3; ++i) out[3*k+(size_t)i]=(uint16_t)floor(fmin(1,fmax(0,result[i]))*65535+.5);
    }
    return 0;
}

int hb_highlight53_float(const hb_highlight53 *p, const float *in,
                        float *out, size_t pixels) {
    if (!p || !in || !out || pixels>SIZE_MAX/3) return -1;
    for (size_t k=0; k<3*pixels; ++k) if (!isfinite(in[k]) || in[k]<0) return -1;
    for (size_t k=0; k<pixels; ++k) {
        double v[3], result[3];
        for (int i=0; i<3; ++i) v[i]=in[3*k+(size_t)i];
        convert(p,v,result);
        for (int i=0; i<3; ++i) out[3*k+(size_t)i]=(float)result[i];
    }
    return 0;
}
