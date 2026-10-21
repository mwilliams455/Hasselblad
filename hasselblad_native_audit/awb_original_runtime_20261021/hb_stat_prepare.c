/* SPDX-License-Identifier: MIT
 * Owned numeric reconstruction from original ARM64 control flow. Calibration
 * data is supplied at runtime; no proprietary LUTs are embedded here.
 */
#include "hb_stat_prepare.h"
#include <limits.h>
#include <math.h>
#include <string.h>
static uint32_t r32(const unsigned char *p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t r16(const unsigned char *p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const unsigned char *p){float v;memcpy(&v,p,4);return v;}
static void w32(unsigned char *p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char *p,uint16_t v){memcpy(p,&v,2);}
static void wf(unsigned char *p,float v){memcpy(p,&v,4);}
static uint32_t fcvtzu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static uint32_t ratio(uint32_t g,uint32_t c){uint32_t q=c?(g<<12)/c:0;return q<65535?q:65535;}

uint32_t hb_e2_main_parse(unsigned char *ctx,unsigned char *e2,unsigned char *out,unsigned char *meta){
    unsigned changed=r16(ctx+0xd494)!=r16(ctx+0xd4a2);
    /* Original post-processing remains a separate, explicitly unsupported
     * branch here. The unmodified IMX861 configuration initializes it off. */
    if(changed?ctx[0xd4b0]:e2[0x4bb4])return HB_PREP_UNSUPPORTED;
    uint32_t width=r16(e2+0x4158),height=r16(e2+0x415a);
    if(width*height>1024)return HB_PREP_UNSUPPORTED;
    w32(out,width);w32(out+4,height);w32(out+8,r32(e2+0x4118));w32(out+12,r32(e2+0x411c));
    w32(ctx+0xa24c0,width);w32(ctx+0xa24c4,height);w32(ctx+0xa24bc,r32(e2+0x10));
    if(changed){
        const unsigned bases[]={0x4bb4,0x17e74,0xe2b0};
        for(unsigned i=0;i<3;++i){unsigned char *p=e2+bases[i];
            p[0]=ctx[0xd4b0];p[4]=ctx[0xd4a5];
            memcpy(p+8,ctx+0xd4b4,8);memcpy(p+16,ctx+0xd4a8,8);
        }
        memmove(ctx+0xd494,ctx+0xd4a2,14);
    }
    for(uint32_t i=0;i<width*height;++i){
        const unsigned char *s=e2+0x18+16*i;unsigned char *d=out+16+32*i;
        uint32_t r=r16(s),g1=r16(s+2),g2=r16(s+4),b=r16(s+6),q=s[8],g=(g1+g2)>>1;
        unsigned valid=q>=10&&g!=0;
        w32(d,valid?ratio(g,r):0);w32(d+4,valid?4096:0);w32(d+8,valid?ratio(g,b):0);
        w32(d+12,r);w32(d+16,g);w32(d+20,b);w32(d+24,q);w32(d+28,valid?10000:0);
        unsigned char *rgb=ctx+0xa24c8+6*i;
        w16(rgb,(uint16_t)r);w16(rgb+2,(uint16_t)((g1>>1)+(g2>>1)));w16(rgb+4,(uint16_t)b);
    }
    w32(meta,r32(e2+0x10));w32(meta+4,r32(e2+8));
    for(unsigned i=0;i<4;++i)w32(meta+8+4*i,r16(e2+0x4150+2*i));
    return 0;
}

uint32_t hb_import_stats(unsigned char *ctx,const unsigned char *in,const unsigned char *meta){
    if(!in)return 7;
    if(r32(ctx+0x170)!=1)return HB_PREP_UNSUPPORTED;
    memset(ctx+0x84f48,0,0x14000);
    uint32_t width=r32(in),height=r32(in+4);
    if(width>64||height>64)return 7;
    uint32_t x=r32(meta+8),y=r32(meta+12),sx=r32(meta+16),sy=r32(meta+20);
    w32(ctx+0x20,sx*width+x);w32(ctx+0x24,sy*height+y);
    w32(ctx,r32(in+8));w32(ctx+4,r32(in+12));
    w32(ctx+8,x);w32(ctx+12,y);w32(ctx+16,sx);w32(ctx+20,sy);
    w32(ctx+24,width);w32(ctx+28,height);w32(ctx+40,width*height);w32(ctx+44,8);
    for(uint32_t i=0;i<width*height;++i){
        const unsigned char *s=in+16+32*i;unsigned char *d=ctx+0x84f48+20*i;
        memcpy(d,s,12);
        double a=(double)r32(s+12)*0.3,b=(double)r32(s+16)*0.6,c=(double)r32(s+20)*0.1;
        w32(d+12,fcvtzu((a+b)+c));w32(d+16,r32(s+28));
    }
    memset(ctx+0x98f48,0,0x180);uint32_t n=in[0x20010];w32(ctx+44,n);
    for(uint32_t i=0;i<n;++i){
        unsigned char *d=ctx+0x98f48+32*i;
        d[0]=(unsigned char)r32(in+0x20014+4*i);
        memcpy(d+4,in+0x20034+32*i,24);w32(d+28,r32(in+0x20050+32*i));
        for(unsigned j=0;j<4;++j)w32(ctx+0x99048+16*i+4*j,fcvtzu(rf(meta+0x44+16*i+4*j)));
    }
    return 0;
}
void hb_stat_awb_info(unsigned char *ctx){
    for(uint32_t i=0;i<r32(ctx+0x28);++i){
        const unsigned char *s=ctx+0x84f48+20*i;unsigned char *d=ctx+0xf450+40*i;
        memcpy(d,s,12);w32(d+32,r32(s+16));w32(d+36,r32(s+12));
    }
    for(uint32_t i=0;i<r32(ctx+0x2c);++i){
        const unsigned char *s=ctx+0x98f48+32*i;unsigned char *d=ctx+0x37458+40*i;
        ctx[0x37450+i]=s[0];memcpy(d,s+4,24);w32(d+36,r32(s+28));
        memcpy(ctx+0x37598+16*i,ctx+0x99048+16*i,16);
    }
}
static uint32_t interp(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x){
    uint32_t lo=x0<x1?x0:x1,hi=x0<x1?x1:x0,a=x0<x1?y0:y1,b=x0<x1?y1:y0;
    float wa,wb;
    if((float)lo>=x){wa=1;wb=0;}
    else if((float)hi<=x){wa=0;wb=1;}
    else{wb=x-(float)lo;wa=(float)hi-x;}
    float sum=wb+wa;if(sum==0)return (a+b)>>1;
    float p=wa*(float)a,q=wb*(float)b;return fcvtzu((q+p)/sum);
}
uint32_t hb_update_calib_gain(unsigned char *ctx){
    uint32_t n=ctx[0x1a0],ct=r32(ctx+0x1bc),r=4096,b=4096;
    if(n){
        const unsigned char *first=ctx+0x1a4,*last=first+12*(n-1),*chosen=NULL;
        if(ct<=r32(first))chosen=first;
        else if(ct>=r32(last)){chosen=last;if(ct>10000)w32(ctx+0x1bc,10000);}
        if(chosen){r=r32(chosen+4);b=r32(chosen+8);}
        else{
            uint32_t lo=0,hi=n-1;
            for(uint32_t i=1;i<n;++i)if(ct<r32(first+12*i)){lo=i-1;hi=i;break;}
            const unsigned char *a=first+12*lo,*z=first+12*hi;
            r=interp(r32(a),r32(z),r32(a+4),r32(z+4),(float)ct);
            b=interp(r32(a),r32(z),r32(a+8),r32(z+8),(float)ct);
        }
    }
    w32(ctx+0x1c0,r);w32(ctx+0x1c4,b);return 0;
}
static uint32_t calibrated(uint32_t value,uint32_t gain){uint32_t p=value*gain;return p>>28?65535:p>>12;}
uint32_t hb_stat_calib_proc(unsigned char *ctx){
    if(!ctx[0x19c]){w32(ctx+0x1c0,4096);w32(ctx+0x1c4,4096);return 0;}
    hb_update_calib_gain(ctx);uint32_t r=r32(ctx+0x1c0),b=r32(ctx+0x1c4);
    for(uint32_t i=0;i<r32(ctx+0x28);++i){unsigned char *d=ctx+0xf450+40*i;
        w32(d,calibrated(r32(d),r));w32(d+8,calibrated(r32(d+8),b));}
    for(uint32_t i=0;i<r32(ctx+0x2c);++i)if(ctx[0x37450+i]){unsigned char *d=ctx+0x37458+40*i;
        w32(d,calibrated(r32(d),r));w32(d+8,calibrated(r32(d+8),b));}
    return 0;
}
void hb_stat_ae_info(unsigned char *ctx,const unsigned char *config){
    float v=rf(ctx+0x990d4);if(v< -5)v=-5;else if(v>24)v=24;
    ctx[0xa883f]=ctx[0x990dc];memcpy(ctx+0xa8840,ctx+0x990d8,4);memcpy(ctx+0xa8844,ctx+0x990e0,4);
    ctx[0x3761c]=(unsigned char)((int)((double)(v>=0?v:0)+0.5));
    wf(ctx+0x37618,v);wf(ctx+0xa85da,v);
    if(config[0x139e2c]&&config[0x139e2e]){
        uint16_t n=(uint16_t)r32(ctx+0x990e4);w16(ctx+0x3761e,n);float total=rf(ctx+0x990e8);
        if(!(total>0)){memset(ctx+0x37620,0,4096);w32(ctx+0x37620,10000000);}
        else{float factor=10000000.0f/total;for(uint32_t i=0;i<n;++i)w32(ctx+0x37620+4*i,fcvtzu(rf(ctx+0x990ec+4*i)*factor));}
    }
}
static double distance(double r,double b,const unsigned char *table,uint32_t i){
    double dr=r-(double)r32(table+16*i),db=b-(double)r32(table+16*i+4);
    return dr*dr+db*db;
}
uint32_t hb_stat_auto(unsigned char *ctx,const unsigned char *config){
    /* Retain the earlier bounded entry. hb_stat_auto_complete owns the
     * enabled E-ND prefix and shares the classification suffix below. */
    if(ctx[0x278]||ctx[0x2f4]||config[0xc88]==0)return HB_PREP_UNSUPPORTED;
    hb_stat_awb_info(ctx);hb_stat_calib_proc(ctx);
    w32(ctx+0x2ec,4096);w32(ctx+0x2f0,4096);w32(ctx+0x300,4096);w32(ctx+0x304,4096);
    hb_stat_ae_info(ctx,config);
    return hb_stat_auto_classify(ctx,config);
}
uint32_t hb_stat_auto_classify(unsigned char *ctx,const unsigned char *config){
    const unsigned char *table=ctx+0x348,*ranges=ctx+0x308;
    for(uint32_t i=0;i<r32(ctx+0x28);++i){
        if(!r32(ctx+0x84f58+20*i))continue;
        unsigned char *d=ctx+0xf450+40*i;double r=r32(d),b=r32(d+8);
        double best=2147483648.0,previous_best=2147483648.0,dp=0,dn=0;
        uint32_t best_i=80,previous_i=80,mid=0,found=0;
        for(uint32_t s=1;s<config[0xc88];++s){
            uint32_t lo=r32(ranges+4*(s-1)),right=r32(ranges+4*s),candidate;
            double value;
            if(right-lo>=2){
                for(;;){
                    mid=(lo+right)>>1;
                    double dm=distance(r,b,table,mid);dp=distance(r,b,table,mid-1);
                    if(dm<=dp){
                        dn=distance(r,b,table,mid+1);
                        if(dm<=dn){found=1;candidate=mid;value=dm;goto chosen;}
                        lo=mid;
                    }else right=mid;
                    if(right-lo<=1)break;
                }
            }
            if(found){candidate=previous_i;value=previous_best;}
            else if(mid==lo+1){candidate=lo;value=dp;found=0;}
            else if(mid==right-1){candidate=right;value=dn;found=0;}
            else{candidate=previous_i;value=previous_best;found=0;}
chosen:
            previous_i=candidate;previous_best=value;
            if(value<best){best=value;best_i=candidate;}
        }
        double dist=sqrt(best),radius=r32(table+16*best_i+8);
        if(dist>radius)continue;
        w32(d+16,best_i);w32(d+12,2000+100*best_i);d[24]=1;
        double weight=1.0-dist/radius;
        if(!(weight<=1.0))weight=1.0;else if(weight<0)weight=0;
        wf(d+28,(float)weight);
    }
    return 0;
}
