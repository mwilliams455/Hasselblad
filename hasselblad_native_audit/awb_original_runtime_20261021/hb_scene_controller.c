/* SPDX-License-Identifier: MIT */
#include "hb_scene_controller.h"
#include "hb_scene_candidates.h"
#include "hb_scene_filter.h"
#include "hb_scene_optimizer.h"
#include <string.h>
static uint32_t u32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const unsigned char*p){float v;memcpy(&v,p,4);return v;}
static void w32(unsigned char*p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char*p,uint16_t v){memcpy(p,&v,2);}
uint32_t hb_scene_interpolate(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x){
    if(x0>=x1){uint32_t t=x0;x0=x1;x1=t;t=y0;y0=y1;y1=t;}
    return hb_interp_opt(x0,x1,y0,y1,x);
}
uint32_t hb_special_gate_curve(const unsigned char *ctx,int32_t camera_index,uint32_t slot,const unsigned char *p,uint32_t *out){
    unsigned n=p[4];if(!n){*out=0;return 0;}
    uint32_t gate=u16(ctx+0x3da50+2*(slot&255));
    const unsigned char *a=p+5,*b=a+2*(n-1);
    if(gate<=a[0]){*out=a[1];return 0;}if(gate>=b[0]){*out=b[1];return 0;}
    for(unsigned i=1;i<n;++i)if(gate<=p[5+2*i]){b=p+5+2*i;a=b-2;break;}
    /* Original selects brackets with the gate, but interpolates camera_index. */
    *out=hb_scene_interpolate(a[0],b[0],a[1],b[1],(float)camera_index);return 0;
}
uint32_t hb_special_ct_curve(const unsigned char *ctx,int32_t camera_index,uint32_t slot,const unsigned char *p,uint32_t *out){
    unsigned n=p[1];if(!n){*out=0;return 0;}
    uint32_t ct=u32(ctx+0x841bc+(slot&255)*0x74);
    const unsigned char *a=p+4,*b=a+24*(n-1);
    if(ct<=u32(a))b=a;else if(ct>=u32(b))a=b;
    else{unsigned i;for(i=1;i<n;++i)if(ct<=u32(p+4+24*i)){b=p+4+24*i;a=b-24;break;}if(i==n)return 73;}
    uint32_t av,bv,st=hb_special_gate_curve(ctx,camera_index,slot,a,&av);if(st)return st;
    st=hb_special_gate_curve(ctx,camera_index,slot,b,&bv);if(st)return st;
    *out=hb_scene_interpolate(u32(a),u32(b),av,bv,(float)ct);return 0;
}
uint32_t hb_special_post_weight(unsigned char *ctx,const unsigned char *cfg,int32_t camera_index,uint32_t slot){
    size_t off=((slot-2)&255)*0x2bd0;unsigned n=cfg[0x17fdc+off];
    if(!n){w32(ctx+0x841d4+(slot&255)*0x74,0);return 0;}
    float ev=rf(ctx+0x37618);const unsigned char *a=cfg+0x17fe0+off,*b=a+196*(n-1);
    if(ev<=(float)a[0])b=a;else if(ev>=(float)b[0])a=b;
    else{unsigned i;for(i=1;i<n;++i)if(ev<=(float)a[196*i]){b=a+196*i;a=b-196;break;}if(i==n)return 73;}
    uint32_t av,bv,st=hb_special_ct_curve(ctx,camera_index,slot,a,&av);if(st)return st;
    st=hb_special_ct_curve(ctx,camera_index,slot,b,&bv);if(st)return st;
    w32(ctx+0x841d4+(slot&255)*0x74,hb_scene_interpolate(a[0],b[0],av,bv,ev));return 0;
}
uint32_t hb_special_spectral_weight(unsigned char *ctx,const unsigned char *cfg,uint32_t slot){
    size_t off=((slot-2)&255)*0x2bd0;slot&=255;
    if(!cfg[0x139e2c]||!cfg[0x139e2e]||!cfg[0x16c6c+off])return 0;
    if(!u32(ctx+0xc5a0)){memset(ctx+0x2154+slot*0xa71,1,81);return 0;}
    uint32_t n=u16(ctx+0x3761e),request=u32(cfg+0x16c70+off),start=request?request:1;
    if(request>n)start=n+65535;start=(start+65535)&65535;
    uint32_t sum=0;for(uint32_t i=start;i<n;++i)sum+=u32(ctx+0x37620+4*i);
    return hb_spectral_ratio(cfg+0x16c74+off,sum,ctx+0x2154+slot*0xa71);
}
uint32_t hb_scene_process(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model,int32_t camera_index){
    uint32_t maximum=0,st=hb_scene_normal_slots(ctx,cfg,model,&maximum);if(st)return st;
    for(unsigned slot=2;slot<4;++slot){
        size_t offset=(slot-2)*0x2bd0;
        if(u16(ctx+0x3da50+slot*2)&&cfg[0x15a30+offset]==1){
            st=hb_special_spectral_weight(ctx,cfg,slot);if(st)return st;
            unsigned n=cfg[0x15c88+offset],eligible=0,metric=0;const unsigned char *params=cfg+0x15c8c+offset;
            for(unsigned scene=0;scene<n;++scene){const unsigned char *p=params+scene*508;uint32_t ev=ctx[0x3761c];
                if(u32(p)>ev||u32(p+4)<ev)continue;eligible=1;
                size_t off=slot*0x10188+scene*0x2020;ctx[0x3dacc+off]=1;
                st=hb_candidate_weight(ctx,cfg,p,scene,slot);if(st)return st;
                st=hb_scene_filter(ctx,scene,slot,cfg[0x15c89+offset]);if(st)return st;
                st=hb_candidate_accumulate_with_model(ctx,cfg,p,cfg+0x16db8+offset,scene,slot,u32(cfg+0x15a34+offset),cfg[0x15c8a+offset],model);if(st)return st;
                uint32_t m=u32(ctx+0x3fae4+off);if(m>metric)metric=m;
            }
            if(eligible){st=hb_scene_optimizer(ctx,slot,n,params);if(st)return st;
                st=hb_special_post_weight(ctx,cfg,camera_index,slot);if(st)return st;
                unsigned char *m=ctx+0x841cc+slot*0x74;if(u32(m)<metric)w32(m,metric);
            }
        }
        uint32_t m=u32(ctx+0x841cc+slot*0x74);maximum=m>(maximum&65535)?m:(maximum&65535);
    }
    w16(ctx+0xb142c,(uint16_t)maximum);return 0;
}
