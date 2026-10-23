/* SPDX-License-Identifier: MIT */
#include "hb42_colour.h"
#include <math.h>
#include <stdint.h>

static double clamp(double v, double lo, double hi) {
    return v < lo ? lo : v > hi ? hi : v;
}
static int finite_bounded(const double *v, size_t n, double bound) {
    for (size_t i=0;i<n;i++) if (!isfinite(v[i]) || fabs(v[i])>bound) return 0;
    return 1;
}
static int overlaps(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x=(uintptr_t)a, y=(uintptr_t)b;
    return x<=y ? y-x<an : x-y<bn;
}
int hb42_validate(const hb42_params *p) {
    if (!p || !p->grid || !p->curve || p->width<2 || p->height<2 ||
        p->width>256 || p->height>256 ||
        p->grid_count!=(size_t)p->width*p->height*2 || p->curve_count!=65536 ||
        p->wb_owner>HB42_WB_IN_INPUT ||
        !finite_bounded(p->first,9,1e6) || !finite_bounded(p->second,9,1e6) ||
        !finite_bounded(p->shadow,4,1e6) || p->shadow[0]<=0 ||
        !finite_bounded(p->wb,3,64) ||
        !isfinite(p->exposure) || p->exposure<=0 || p->exposure>64 ||
        !isfinite(p->bias_x) || !isfinite(p->bias_y) ||
        fabs(p->bias_x)>256 || fabs(p->bias_y)>256 ||
        !finite_bounded(p->grid,p->grid_count,1e6)) return HB42_INVALID;
    for (size_t i=0;i<3;i++)
        if (p->wb[i]<=0 || (p->wb_owner!=HB42_WB_SEPARATE && p->wb[i]!=1))
            return HB42_INVALID;
    for (size_t i=0;i<65536;i++)
        if (!isfinite(p->curve[i]) || p->curve[i]<0 || p->curve[i]>65535)
            return HB42_INVALID;
    return HB42_OK;
}
int hb42_render(const hb42_params *p, const uint16_t *rgb, size_t n, uint16_t *out) {
    if (!rgb || !out || n==0 || n>16777216 || hb42_validate(p)) return HB42_INVALID;
    size_t bytes=n*3*sizeof(uint16_t);
    if (overlaps(rgb,bytes,out,bytes) || overlaps(p,sizeof(*p),out,bytes) ||
        overlaps(p->grid,p->grid_count*sizeof(double),out,bytes) ||
        overlaps(p->curve,65536*sizeof(float),out,bytes)) return HB42_OVERLAP;
    for (size_t i=0;i<n;i++) {
        double v[3], yc[3];
        for (size_t c=0;c<3;c++) v[c]=rgb[3*i+c]*p->wb[c]*p->exposure;
        for (size_t c=0;c<3;c++)
            yc[c]=(p->first[3*c]*v[0]+p->first[3*c+1]*v[1])+p->first[3*c+2]*v[2];
        double yy=yc[0];
        if (yy<=0) {out[3*i]=out[3*i+1]=out[3*i+2]=0; continue;}
        double x=clamp(yc[1]/yy*32+p->bias_x,0,p->width-1);
        double y=clamp(yc[2]/yy*32+p->bias_y,0,p->height-1);
        size_t x0=(size_t)x, y0=(size_t)y;
        size_t x1=x0+1<p->width ? x0+1 : x0;
        size_t y1=y0+1<p->height ? y0+1 : y0;
        double dx=x-x0, dy=y-y0, chroma[2];
        for (size_t c=0;c<2;c++) {
            double top=p->grid[2*(y0*p->width+x0)+c]*(1-dx)
                      +p->grid[2*(y0*p->width+x1)+c]*dx;
            double bot=p->grid[2*(y1*p->width+x0)+c]*(1-dx)
                      +p->grid[2*(y1*p->width+x1)+c]*dx;
            chroma[c]=(top*(1-dy)+bot*dy)/32;
        }
        double weight=yy>p->shadow[0] ? 1 :
            (p->shadow[1]*yy+p->shadow[2])*yy+p->shadow[3];
        weight=clamp(weight,0,1);
        double cb=chroma[0]*yy*weight, cr=chroma[1]*yy*weight;
        for (size_t c=0;c<3;c++) {
            /* Deliberately omit column zero: the verified routine adds Y. */
            double value=(yy+p->second[3*c+1]*cb)+p->second[3*c+2]*cr;
            size_t index=(size_t)clamp(value,0,65535);
            out[3*i+c]=(uint16_t)p->curve[index];
        }
    }
    return HB42_OK;
}
