/* SPDX-License-Identifier: MIT */
#include "hb_scene_candidates.h"
#include "hb_stat_prepare.h"
#include "hb_scene_filter.h"
#include "hb_scene_optimizer.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const unsigned char*p){float v;memcpy(&v,p,4);return v;}
static void w32(unsigned char*p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t fu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int32_t fs(double v){return isnan(v)?0:v>=2147483647.0?INT32_MAX:v<=-2147483648.0?INT32_MIN:(int32_t)v;}
static uint32_t divu(uint32_t a,uint32_t b){return b?a/b:0;}
uint32_t hb_interp_opt(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x){
    float a,b;if((float)x0>=x){a=1;b=0;}else if((float)x1<=x){a=0;b=1;}else{b=x-(float)x0;a=(float)x1-x;}
    float p=a*(float)y0,q=b*(float)y1;return fu((q+p)/(b+a));
}
static void bracket_ct(const unsigned char *p,uint32_t n,uint32_t ct,const unsigned char **a,const unsigned char **b){
    *a=p+4;*b=*a+72*(n-1);
    if(u32(*a)>=ct){*b=*a;return;}if(u32(*b)<=ct){*a=*b;return;}
    for(uint32_t i=1;i<n;++i)if(u32(p+4+72*i)>=ct){*b=p+4+72*i;*a=*b-72;return;}
}
static uint32_t curve_axis(const unsigned char *p,uint32_t value,int tint,uint32_t *out){
    unsigned n=p[4];if(!n)return tint?61:56;
    const unsigned char *a=p+8,*b=p+8*n;
    if(tint){
        int32_t v=(int32_t)value;
        if((int32_t)u32(a)>=v)b=a;else if((int32_t)u32(b)<=v)a=b;
        else for(unsigned i=1;i<n;++i)if((int32_t)u32(p+8+8*i)>=v){b=p+8+8*i;a=b-8;break;}
        *out=hb_interp_opt(u32(a),u32(b),a[4],b[4],(float)v);
    }else{
        uint16_t v=(uint16_t)value;
        if(u16(a)>=v)b=a;else if(u16(b)<=v)a=b;
        else for(unsigned i=1;i<n;++i)if(u16(p+8+8*i)>=v){b=p+8+8*i;a=b-8;break;}
        *out=hb_interp_opt(u16(a),u16(b),u32(a+4),u32(b+4),(float)v);
    }
    return 0;
}
uint32_t hb_candidate_curve(const unsigned char *p,uint32_t ct,uint32_t value,uint32_t *out,int tint){
    if(!tint)*out=256;unsigned n=p[1];if(!n)return tint?59:55;
    const unsigned char *a,*b;bracket_ct(p,n,ct,&a,&b);
    uint32_t av,bv,st=curve_axis(a,value,tint,&av);if(st)return st;
    st=curve_axis(b,value,tint,&bv);if(st)return st;
    *out=hb_interp_opt(u32(a),u32(b),av,bv,(float)ct);return 0;
}
static void ev_rows(const unsigned char *first,unsigned n,float ev,const unsigned char **a,const unsigned char **b){
    *a=first;*b=first+580*(n-1);
    if(ev<=(float)(*a)[0])*b=*a;else if(ev>=(float)(*b)[0])*a=*b;
    else for(unsigned i=1;i<n;++i)if(ev<=(float)first[580*i]){*b=first+580*i;*a=*b-580;break;}
}
static void remap(const unsigned char *ctx,uint32_t ct,uint32_t *r,uint32_t *b){
    unsigned i=ct<=2000?0:ct>10000?80:(ct-2000)/100;if(i>79)i=80;
    const unsigned char *a=ctx+0x348+16*i,*z=ctx+0x858+16*i;
    float red=(float)*r/(float)u32(a),blue=(float)*b/(float)u32(a+4);
    *r=fu(red*(float)u32(z));*b=fu(blue*(float)u32(z+4));
}
static int32_t line(uint32_t r,const unsigned char *p,int offset){
    uint32_t v=u32(p)*r;v=(uint32_t)((int32_t)v>>12)+u32(p+4)+(uint32_t)offset;return (int32_t)v;
}
uint32_t hb_candidate_weight(unsigned char *ctx,const unsigned char *cfg,const unsigned char *p,uint32_t scene,uint32_t slot){
    if(!p)return 40;scene&=255;slot&=255;
    size_t off=slot*0x10188+scene*0x2020;unsigned char *weights=ctx+0x3dace +off;
    uint32_t width=u32(ctx+0x18),height=u32(ctx+0x1c);unsigned remap_flag=ctx[0x990dc];
    for(uint32_t row=0;row<height;++row)for(uint32_t col=0;col<width;++col){
        uint32_t i=row*width+col;const unsigned char *d=ctx+0xf450+40*i;unsigned char *out=weights+2*i;
        if(d[24]){
            uint32_t w=ctx[0x1734+slot*0xa71+scene*81+u32(d+16)];w16(out,(uint16_t)w);
            if(w){
                w=(uint16_t)fs((float)w*rf(d+28));w16(out,(uint16_t)w);
                if(cfg[0x138748]==1&&cfg[slot*0xa278+0x2678]==1){
                    unsigned category=ctx[0x3be2c+i];uint32_t scale=256;
                    if(category>=1&&category<=6){
                        const unsigned char *z=cfg+slot*0xa278+(category-1)*0x1228+0x267c;
                        if(u32(z)!=category)return 53;
                        if(z[4]==1){
                            unsigned n=z[5];if(!n)return 54;
                            const unsigned char *a,*b;float ev=rf(ctx+0x37618);ev_rows(z+8,n,ev,&a,&b);
                            uint32_t probability=u16(ctx+0x3862c+2*(u32(ctx+0x28)*category+i)),av,bv;
                            uint32_t st=hb_candidate_curve(a,u32(d+12),probability,&av,0);if(st)return st;
                            st=hb_candidate_curve(b,u32(d+12),probability,&bv,0);if(st)return st;
                            scale=hb_interp_opt(a[0],b[0],av,bv,ev);
                        }
                    }
                    w=(uint16_t)((w*scale)>>8);w16(out,(uint16_t)w);
                }
                if(!w){w=1;w16(out,1);}
                if(cfg[0x16edcc]==1){uint32_t index=u32(d+36)>>(cfg[0x16edcd]&31);if(index>=63)index=63;
                    w=(uint16_t)((w*u16(cfg+0x16edce +2*index))>>8);w16(out,(uint16_t)w);}
            }
        }
        uint32_t r=u32(d),b=u32(d+8);if(remap_flag==1)remap(ctx,u32(d+12),&r,&b);
        int32_t zone_weight=-1;
        for(unsigned j=0;j<p[0x58];++j){const unsigned char *z=p+0x5c+52*j;
            if((int32_t)r<(int32_t)u32(z)||(int32_t)r>(int32_t)u32(z+4)||
               (int32_t)b<(int32_t)u32(z+8)||(int32_t)b>(int32_t)u32(z+12)||
               (int32_t)b>line(r,z+24,2)||(int32_t)b<line(r,z+16,-2)||
               (int32_t)b>line(r,z+40,2)||(int32_t)b<line(r,z+32,-2))continue;
            if(zone_weight<z[48])zone_weight=z[48];
        }
        if(zone_weight>=0)w16(out,(uint16_t)zone_weight);
    }
    uint32_t n=0;for(unsigned i=0;i<u16(ctx+0x28);++i)n+=u16(weights+2*i)!=0;
    w32(ctx+0x3fae4+off,n);return 0;
}
uint32_t hb_candidate_temperature(const unsigned char *ctx,uint32_t mode,uint32_t r,uint32_t g,uint32_t b,float *ct,float *tint){
    (void)g;if(mode)return mode<=2?HB_PREP_UNSUPPORTED:94;
    uint32_t best=0x80000000,index=UINT32_MAX;
    for(unsigned i=0;i<81;++i){uint32_t dr=r-u32(ctx+0x348+16*i),db=b-u32(ctx+0x34c+16*i),dist=dr*dr+db*db;
        if(dist<best){best=dist;index=i;}}
    uint32_t temperature=index==UINT32_MAX?0:2000+100*index;
    unsigned hi=index==UINT32_MAX||index==0?1:index;
    uint32_t ar=u32(ctx+0x348+16*(hi-1)),ab=u32(ctx+0x34c+16*(hi-1));
    uint32_t zr=u32(ctx+0x348+16*hi),zb=u32(ctx+0x34c+16*hi);
    uint32_t dy=ab-zb,dx=ar-zr,len2=dy*dy+dx*dx;
    uint32_t numerator=ar*zb-ab*zr+dy*r+(zr-ar)*b;
    int32_t deviation=fs((double)(int32_t)numerator/sqrt((double)(int32_t)len2));
    *ct=(float)temperature;*tint=(float)deviation;return 0;
}
uint32_t hb_candidate_accumulate(unsigned char *ctx,const unsigned char *p,const unsigned char *curves,uint32_t scene,uint32_t slot,uint32_t mode,uint32_t fraction){
    const unsigned char *cfg;memcpy(&cfg,ctx+0xb2028,sizeof cfg);
    return hb_candidate_accumulate_with_model(ctx,cfg,p,curves,scene,slot,mode,fraction,NULL);
}
uint32_t hb_candidate_accumulate_with_model(unsigned char *ctx,const unsigned char *cfg,const unsigned char *p,const unsigned char *curves,uint32_t scene,uint32_t slot,uint32_t mode,uint32_t fraction,const hb_temperature_model *model){
    scene&=255;slot&=255;size_t off=slot*0x10188+scene*0x2020;
    uint32_t threshold=(u32(ctx+0x28)*(fraction&255))>>8,ev=ctx[0x3761c],count=0;
    uint64_t weights=0,red=0,blue=0;
    for(uint32_t y=0;y<u32(ctx+0x1c);++y)for(uint32_t x=0;x<u32(ctx+0x18);++x){
        uint32_t i=y*u32(ctx+0x18)+x,w=u16(ctx+0x3dace +off+2*i);if(!w)continue;
        unsigned char *d=ctx+0xf450+40*i;weights+=w;++count;red+=(uint32_t)(u32(d)*w);blue+=(uint32_t)(u32(d+8)*w);w32(d+20,u32(d+20)+1);
    }
    unsigned char *candidate=ctx+0x3fad0+off;
    if(count<threshold){w32(candidate+20,count);
        uint32_t w=p[10]+divu(((uint32_t)p[11]-p[10])*(ev-u32(p)),u32(p+4)-u32(p));
        w32(candidate+24,w);return 0;}
    if(weights){red/=weights;blue/=weights;}
    w32(candidate,(uint32_t)red);w32(candidate+4,(uint32_t)blue);w32(candidate+20,count);candidate[8]=1;
    float ct=0,tint=0;uint32_t st=hb_temperature_compute(ctx,cfg,model,mode,(uint32_t)red,4096,(uint32_t)blue,&ct,&tint);if(st)return st;
    unsigned n=curves[0];if(!n)return 57;
    const unsigned char *a,*b;ev_rows(curves+4,n,(float)ev,&a,&b);
    uint32_t av,bv,temperature=fu(ct),deviation=(uint32_t)fs(tint);
    st=hb_candidate_curve(a,temperature,deviation,&av,1);if(st)return st;
    st=hb_candidate_curve(b,temperature,deviation,&bv,1);if(st)return st;
    w32(candidate+24,hb_interp_opt(a[0],b[0],av,bv,(float)ev));
    w32(candidate+12,temperature);w32(candidate+16,deviation);return 0;
}
uint32_t hb_spectral_distribution(const unsigned char *p,unsigned char *out){
    unsigned n=p[4];if(!n)return 0;unsigned char values[81]={0};
    for(unsigned i=0;i+1<n;++i){
        unsigned left=(u16(p+6+4*i)/100)&255,right=(u16(p+10+4*i)/100)&255;
        int32_t span=(int32_t)(right-left);if(span<1)return 45;
        if(left>80)return HB_PREP_UNSUPPORTED;
        uint32_t a=u16(p+8+4*i),b=u16(p+12+4*i),delta=(b-a)<<10;
        int32_t slope=(int32_t)delta/span;values[left]=(unsigned char)a;
        for(unsigned j=1;j<=(unsigned)span&&left+j<=80;++j){
            uint32_t product=j*(uint32_t)slope;if((int32_t)product<0)product+=1023;
            values[left+j]=(unsigned char)(values[left]+(product>>10));
        }
    }
    memcpy(out,values,81);return 0;
}
uint32_t hb_spectral_ratio(const unsigned char *p,uint32_t ratio,unsigned char *out){
    unsigned n=p[0];if(!n)return 0;
    const unsigned char *a=p+4,*b=a+40*(n-1);
    if(u32(a)>=ratio)b=a;else if(u32(b)<=ratio)a=b;
    else{unsigned i;for(i=1;i<n;++i)if(u32(p+4+40*i)>=ratio){b=p+4+40*i;a=b-40;break;}if(i==n)return 46;}
    unsigned char av[81]={0},bv[81]={0};
    uint32_t st=hb_spectral_distribution(a,av);if(st)return st;st=hb_spectral_distribution(b,bv);if(st)return st;
    uint32_t lo=u32(a),hi=u32(b);if(lo>=hi){uint32_t t=lo;lo=hi;hi=t;for(unsigned i=0;i<81;++i){unsigned char v=av[i];av[i]=bv[i];bv[i]=v;}}
    float wa,wb;if(lo>=ratio){wa=1;wb=0;}else if(hi<=ratio){wa=0;wb=1;}else{wa=(float)(hi-ratio);wb=(float)(ratio-lo);}
    float sum=wa+wb;
    for(unsigned i=0;i<81;++i){if(sum==0)out[i]=(unsigned char)((av[i]+bv[i])>>1);
        else{float x=(float)av[i]*wa,y=(float)bv[i]*wb;out[i]=(unsigned char)fu((x+y)/sum);}}
    return 0;
}
uint32_t hb_scene_spec_weight(unsigned char *ctx,const unsigned char *cfg,uint32_t slot){
    slot&=255;if(!cfg[0x139e2c]||!cfg[0x139e2e]||!cfg[0x252c+slot*0xa278])return 0;
    if(!u32(ctx+0xc5a0)){memset(ctx+0x2154+slot*0xa71,1,81);return 0;}
    uint32_t n=u16(ctx+0x3761e),request=u32(cfg+0x2530+slot*0xa278),start=request?request:1;
    if(request>n)start=n+65535;start=(start+65535)&65535;
    uint32_t sum=0;for(uint32_t i=start;i<n;++i)sum+=u32(ctx+0x37620+4*i);
    return hb_spectral_ratio(cfg+0x2534+slot*0xa278,sum,ctx+0x2154+slot*0xa71);
}
uint32_t hb_normal_scene(unsigned char *ctx,const unsigned char *cfg){
    return hb_normal_scene_with_model(ctx,cfg,NULL);
}
uint32_t hb_normal_scene_with_model(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model){
    if(u16(ctx+0x3da54)||u16(ctx+0x3da56))return HB_PREP_UNSUPPORTED;
    uint32_t maximum=0;
    for(unsigned slot=0;slot<2;++slot){
        if(u16(ctx+0x3da50+2*slot)){
            uint32_t st=hb_scene_spec_weight(ctx,cfg,slot);if(st)return st;
            unsigned n=cfg[0x1540+slot*0xa278],eligible=0,metric=0;
            const unsigned char *params=cfg+0x154c+slot*0xa278;
            for(unsigned scene=0;scene<n;++scene){
                const unsigned char *p=params+508*scene;uint32_t ev=ctx[0x3761c];if(u32(p)>ev||u32(p+4)<ev)continue;
                eligible=1;size_t off=slot*0x10188+scene*0x2020;ctx[0x3dacc+off]=1;
                st=hb_candidate_weight(ctx,cfg,p,scene,slot);if(st)return st;
                st=hb_scene_filter(ctx,scene,slot,cfg[0x1548+slot*0xa278]);if(st)return st;
                st=hb_candidate_accumulate_with_model(ctx,cfg,p,cfg+slot*0xa278+0xa594,scene,slot,u32(cfg+slot*0xa278+0x1544),cfg[slot*0xa278+0x154a],model);if(st)return st;
                uint32_t m=u32(ctx+0x3fae4+off);if(m>metric)metric=m;
            }
            if(n){if(!eligible)return 40;st=hb_scene_optimizer(ctx,slot,n,params);if(st)return st;}
            unsigned char *m=ctx+0x841cc+slot*0x74;if(u32(m)<metric)w32(m,metric);
        }
        uint32_t m=u32(ctx+0x841cc+slot*0x74);maximum=m>(maximum&65535)?m:(maximum&65535);
    }
    for(unsigned slot=2;slot<4;++slot){uint32_t m=u32(ctx+0x841cc+slot*0x74);maximum=m>(maximum&65535)?m:(maximum&65535);}
    w16(ctx+0xb142c,(uint16_t)maximum);return 0;
}
