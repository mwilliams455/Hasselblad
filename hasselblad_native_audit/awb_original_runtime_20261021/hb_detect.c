/* SPDX-License-Identifier: MIT */
#include "hb_detect.h"
#include "hb_history.h"
#include "hb_scene_optimizer.h"
#include "hb_scene_controller.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t fu(double x){return !(x>0)?0:x>=4294967295.0?UINT32_MAX:(uint32_t)x;}
static int32_t fs(double x){return isnan(x)?0:x>=2147483647.0?INT32_MAX:x<=-2147483648.0?INT32_MIN:(int32_t)x;}
static uint32_t divu(uint32_t a,uint32_t b){return b?a/b:0;}
static int32_t divs(uint32_t a,uint32_t b){if(!b)return 0;if(a==0x80000000&&b==UINT32_MAX)return INT32_MIN;return (int32_t)a/(int32_t)b;}
static uint32_t interp(uint32_t a,uint32_t b,uint32_t x,uint32_t y,float t){return hb_scene_interpolate(a,b,x,y,t);}
static int32_t interps(int32_t a,int32_t b,int32_t x,int32_t y,float t){
    if(a>=b){int32_t z=a;a=b;b=z;z=x;x=y;y=z;}
    float p,q;if((float)a>=t){p=0;q=1;}else if((float)b<=t){p=1;q=0;}else{p=t-(float)a;q=(float)b-t;}
    float d=p+q;return d==0?(int32_t)((uint32_t)x+(uint32_t)y)/2:fs((p*(float)y+q*(float)x)/d);
}
static void remap(const unsigned char*c,uint32_t ct,uint32_t*r,uint32_t*b){
    unsigned i=ct<=2000?0:ct>10000?80:(ct-2000)/100;const unsigned char*a=c+0x348+16*i,*z=c+0x858+16*i;
    *r=fu(((float)*r/(float)u32(a))*(float)u32(z));*b=fu(((float)*b/(float)u32(a+4))*(float)u32(z+4));
}
/* Sorted, unsigned-key brackets. Empty tables are handled by each caller. */
static void bracket(const unsigned char*p,unsigned n,unsigned stride,uint32_t x,const unsigned char**a,const unsigned char**b){
    *a=p;*b=p+stride*(n-1);if(u32(*a)>=x)*b=*a;else if(u32(*b)<=x)*a=*b;
    else for(unsigned i=1;i<n;++i)if(u32(p+stride*i)>x){*b=p+stride*i;*a=*b-stride;break;}
}
uint32_t hb_detect_curve(const unsigned char*p,float x,uint32_t*out){
    if(!p||!out||p[0]>8||!isfinite(x))return HB_PREP_UNSUPPORTED;if(!p[0])return 247;
    unsigned n=p[0];uint32_t a,b,v,z;
    if((float)u32(p+16)>x){b=u32(p+16);uint32_t fade=u32(p+4);a=b>fade?b-fade:0;v=u32(p+8);z=u16(p+48);}
    else if((float)u32(p+12+4*n)<x){a=u32(p+12+4*n);b=a+u32(p+4);v=u16(p+46+2*n);z=u32(p+12);}
    else{unsigned hi=1;for(;hi<n;++hi)if((float)u32(p+16+4*hi)>=x)break;
        a=u32(p+12+4*hi);b=u32(p+16+4*hi);v=u16(p+46+2*hi);z=u16(p+48+2*hi);}
    *out=interp(a,b,v,z,x);return 0;
}
static unsigned zone_weight(const unsigned char*z,unsigned n,uint32_t r,uint32_t b){unsigned best=0;for(unsigned j=0;j<n;++j)if(hb_zone_contains(z?z+52*j:NULL,r,b)==246&&z[52*j+48]>best)best=z[52*j+48];return best;}
uint32_t hb_detect_zone_count(const unsigned char*c,const unsigned char*k,unsigned category,unsigned n,const unsigned char*z,unsigned m,const unsigned char*semantic,uint32_t*out,uint32_t*weighted){
    if(!c||!k||!out||!weighted||u32(c+0x28)>1024||n>8||m>8)return HB_PREP_UNSUPPORTED;
    if((category&255)!=3||k[0x138748]!=1)return hb_history_zone_count(c,k,1,0,n,z,out,weighted);
    uint32_t sum[2]={0},hits[2]={0},valid=0,count=u32(c+0x28);
    for(unsigned i=0;i<count;++i){const unsigned char*d=c+0xf450+40*i;uint32_t r=u32(d),b=u32(d+8);if(c[0x990dc]==1)remap(c,u32(d+12),&r,&b);
        unsigned weights[2]={zone_weight(z,n,r,b),c[0x3be2c+i]==1?zone_weight(semantic,m,r,b):0};
        /* A containing zero-weight zone still contributes a valid hit. */
        for(unsigned h=0;h<2;++h){sum[h]+=weights[h];if(!u32(d+20)||(h&&c[0x3be2c+i]!=1))continue;
            const unsigned char*p=h?semantic:z;unsigned size=h?m:n;for(unsigned j=0;j<size;++j)if(hb_zone_contains(p?p+52*j:NULL,r,b)==246){++hits[h];break;}}
        valid+=u32(d+20)!=0;
    }
    uint32_t values[2];for(unsigned h=0;h<2;++h){uint32_t a=divu(sum[h]<<8,count),b=divu(hits[h]<<8,valid);values[h]=a>b?a:b;}
    *out=values[0]>values[1]?values[0]:values[1];*weighted=values[0];return 0;
}
static uint32_t ordinary(const unsigned char*c,const unsigned char*k,unsigned n,const unsigned char*z){uint32_t a,b;hb_history_zone_count(c,k,1,0,n,z,&a,&b);return b;}
static uint32_t adjust_regions(unsigned char*c,const unsigned char*k){
    memcpy(c+0xa852a,c+0x9c1ac,12);
    if(k[0x1348f4]!=1){memcpy(c+0x38620,c+0x9c1ac,12);return 0;}
    uint32_t r=u32(c+0xb0bb0),b=u32(c+0xb0bb8);if(c[0x990dc]==1)remap(c,hb_scene_temperature(c,r,b),&r,&b);
    for(unsigned i=1;i<6;++i){const unsigned char*p=k+0x1348f8+0x4b8*(i-1);uint16_t weight=u16(c+0x9c1ac+2*i);if(!weight||p[0]!=1||!p[1])continue;
        unsigned inside=0;uint32_t distance=200;for(unsigned j=0;j<p[1];++j)if(hb_zone_contains(p+4+52*j,r,b)==246){inside=1;break;}
        if(!inside){for(unsigned j=0;j<p[1];++j){uint32_t d=hb_zone_distance(p+4+52*j,r,b);if(d<distance)distance=d;}if(distance>=200)continue;}
        uint32_t number,weighted;hb_detect_zone_count(c,k,i,p[2],p+212,p[3],p+420,&number,&weighted);
        if(!inside)number=interps(0,200,(int32_t)number,0,(float)distance);
        unsigned n=p[628];if(!n)return 106;const unsigned char*a,*z;bracket(p+632,n,72,number,&a,&z);
        if(!a[4]||!z[4])return 106;uint32_t values[2];const unsigned char*rows[2]={a,z};
        for(unsigned j=0;j<2;++j){const unsigned char*x,*y;bracket(rows[j]+8,rows[j][4],8,weight,&x,&y);values[j]=interp(u32(x),u32(y),u32(x+4),u32(y+4),(float)weight);}
        uint32_t factor=interp(u32(a),u32(z),values[0],values[1],(float)number);w16(c+0x38620+2*i,(factor*weight)>>8);
    }
    uint32_t rest=256;for(unsigned i=1;i<6;++i)rest-=u16(c+0x38620+2*i);uint32_t base=u16(c+0x9c1ac);w16(c+0x38620,rest>base?rest:base);return 0;
}
static void smooth(unsigned char*c){
    memcpy(c+0xa863e,c+0x38620,12);
    for(unsigned i=0;i<6;++i){unsigned char*s=c+0xc374+12*i;uint32_t value=u16(c+0x38620+2*i),first,second;
        if(s[0]){uint32_t product=u32(s+4)*0x7400+value*0xc00;if((int32_t)product<0)product|=127;
            uint32_t old=u32(s+8)<<8,delta=((uint32_t)((int32_t)product>>7)-old)*6;int32_t change=divs(delta,128);
            first=(int32_t)product>>15;second=(int32_t)(old+(uint32_t)change)>>8;
        }else{first=second=value;s[0]=1;}w32(s+4,first);w32(s+8,second);w16(c+0x38620+2*i,second);
    }memcpy(c+0xa864a,c+0x38620,12);
}
static void normalize(unsigned char*p,unsigned n,unsigned fallback,unsigned wrap){
    uint32_t sum=0;for(unsigned i=0;i<n;++i)sum+=u16(p+2*i);if(wrap)sum=(uint16_t)sum;
    if(sum)for(unsigned i=0;i<n;++i)w16(p+2*i,((uint32_t)u16(p+2*i)<<8)/sum);
    else if(fallback<n){memset(p,0,n*2);w16(p+2*fallback,256);}
}
static uint32_t semantic_mix(unsigned char*c,const unsigned char*k,unsigned char*a,unsigned char*b){
    if(k[0x138748]!=1)return 0;const unsigned char*p=k+0x13994c;unsigned n=p[0];if(!n)return 177;
    uint32_t value=u16(b),current=u16(c+0x3c23c);if(value<current){w16(a,u16(c+0x3c23a));w16(b,current);return 0;}
    const unsigned char*x=p+2,*y=p+2+4*(n-1);if(value<=x[0])y=x;else if(value>=y[0])x=y;
    else for(unsigned j=1;j<n;++j)if(value<p[2+4*j]){y=p+2+4*j;x=y-4;break;}
    uint32_t v=interp(x[0],y[0],u16(x+2),u16(y+2),(float)value),first=u16(p+4),last=u16(p+4+4*(n-1));
    current+=divu((200-current)*(v-first),last-first);if(current>=256)current=256;w16(c+0x3c23c,current);w16(c+0x3c23a,256-current);
    if(current>u16(b)){w16(a,u16(c+0x3c23a));w16(b,current);}return 0;
}
static uint32_t blend(unsigned char*c,const unsigned char*k){
    uint32_t count=u32(c+0xc5a0);unsigned char*p=c+(count?0x3da70:0x3da42);
    for(unsigned i=0;i<6;++i)for(unsigned j=0;j<11;++j){float f=f32(c+(j<7?0x90+28*i+4*j:0x30+16*i+4*(j-7)));
        float product=f*(float)u16(c+0x38620+2*i);w16(p+2*j,fs(product+(float)u16(p+2*j)));}
    if(!count){normalize(p+14,4,0,1);normalize(p,7,5,1);}
    memcpy(c+0xa8536,p,8);memcpy(c+0xa853c,p+6,8);memcpy(c+0xa8552,p+14,8);
    uint32_t status=semantic_mix(c,k,p+14,p+16);if(status)return status;
    if(!count){normalize(p+14,4,0,1);memcpy(c+0xa855a,p+14,8);return 0;}
    memcpy(c+0xa855a,p+14,8);
    for(unsigned i=0;i<7;++i)w16(c+0x3da42+2*i,u16(p+2*i)+((count*u16(c+0x3da9e +2*i))>>10));
    normalize(c+0x3da42,7,5,1);uint16_t sum=0;for(unsigned i=0;i<6;++i)sum+=u16(c+0x38620+2*i);
    uint32_t rest=(uint32_t)sum-u16(c+0x38620);
    for(unsigned i=0;i<4;++i)w16(c+0x3da50+2*i,(uint32_t)divs(rest*u16(p+14+2*i),sum)+((count*u16(c+0x3daac+2*i))>>10));
    normalize(c+0x3da50,4,0,1);memcpy(c+0xa8544,c+0x3da42,8);memcpy(c+0xa854a,c+0x3da48,8);memcpy(c+0xa8562,c+0x3da50,8);return 0;
}
static uint32_t outter_count(unsigned char*c,const unsigned char*k,unsigned n,const unsigned char*z,unsigned char*mask){
    uint32_t width=u32(c+0x18),height=u32(c+0x1c),count=u32(c+0x28),sum=0;
    if(width<=32&&height<=32){for(unsigned i=0;i<count;++i){const unsigned char*d=c+0xf450+40*i;uint32_t r=u32(d),b=u32(d+8);if(c[0x990dc]==1)remap(c,u32(d+12),&r,&b);
        unsigned v=k[0x138748]==1&&c[0x3be2c+i]!=2?0:zone_weight(z,n,r,b);sum+=v;mask[i]=v?255:0;}return divu(sum<<8,count);}
    unsigned w=width<32?width:32,h=height<32?height:32;float sy=(float)height/(float)h,sx=(float)width/(float)w,y=-sy;
    for(unsigned row=0;row<h;++row){y=sy+y;int32_t iy=fs(y);if(iy<0)iy=0;if((uint32_t)iy>height)iy=height;float x=-sx;
        for(unsigned col=0;col<w;++col){x=sx+x;int32_t ix=fs(x);if(ix<0)ix=0;if((uint32_t)ix>width)ix=width;unsigned i=width*(uint32_t)iy+(uint32_t)ix;
            const unsigned char*d=c+0xf450+40*i;uint32_t r=u32(d),b=u32(d+8);if(c[0x990dc]==1)remap(c,u32(d+12),&r,&b);
            unsigned v=width*height<=1024&&k[0x138748]==1&&c[0x3be2c+i]!=2?0:zone_weight(z,n,r,b);sum+=v;mask[row*w+col]=v?255:0;}}
    return divu(sum<<8,w*h);
}
uint32_t hb_detect_outter(unsigned char*c,const unsigned char*k){
    if(!c||!k)return HB_PREP_UNSUPPORTED;if(k[0x136548]!=1)return 0;
    if(u32(c+0x28)>1024||u32(c+0x18)>1024||u32(c+0x1c)>1024||(uint64_t)u32(c+0x18)*u32(c+0x1c)>1024||k[0x136549]>1||k[0x13654f]>8)return HB_PREP_UNSUPPORTED;
    if(k[0x136548]!=1)return 0;float ev=f32(c+0x37618);
    for(unsigned i=0;i<k[0x136549];++i){const unsigned char*p=k+0x13654d+420*i;unsigned low=p[0]>1?(p[0]-2)&255:0,high=p[1]+2<24?p[1]+2:24;
        if(ev<(float)low||ev>(float)high)continue;uint32_t v=outter_count(c,k,p[2],p+3,c+0xb1004+1024*i),weight=1024;
        if(ev<(float)p[0])weight=interp(low,p[0],0,1024,ev);else if(ev>(float)p[1])weight=interp(high,p[1],0,1024,ev);
        w32(c+0xb1404+4*i,(uint32_t)(((uint64_t)v*weight)>>10));}return 0;
}
static uint32_t ramp(const unsigned char*p,uint32_t x,unsigned reverse){uint32_t a=u32(p),b=u32(p+4);if(x<a)return reverse?256:0;if(x>b)return reverse?0:256;return interp(a,b,reverse?256:0,reverse?0:256,(float)x);}
static uint32_t optional_curve(const unsigned char*p,float x){uint32_t v=256;if(p[0])hb_detect_curve(p,x,&v);return v;}
static uint32_t optional_zero(const unsigned char*p,uint32_t x){uint32_t v=0;if(p[0])hb_detect_curve(p,(float)x,&v);return v;}
static uint32_t doubled(const unsigned char*c,const unsigned char*k,unsigned n,const unsigned char*p,unsigned fallback){return n?(ordinary(c,k,n,p)&0x7fffff)*2:fallback;}
static uint32_t scheduled(unsigned char*c,const unsigned char*k){
    if(k[0x1366f0]!=1)return 0;
    for(unsigned i=0;i<k[0x1366f2];++i){const unsigned char*p=k+0x1366f4+0xdd0*i;unsigned id=p[0];unsigned char*state=c+4*id;
        uint32_t cadence=u32(state+0xc45c);if(cadence!=p[4]){w32(state+0xc45c,cadence+1);continue;}w32(state+0xc45c,0);
        uint32_t ct=u32(c+0xb0c04);if(ct>10000)ct=10000;if(ct<2000)ct=2000;float ev=f32(c+0x37618);
        uint32_t low=u32(p+60)-300;if(low<2000)low=2000;uint32_t high=u32(p+64)+300;if(high>10000)high=10000;
        uint32_t factors[4];factors[0]=ct<u32(p+60)?interp(low,u32(p+60),0,256,(float)ct):ct>u32(p+64)?interp(high,u32(p+64),0,256,(float)ct):256;
        factors[1]=ev<(float)p[56]?interp(p[56]>1?(p[56]-2)&255:0,p[56],0,256,ev):ev>(float)p[57]?interp(p[57]+2<24?p[57]+2:24,p[57],0,256,ev):256;
        unsigned alternate=u32(c+0xc370)==1&&p[8]==1;
        uint32_t positive=doubled(c,k,p[68],p+72,512),negative=doubled(c,k,p[69],p+488,0);
        factors[2]=ramp(p+(alternate?12:904),positive,0);factors[3]=ramp(p+(alternate?20:912),negative,1);
        for(unsigned j=0;j<4;++j)w32(c+0xc464+16*id+4*j,factors[j]);
        uint32_t combined,final;
        unsigned spectral=(k[0x139e2c]&&k[0x139e2e]&&u32(c+0xc5a0))||k[0x1366f1];
        if(!spectral){if(p[5])combined=final=0;else{uint32_t v=(factors[1]*factors[0])>>8;v=(v*factors[2])>>8;v=(v*factors[3])>>8;combined=final=ramp(p+920,v,0);}}
        else{
            if(!id&&k[0x1366f1]==1)w16(c+0x3da54,u16(c+0x9c1b6));
            uint32_t f[9];f[2]=optional_curve(p+928,(float)fu(f32(c+0xc6d4)));f[3]=optional_curve(p+992,(float)u16(c+0xc6e4));f[4]=optional_curve(p+1056,(float)u16(c+0xc6e6));
            f[6]=optional_curve(p+1120,(float)u16(c+0x3da50));f[7]=optional_curve(p+1184,(float)u16(c+0x3da52));f[8]=optional_curve(p+1248,(float)u16(c+0x3da54));
            f[5]=p[1312]==1?optional_curve(p+1320,(float)u16(c+0xc6e8+2*p[1316])):256;
            positive=doubled(c,k,p[1384],p+1388,512);negative=doubled(c,k,p[1385],p+1804,0);
            f[0]=ramp(p+(alternate?28:2220),positive,0);f[1]=ramp(p+(alternate?36:2228),negative,1);
            for(unsigned j=0;j<9;++j)w32(c+0xc484+36*id+4*j,f[j]);
            uint32_t v=f[3]*f[2]*f[4];v=(v>>8)*f[5];v=(v>>8)*f[6];v=(v>>8)*f[7];v=(v>>8)*f[8];v>>=16;
            uint32_t response=ramp(p+2236,v,0),base=factors[1]*factors[0];
            uint32_t normal=ramp(p+920,(((base*factors[2])>>8)*factors[3])>>16,0);
            uint32_t spectral_weight=ramp(p+920,(((base*f[0])>>8)*f[1])>>16,0);
            uint32_t weight=optional_zero(p+2244,response);combined=(spectral_weight*weight+normal*(256-weight))>>8;
            if(u32(p+44)==1){weight=optional_zero(p+2308,response);v=(response*weight+(256-weight)*combined)>>8;v=(v*(f[3]*factors[1]))>>16;}
            else v=(response*combined)>>8;
            final=ramp(p+2372,v,0);
        }
        unsigned index=u32(state+0xc454);unsigned char*history=c+0xc3bc+60*id;uint32_t sum=u32(state+0xc444)-u32(history+4*index);
        w32(state+0xc444,sum);w32(history+4*index,final);w32(state+0xc434,final);sum+=final;w32(state+0xc444,sum);
        if(sum>=3841){memset(history,0,60);w32(state+0xc444,0);return 131;}
        uint32_t average=sum/15;w32(state+0xc43c,u32(state+0xc44c));w32(state+0xc44c,average);w32(state+0xc454,index+1==15?0:index+1);
        if(p[48]==1)w16(c+0x3da50+2*p[52],average);
        (void)combined;
    }return 0;
}
static uint32_t magnitude(int32_t x){return x<0?0-(uint32_t)x:(uint32_t)x;}
static void modifications(unsigned char*c,const unsigned char*k){
    if(k[0x1366f0]!=1)return;int32_t delta[11]={0};
    for(unsigned i=0;i<k[0x1366f2];++i){const unsigned char*p=k+0x1366f4+0xdd0*i;if(p[2380]!=1)continue;uint32_t value=u32(c+0xc44c+4*p[0]);
        for(unsigned group=0;group<2;++group){const unsigned char*q=p+(group?2804:2384);unsigned base=group?4:0;
            for(unsigned j=0;j<q[0];++j){const unsigned char*r=q+4+104*j;uint32_t id=u32(r);int32_t scale=256,offset=0;
                if(r[4]){const unsigned char*a,*b;bracket(r+8,r[4],12,value,&a,&b);scale=interps(u32(a),u32(b),u32(a+4),u32(b+4),(float)value);offset=interps(u32(a),u32(b),u32(a+8),u32(b+8),(float)value);}
                uint32_t old=u16(c+(group?0x3da42:0x3da50)+2*id);int32_t product=(uint32_t)scale*old+(uint32_t)offset;
                int32_t next=product>-256?product/256:0;int32_t diff=(uint32_t)next-old;
                if((int32_t)magnitude(diff)>(int32_t)magnitude(delta[base+id]))delta[base+id]=diff;
            }
        }
    }
    for(unsigned g=0;g<2;++g){unsigned count=g?7:4,base=g?4:0;unsigned char*p=c+(g?0x3da42:0x3da50);
        for(unsigned i=0;i<count;++i){int32_t v=(uint32_t)delta[base+i]+u16(p+2*i);w16(p+2*i,v<0?0:v);}normalize(p,count,count,0);}
}
static uint32_t hysteresis(unsigned char*c,const unsigned char*k){
    if(k[0x138294]!=1)return 0;int current=(int8_t)c[0xc4cc],previous=current>0?current-1:0,next=current>=3?3:current+1;
    for(unsigned i=0;i<4;++i){const unsigned char*p=k+0x138298+212*i;w16(c+0x3da58+2*i,ordinary(c,k,p[0],p+4));}
    unsigned any=0,last=0;
    for(unsigned i=0;i<4;++i){const unsigned char*p=k+0x1385e8+88*i;uint32_t value=0;for(unsigned j=0;j<4;++j)value+=((uint32_t)u16(p+2*j)*u16(c+0x3da58+2*j))>>8;
        w16(c+0x3da60+2*i,value);if((uint16_t)value>u16(p+8)){w16(c+0x3da68+2*i,1);any=1;}if((uint16_t)value)last=i;
    }
    if(!(any|last))w16(c+0x3da68,1);
    if(c[0xc4ce]==1){uint32_t ticks=u32(c+0xc4dc);if(u16(c+0x3da68+2*current)==1){if(ticks)w32(c+0xc4dc,ticks-1);}
        else{++ticks;w32(c+0xc4dc,ticks);if(ticks>=u16(k+0x1385f4+88*current)){c[0xc4ce]=0;memset(c+0xc4d0,0,16);}}}
    else{
        for(int i=0;i<current;++i)if(u16(c+0x3da68+2*i)==1){w32(c+0xc4d0,u32(c+0xc4d0)+1);break;}
        if(u16(c+0x3da68+2*current)==1)w32(c+0xc4d8,u32(c+0xc4d8)+1);
        for(int i=current+1;i<4;++i)if(u16(c+0x3da68+2*i)==1){w32(c+0xc4d4,u32(c+0xc4d4)+1);break;}
        int selected=-1;if(u32(c+0xc4d8)>=u16(k+0x1385f2+88*current)){c[0xc4ce]=1;w32(c+0xc4dc,0);}
        else{if(u32(c+0xc4d0)>=u16(k+0x1385f2+88*previous))selected=previous;else if(u32(c+0xc4d4)>=u16(k+0x1385f2+88*next))selected=next;
            if(selected>=0){c[0xc4cd]=c[0xc4cc];c[0xc4cc]=selected;if(u16(c+0x3da68+2*selected)==1){c[0xc4ce]=1;w32(c+0xc4dc,0);}else{c[0xc4ce]=0;memset(c+0xc4d0,0,16);}}}
    }
    uint32_t result,status=hb_detect_curve(k+0x138600,(float)u16(c+0x3da54),&result);if(status)return status;w16(c+0x3da54,result);normalize(c+0x3da50,4,4,0);return 0;
}
static unsigned supported(const unsigned char*c,const unsigned char*k){
    if(u32(c+0x28)>1024||u32(c+0x18)>1024||u32(c+0x1c)>1024||(uint64_t)u32(c+0x18)*u32(c+0x1c)>1024)return 0;
    if(k[0x1348f4]==1)for(unsigned i=0;i<5;++i){const unsigned char*p=k+0x1348f8+1208*i;if(p[1]>4||p[2]>4||p[3]>4||p[628]>8)return 0;for(unsigned j=0;j<p[628];++j)if(p[636+72*j]>8)return 0;}
    if(k[0x138748]==1&&k[0x13994c]>8)return 0;
    if(k[0x136548]==1&&(k[0x136549]>1||k[0x13654f]>8))return 0;
    if(k[0x1366f0]==1){if(k[0x1366f2]>2)return 0;for(unsigned i=0;i<k[0x1366f2];++i){const unsigned char*p=k+0x1366f4+3536*i;
        if(p[0]>1||u32(c+0xc454+4*p[0])>14||p[52]>3||p[68]>8||p[69]>8||p[1384]>8||p[1385]>8||p[1316]>7)return 0;
        static const unsigned curves[]={928,992,1056,1120,1184,1248,1320,2244,2308};for(unsigned j=0;j<9;++j)if(p[curves[j]]>8)return 0;
        if(p[2384]>4||p[2804]>7)return 0;for(unsigned g=0;g<2;++g){const unsigned char*q=p+(g?2804:2384);for(unsigned j=0;j<q[0];++j)if(u32(q+4+104*j)>=(g?7:4)||q[8+104*j]>8)return 0;}
    }}
    if(k[0x138294]==1){if(c[0xc4cc]>3||k[0x138600]>8)return 0;for(unsigned i=0;i<4;++i)if(k[0x138298+212*i]>4)return 0;}
    return 1;
}
uint32_t hb_detect_process(unsigned char*c,const unsigned char*k){
    if(!c||!k||!supported(c,k))return HB_PREP_UNSUPPORTED;uint32_t status=adjust_regions(c,k);if(status)return status;smooth(c);status=blend(c,k);if(status)return status;
    status=hb_detect_outter(c,k);if(status)return status;status=scheduled(c,k);if(status)return status;modifications(c,k);return hysteresis(c,k);
}
