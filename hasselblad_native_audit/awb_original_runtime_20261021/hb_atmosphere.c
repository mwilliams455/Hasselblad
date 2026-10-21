/* SPDX-License-Identifier: MIT */
#include "hb_atmosphere.h"
#include "hb_history.h"
#include "hb_scene_controller.h"
#include "hb_scene_optimizer.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const unsigned char*p){float v;memcpy(&v,p,4);return v;}
static void w32(unsigned char*p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char*p,uint16_t v){memcpy(p,&v,2);}
static void wf(unsigned char*p,float v){memcpy(p,&v,4);}
static int32_t fs(double v){return isnan(v)?0:v>=2147483647.0?INT32_MAX:v<=-2147483648.0?INT32_MIN:(int32_t)v;}
static uint32_t fu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static uint32_t abs32(uint32_t v){return (int32_t)v<0?0-v:v;}
static int32_t sd(uint32_t a,uint32_t b){int32_t x=(int32_t)a,y=(int32_t)b;return !y?0:x==INT32_MIN&&y==-1?INT32_MIN:x/y;}
int32_t hb_atmosphere_interpolate_signed(int32_t x0,int32_t x1,int32_t y0,int32_t y1,float x){
    if(x0>=x1){int32_t t=x0;x0=x1;x1=t;t=y0;y0=y1;y1=t;}
    float a,b;if((float)x0>=x){a=1;b=0;}else if((float)x1<=x){a=0;b=1;}else{b=x-(float)x0;a=(float)x1-x;}
    float total=b+a;if(total==0)return (int32_t)((uint32_t)y0+(uint32_t)y1)/2;
    float p=a*(float)y0,q=b*(float)y1;return fs((q+p)/total);
}
static void bracket_u(const unsigned char *p,unsigned n,unsigned stride,uint32_t value,const unsigned char **a,const unsigned char **b){
    *a=p;*b=p+stride*(n-1);if(u32(*a)>=value)*b=*a;else if(u32(*b)<=value)*a=*b;
    else{*b=p+stride;for(unsigned i=1;i<n;++i){if(u32(p+stride*i)>=value){*b=p+stride*i;*a=*b-stride;return;}}}
}
static void bracket_f(const unsigned char *p,unsigned n,unsigned stride,float value,int half,const unsigned char **a,const unsigned char **b){
    *a=p;*b=p+stride*(n-1);float lo=half?(float)u16(*a):(float)u32(*a),hi=half?(float)u16(*b):(float)u32(*b);
    if(lo>=value)*b=*a;else if(hi<=value)*a=*b;
    else{*a=*b=p;for(unsigned i=1;i<n;++i){*b=p+stride*i;float q=half?(float)u16(*b):(float)u32(*b);if(q>=value)return;*a=*b;}}
}
static void bracket_s(const unsigned char *p,unsigned n,unsigned stride,int32_t value,const unsigned char **a,const unsigned char **b){
    *a=p;*b=p+stride*(n-1);if((int32_t)u32(*a)>=value)*b=*a;else if((int32_t)u32(*b)<=value)*a=*b;
    else{*b=p+stride;for(unsigned i=1;i<n;++i)if((int32_t)u32(p+stride*i)>=value){*b=p+stride*i;*a=*b-stride;return;}}
}
static void integer_distance(const unsigned char *row,int32_t value,uint32_t out[2]){
    const unsigned char *a,*b;bracket_s(row+8,row[4],12,value,&a,&b);
    if(a==b){out[0]=u32(a+4);out[1]=u32(a+8);return;}
    uint32_t wa=u32(b)-(uint32_t)value,wb=(uint32_t)value-u32(a),den=u32(b)-u32(a);
    for(unsigned ch=0;ch<2;++ch)out[ch]=(uint32_t)sd(u32(a+4+4*ch)*wa+u32(b+4+4*ch)*wb,den);
}
uint32_t hb_atmosphere_ev_row(const unsigned char *p,uint32_t ct,int32_t tint,uint32_t *r,uint32_t *b){
    const unsigned char *a,*z;bracket_u(p+8,p[4],104,ct,&a,&z);uint32_t av[2],bv[2];integer_distance(a,tint,av);integer_distance(z,tint,bv);
    *r=hb_scene_interpolate(u32(a),u32(z),av[0],bv[0],(float)ct);*b=hb_scene_interpolate(u32(a),u32(z),av[1],bv[1],(float)ct);return 0;
}
static uint32_t ev_gains(const unsigned char *p,unsigned n,uint32_t ct,float ev,float tint,uint32_t *r,uint32_t *b){
    if(!n)return 0;const unsigned char *a,*z;bracket_f(p+4,n,1568,ev,0,&a,&z);
    uint32_t ar,ab,zr,zb,st=hb_atmosphere_ev_row(a,ct,fs(tint),&ar,&ab);if(st)return st;
    st=hb_atmosphere_ev_row(z,ct,fs(tint),&zr,&zb);if(st)return st;
    /* Brackets read uint32 EV knots, but the final interpolation reads bytes. */
    *r=hb_scene_interpolate(a[0],z[0],ar,zr,ev);*b=hb_scene_interpolate(a[0],z[0],ab,zb,ev);return 0;
}
uint32_t hb_atmosphere_gains(const unsigned char *p,uint32_t ct,float ev,float tint,uint32_t *r,uint32_t *b){return ev_gains(p,p[0],ct,ev,tint,r,b);}
uint32_t hb_atmosphere_end_value(const unsigned char *p,uint32_t ct,float ev,float tint,uint32_t *r,uint32_t *b){return ev_gains(p,p[2],ct,ev,tint,r,b);}
uint32_t hb_atmosphere_end_gains(const unsigned char *p,uint32_t ct,float end,float ev,float tint,uint32_t *r,uint32_t *b){
    if(!p[0])return 0;const unsigned char *a,*z;bracket_f(p+4,p[0],0x3104,end,1,&a,&z);
    if(!a[2]||!z[2])return HB_PREP_UNSUPPORTED;
    uint32_t ar,ab,zr,zb,st=hb_atmosphere_end_value(a,ct,ev,tint,&ar,&ab);if(st)return st;
    st=hb_atmosphere_end_value(z,ct,ev,tint,&zr,&zb);if(st)return st;
    *r=hb_scene_interpolate(u16(a),u16(z),ar,zr,end);*b=hb_scene_interpolate(u16(a),u16(z),ab,zb,end);return 0;
}
uint32_t hb_atmosphere_category_distance(const unsigned char *ctx,uint32_t slot,const unsigned char *p,uint32_t *r,uint32_t *b){
    int32_t tint=fs(rf(ctx+0x841c4+(slot&255)*0x74));const unsigned char *a,*z;bracket_s(p+8,p[4],12,tint,&a,&z);
    int32_t red=hb_atmosphere_interpolate_signed((int32_t)u32(a),(int32_t)u32(z),(int32_t)u32(a+4),(int32_t)u32(z+4),(float)tint);
    int32_t blue=hb_atmosphere_interpolate_signed((int32_t)u32(a),(int32_t)u32(z),(int32_t)u32(a+8),(int32_t)u32(z+8),(float)tint);
    if(red<0||blue<0)return 168;*r=(uint32_t)red;*b=(uint32_t)blue;return 0;
}
uint32_t hb_atmosphere_category_ct(const unsigned char *ctx,uint32_t slot,const unsigned char *p,uint32_t *r,uint32_t *b){
    uint32_t ct=u32(ctx+0x841bc+(slot&255)*0x74);const unsigned char *a,*z;bracket_u(p+8,p[4],104,ct,&a,&z);
    uint32_t ar,ab,zr,zb,st=hb_atmosphere_category_distance(ctx,slot,a,&ar,&ab);if(st)return st;
    st=hb_atmosphere_category_distance(ctx,slot,z,&zr,&zb);if(st)return st;
    *r=hb_scene_interpolate(u32(a),u32(z),ar,zr,(float)ct);*b=hb_scene_interpolate(u32(a),u32(z),ab,zb,(float)ct);return 0;
}
uint32_t hb_atmosphere_category_ev(const unsigned char *ctx,uint32_t slot,const unsigned char *p,uint32_t *r,uint32_t *b){
    uint32_t ev=ctx[0x3761c];const unsigned char *a,*z;bracket_u(p+8,p[4],1568,ev,&a,&z);
    uint32_t ar,ab,zr,zb,st=hb_atmosphere_category_ct(ctx,slot,a,&ar,&ab);if(st)return st;
    st=hb_atmosphere_category_ct(ctx,slot,z,&zr,&zb);if(st)return st;
    *r=hb_scene_interpolate(u32(a),u32(z),ar,zr,(float)ev);*b=hb_scene_interpolate(u32(a),u32(z),ab,zb,(float)ev);return 0;
}
static void refresh(unsigned char *ctx,unsigned slot){
    size_t m=slot*0x74;uint32_t r=u32(ctx+0x84168+m),b=u32(ctx+0x84170+m),ct=hb_scene_temperature(ctx,r,b);
    w32(ctx+0x841bc+m,ct);wf(ctx+0x841c4+m,(float)hb_temperature_distance(ctx,ct,r,b));
}
static uint32_t temperature_gate(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model,unsigned slot,uint32_t *ct,float *tint,int *enabled){
    size_t m=slot*0x74;uint32_t mode=slot>=2?u32(cfg+0x10294+slot*0x2bd0):0;*enabled=0;
    if(mode){float temp;uint32_t st=hb_temperature_compute(ctx,cfg,model,mode,u32(ctx+0x84168+m),4096,u32(ctx+0x84170+m),&temp,tint);if(st)return st;
        *ct=fu(temp<2000.0f?2000.0f:temp);ctx[0x178+slot]=0;*enabled=1;return 0;}
    *ct=u32(ctx+0x841bc+m);*tint=rf(ctx+0x841c4+m);
    if(((*ct-2000)>>2)>2024)return 0;
    unsigned row=(*ct-2000)/100;int outside=abs32((uint32_t)fs(*tint))>u32(ctx+0x350+16*row);
    ctx[0x178+slot]=(unsigned char)outside;*enabled=!outside||cfg[0x3c+slot]!=0;return 0;
}
uint32_t hb_atmosphere_process(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model){
    for(unsigned slot=0;slot<4;++slot){size_t m=slot*0x74;if(!ctx[0x84164+m])continue;
        uint32_t ct;float tint;int enabled;uint32_t st=temperature_gate(ctx,cfg,model,slot,&ct,&tint,&enabled);if(st)return st;
        if(enabled){if(!cfg[0x1b1d0+slot*0x3104])return HB_PREP_UNSUPPORTED;
            uint32_t r=4096,b=4096;st=hb_atmosphere_gains(cfg+0x1b1d0+slot*0x3104,ct,rf(ctx+0x37618),tint,&r,&b);if(st)return st;
            w16(ctx+0xa859e +2*slot,(uint16_t)r);w16(ctx+0xa85a6+2*slot,(uint16_t)b);
            w32(ctx+0x84168+m,(u32(ctx+0x84168+m)*r)>>12);w32(ctx+0x84170+m,(u32(ctx+0x84170+m)*b)>>12);}
        if(u16(ctx+0x9c1ac)!=256){refresh(ctx,slot);w16(ctx+0xa8686+2*slot,(uint16_t)u32(ctx+0x841bc+m));
            const unsigned char *p=cfg+0x275e0+slot*0x18850;uint32_t rank=0,selected_r=4096,selected_b=4096;
            for(unsigned cat=0;cat<7;++cat){uint32_t confidence=u16(ctx+0x3da42+2*cat);if(!confidence)continue;
                for(unsigned j=0;j<p[0];++j){const unsigned char *e=p+4+j*0x1884c;uint32_t kind=u32(e);if(kind&0xf8)return 189;if((kind&255)!=cat)continue;
                    const unsigned char *a,*z;bracket_u(e+12,e[8],0x3108,confidence,&a,&z);
                    uint32_t ar,ab,zr,zb;st=hb_atmosphere_category_ev(ctx,slot,a,&ar,&ab);if(st)return st;
                    st=hb_atmosphere_category_ev(ctx,slot,z,&zr,&zb);if(st)return st;
                    uint32_t r=hb_scene_interpolate(u32(a),u32(z),ar,zr,(float)confidence),b=hb_scene_interpolate(u32(a),u32(z),ab,zb,(float)confidence);
                    uint32_t magnitude=(r>4095?r-4096:4096-r)+(b>4095?b-4096:4096-b),score=u32(e+4)*confidence*magnitude;
                    if(score>rank){rank=score;selected_r=r;selected_b=b;ctx[0xa85ae +slot]=(unsigned char)cat;}
                }
            }
            w32(ctx+0x84168+m,(u32(ctx+0x84168+m)*selected_r)>>12);w32(ctx+0x84170+m,(u32(ctx+0x84170+m)*selected_b)>>12);
            w16(ctx+0xa85b2+2*slot,(uint16_t)selected_r);w16(ctx+0xa85ba+2*slot,(uint16_t)selected_b);
        }
        if(ctx[0x990dc]){refresh(ctx,slot);st=temperature_gate(ctx,cfg,model,slot,&ct,&tint,&enabled);if(st)return st;
            if(enabled){uint32_t r=4096,b=4096;st=hb_atmosphere_end_gains(cfg+0x89720,ct,rf(ctx+0x990d8),rf(ctx+0x37618),tint,&r,&b);if(st)return st;
                w32(ctx+0x84168+m,(u32(ctx+0x84168+m)*r)>>12);w32(ctx+0x84170+m,(u32(ctx+0x84170+m)*b)>>12);}
        }
        w16(ctx+0xa868e +2*slot,(uint16_t)u32(ctx+0x84168+m));w16(ctx+0xa8696+2*slot,(uint16_t)u32(ctx+0x84170+m));
    }
    return 0;
}
