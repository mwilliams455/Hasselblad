/* SPDX-License-Identifier: MIT */
#include "hb_history.h"
#include "hb_scene_optimizer.h"
#include "hb_scene_controller.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(unsigned char*p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char*p,uint16_t v){memcpy(p,&v,2);}
static float rf(const unsigned char*p){float v;memcpy(&v,p,4);return v;}
static void wf(unsigned char*p,float v){memcpy(p,&v,4);}
static int32_t fs(double v){return isnan(v)?0:v>=2147483647.0?INT32_MAX:v<=-2147483648.0?INT32_MIN:(int32_t)v;}
static uint32_t fu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int32_t add(int32_t a,int32_t b){return (int32_t)((uint32_t)a+(uint32_t)b);}
static int32_t sub(int32_t a,int32_t b){return (int32_t)((uint32_t)a-(uint32_t)b);}
static int32_t si(const unsigned char*p){return (int32_t)u32(p);}
static int32_t abs32(int32_t v){return v<0?sub(0,v):v;}
static int32_t line(const unsigned char*p,uint32_t r,int toward_zero){
    int32_t product=(int32_t)(u32(p)*r);
    return add(toward_zero?product/4096:product>>12,si(p+4));
}
static void remap(const unsigned char *ctx,uint32_t ct,uint32_t *r,uint32_t *b){
    unsigned i=ct<=2000?0:ct>10000?80:(ct-2000)/100;
    const unsigned char *a=ctx+0x348+16*i,*z=ctx+0x858+16*i;
    float red=(float)*r/(float)u32(a),blue=(float)*b/(float)u32(a+4);
    *r=fu(red*(float)u32(z));*b=fu(blue*(float)u32(z+4));
}
int32_t hb_temperature_distance(const unsigned char *ctx,uint32_t ct,uint32_t r,uint32_t b){
    unsigned i=ct<=2000?0:ct>=10001?80:(ct-2000)/100;
    unsigned lo=i?i-1:0,hi=i?i:1;
    uint32_t ar=u32(ctx+0x348+16*lo),ab=u32(ctx+0x34c+16*lo);
    uint32_t zr=u32(ctx+0x348+16*hi),zb=u32(ctx+0x34c+16*hi);
    uint32_t dy=ab-zb,dx=ar-zr,len2=dy*dy+dx*dx;
    uint32_t numerator=ar*zb-ab*zr+dy*r+(zr-ar)*b;
    return fs((double)(int32_t)numerator/sqrt((double)(int32_t)len2));
}
uint32_t hb_zone_contains(const unsigned char *z,uint32_t r,uint32_t b){
    if(!z||(int32_t)r<si(z)||(int32_t)r>si(z+4)||(int32_t)b<si(z+8)||(int32_t)b>si(z+12))return 247;
    if((int32_t)b>add(line(z+24,r,0),2)||(int32_t)b<sub(line(z+16,r,0),2)||
       (int32_t)b>add(line(z+40,r,0),2)||(int32_t)b<sub(line(z+32,r,0),2))return 247;
    return 246;
}
uint32_t hb_zone_edge(const unsigned char *z,uint32_t r,uint32_t b,int32_t *out){
    *out=0;if(!z)return 247;
    int32_t x=(int32_t)r,y=(int32_t)b,a=si(z),d=si(z+4),v[4];
    if(sub(a,50)>x||add(d,50)<x)return 247;
    v[0]=a>x?sub(add(x,50),a):d<x?add(sub(50,x),d):0;
    a=si(z+8);d=si(z+12);
    if(sub(a,50)>y||add(d,50)<y)return 247;
    v[1]=a>y?sub(add(y,50),a):d<y?add(sub(50,y),d):0;
    for(unsigned j=0;j<2;++j){a=line(z+16+16*j,r,1);d=line(z+24+16*j,r,1);
        /* Unlike the rectangle bounds these two comparisons are strict. */
        if(add(d,50)<=y||sub(a,50)>=y)return 247;
        v[2+j]=a>y?sub(add(y,50),a):d<y?add(sub(50,y),d):0;
    }
    int32_t m=v[0];for(unsigned j=1;j<4;++j)if(v[j]<m)m=v[j];*out=m;return 246;
}
int32_t hb_zone_distance(const unsigned char *z,uint32_t r,uint32_t b){
    int32_t best=0x40000000,edge;
    for(unsigned j=0;j<4;++j){uint32_t x=j<2?u32(z+4*j):r,y=j<2?b:u32(z+4*j);
        if(hb_zone_edge(z,x,y,&edge)==246){int32_t d=add(edge,abs32(sub(j<2?(int32_t)r:(int32_t)b,si(z+4*j))));if(d<best)best=d;}}
    float x=(float)(int32_t)r,y=(float)(int32_t)b;
    for(unsigned j=0;j<4;++j){const unsigned char *p=z+16+8*j;float a=(float)si(p)*0.000244140625f,c=(float)si(p+4);
        float aa=a*a,ax=a*x,den=aa+1.0f;
        float px=((a*y+x)-a*c)/den,py=((ax+aa*y)+c)/den;
        if(hb_zone_edge(z,(uint32_t)fs(px),(uint32_t)fs(py),&edge)==246){
            float e=(ax-y)+c;if(e<0)e=-e;
            int32_t d=fs((double)e/sqrt((double)den)+(double)edge);if(d<best)best=d;
        }
    }
    return best;
}
uint32_t hb_history_zone_count(const unsigned char *ctx,const unsigned char *cfg,uint32_t category,uint32_t subindex,uint32_t n,const unsigned char *zones,uint32_t *out,uint32_t *weighted){
    n&=255;uint32_t count=u32(ctx+0x28),sum=0,hits=0,participating=0;
    int semantic=(subindex&255)==1&&(category&255)==0&&cfg[0x138748]==1;
    for(uint32_t i=0;i<count;++i){const unsigned char *d=ctx+0xf450+40*i;uint32_t r=u32(d),b=u32(d+8);
        if(ctx[0x990dc]==1)remap(ctx,u32(d+12),&r,&b);
        unsigned weight=0,hit=0;
        for(unsigned j=0;j<n;++j){const unsigned char *z=zones?zones+52*j:NULL;
            if(semantic&&ctx[0x3be2c+i]!=2)continue;
            if(hb_zone_contains(z,r,b)==246){if(z[48]>weight)weight=z[48];if(u32(d+20))hit=1;}}
        sum+=weight;hits+=hit;participating+=u32(d+20)!=0;
    }
    uint32_t a=count?(sum<<8)/count:0,b=participating?(hits<<8)/participating:0;
    *out=a<b?b:a;*weighted=a;return 0;
}
static uint32_t curve_values(const unsigned char *p,int32_t distance,uint32_t out[2]){
    unsigned n=p[0];if(!n)return 79;
    unsigned lo=0,hi=0;uint32_t a=1,b=0,den=1;
    int32_t first=si(p+4),last=si(p+4+12*(n-1));
    if(first>=distance){}
    else if(last<=distance){lo=hi=n-1;a=0;b=1;}
    else{hi=1;while(hi+1<n&&si(p+4+12*hi)<distance)++hi;lo=hi-1;
        int32_t lower=si(p+4+12*lo),upper=si(p+4+12*hi);
        a=(uint32_t)sub(upper,distance);b=(uint32_t)sub(distance,lower);den=(uint32_t)sub(upper,lower);
        if((int32_t)a<0||(int32_t)b<0||(int32_t)den<1)return 80;
    }
    for(unsigned ch=0;ch<2;++ch)out[ch]=(u32(p+8+12*lo+4*ch)*a+u32(p+8+12*hi+4*ch)*b)/den;
    return 0;
}
static uint32_t scaled(uint32_t value,uint32_t weight){return (uint32_t)((int32_t)((value-4096)*weight)/256)+4096;}
static void scale_axis(const unsigned char *axis,const unsigned char *weights,unsigned n,unsigned step,float value,float fade,uint32_t out[2]){
    float first=step==1?(float)axis[0]:(float)u16(axis),last=step==1?(float)axis[(n-1)*step]:(float)u16(axis+(n-1)*step);
    if(value<first||value>last){float d=value<first?first-value:value-last;if(d>fade)d=fade;
        unsigned i=value<first?0:n-1;uint32_t weight=u16(weights+2*i);
        for(unsigned ch=0;ch<2;++ch){float a=d*4096.0f,b=(fade-d)*(float)scaled(out[ch],weight);out[ch]=fu((a+b)/fade);}
    }else{unsigned hi=1;while(hi+1<n&&!(value<=(step==1?(float)axis[hi]:(float)u16(axis+2*hi))))++hi;
        unsigned lo=(hi-1)&255;hi&=255;
        uint32_t x=step==1?axis[lo]:u16(axis+2*lo),y=step==1?axis[hi]:u16(axis+2*hi);
        uint32_t weight=hb_scene_interpolate(x,y,u16(weights+2*lo),u16(weights+2*hi),value);
        for(unsigned ch=0;ch<2;++ch)out[ch]=scaled(out[ch],weight);
    }
}
static uint32_t history_tables(const unsigned char *ctx,const unsigned char *p,uint32_t count,uint32_t ct,int32_t distance,uint32_t out[2]){
    const unsigned char *a,*b;uint32_t x=u32(p+500),y=u32(p+1312);
    if(x>=count){a=b=p+504;y=x;}
    else if(y<=count){a=b=p+1316;x=y;}
    else if(u32(p+904)>count){a=p+504;b=p+912;y=u32(p+904);}
    else{a=p+912;x=u32(p+904);if(u32(p+908)<count){b=p+1316;x=u32(p+908);}else{b=a;y=u32(p+908);}}
    unsigned char identity[16]={1};w32(identity+8,4096);w32(identity+12,4096);
    const unsigned char *curves[4];uint32_t w0,w1,den;
    if(u32(p+60)>=ct){curves[0]=curves[2]=identity;curves[1]=a;curves[3]=b;w0=u32(p+60)-ct;w1=500-w0;den=500;}
    else if(u32(p+72)<=ct){curves[0]=a+300;curves[2]=b+300;curves[1]=curves[3]=identity;w1=ct-u32(p+72);w0=500-w1;den=500;}
    else{unsigned lo=ct<u32(p+64)?0:ct<=u32(p+68)?1:2;
        curves[0]=a+100*lo;curves[1]=curves[0]+100;curves[2]=b+100*lo;curves[3]=curves[2]+100;
        den=u32(p+64+4*lo)-u32(p+60+4*lo);w0=u32(p+64+4*lo)-ct;w1=den-w0;}
    uint32_t v[4][2];for(unsigned i=0;i<4;++i){uint32_t st=curve_values(curves[i],distance,v[i]);if(st)return st;}
    for(unsigned ch=0;ch<2;++ch){uint32_t av=den?(v[0][ch]*w0+v[1][ch]*w1)/den:v[0][ch];
        uint32_t bv=den?(v[2][ch]*w0+v[3][ch]*w1)/den:v[3][ch];out[ch]=hb_scene_interpolate(x,y,av,bv,(float)count);}
    scale_axis(p+1,p+10,p[0],1,rf(ctx+0x37618),1.0f,out);
    if(p[26]&&ctx[0x990dc])scale_axis(p+28,p+44,p[26],2,rf(ctx+0x990d8),2.5f,out);
    return 0;
}
uint32_t hb_history_process(unsigned char *ctx,const unsigned char *cfg){
    for(unsigned slot=0;slot<4;++slot){size_t o=slot*0x10188,m=slot*0x74;
        if(ctx[0x4dbcc+o]!=1)continue;
        uint32_t ct=u32(ctx+0x4dc24+o),r=u32(ctx+0x4dbd0+o),b=u32(ctx+0x4dbd8+o);
        w16(ctx+0xa856a+2*slot,(uint16_t)ct);w16(ctx+0xa8572+2*slot,(uint16_t)r);w16(ctx+0xa857a+2*slot,(uint16_t)b);
        int32_t distance=hb_temperature_distance(ctx,ct,r,b);
        w32(ctx+0x4dc4c+o,ct);w32(ctx+0x4dc50+o,(uint32_t)distance);
        if(!slot){w32(ctx+0xf008,ct);w32(ctx+0xf00c,(uint32_t)distance);}
        uint32_t selected[2]={4096,4096},measured[2]={4096,4096};int32_t maximum=0,measured_maximum=0;
        uint32_t count=0,correction[2][2]={{0,0},{0,0}};
        for(unsigned entry=0;entry<cfg[0xa1f44+slot*0x6bc4];++entry){
            const unsigned char *e=cfg+0xa1f48+slot*0x6bc4+entry*0xd78;unsigned cat=e[0];if(cat>6)return 74;
            float weights[2]={256.0f,0};
            for(unsigned subindex=0;subindex<2;++subindex){
                if(subindex){uint32_t confidence=u16(ctx+(cfg[0x138748]==1&&!cat?0x3c230:0x3da42+2*cat));if(confidence<u32(e+4))continue;weights[1]=(float)confidence;}
                const unsigned char *p=e+16+subindex*0x6b4;
                int32_t first=(int8_t)p[1],last=(int8_t)p[p[0]];
                int32_t low=first>=3?first-2:0,high=last>18?21:last+2;
                if(low>ctx[0x3761c]||high<ctx[0x3761c]){weights[subindex]=0;continue;}
                uint32_t upper=u32(p+72)+500;if((upper>>4)>=625)upper=10000;
                uint32_t lower=si(p+60)<2501?2000:u32(p+60)-500;
                if((int32_t)ct<(int32_t)lower||(int32_t)ct>(int32_t)upper){weights[subindex]=0;continue;}
                uint32_t rr=u32(ctx+0xb0c84),bb=u32(ctx+0xb0c8c);unsigned inside=0;uint32_t nearest=200;
                if(ctx[0x990dc]==1)remap(ctx,hb_scene_temperature(ctx,rr,bb),&rr,&bb);
                for(unsigned j=0;j<p[76];++j)if(hb_zone_contains(p+80+52*j,rr,bb)==246){inside=1;break;}
                if(!inside){rr=u32(ctx+0xb0c4c);bb=u32(ctx+0xb0c54);
                    if(ctx[0x990dc]==1)remap(ctx,hb_scene_temperature(ctx,rr,bb),&rr,&bb);
                    for(unsigned j=0;j<p[76];++j){uint32_t d=(uint32_t)hb_zone_distance(p+80+52*j,rr,bb);if(d<nearest)nearest=d;}
                    if(nearest>=200){weights[subindex]=0;continue;}
                }
                uint32_t weighted;hb_history_zone_count(ctx,cfg,cat,subindex,p[288],p+292,&count,&weighted);
                uint32_t st=history_tables(ctx,p,count,ct,distance,correction[subindex]);if(st)return st;
                if(!inside)for(unsigned ch=0;ch<2;++ch)correction[subindex][ch]=hb_scene_interpolate(0,200,correction[subindex][ch],4096,(float)nearest);
            }
            uint32_t blended[2]={4096,4096};float total=(weights[0]+0.0f)+weights[1];
            if(total!=0)for(unsigned ch=0;ch<2;++ch){float a=(float)correction[0][ch]*weights[0],b=(float)correction[1][ch]*weights[1];
                float v=((a+0.0f)+b)/total;blended[ch]=isnan(v)?0:(uint32_t)(int64_t)((double)v+0.5);}
            int32_t magnitude=add(abs32(sub((int32_t)blended[0],4096)),abs32(sub((int32_t)blended[1],4096)));
            if(magnitude>maximum){maximum=magnitude;memcpy(selected,blended,sizeof selected);ctx[0x4dc3c+o]=(unsigned char)entry;w32(ctx+0x4dc40+o,count);
                ctx[0xa8582+slot]=(unsigned char)entry;w16(ctx+0xa8586+2*slot,(uint16_t)count);w16(ctx+0xa858e +2*slot,(uint16_t)blended[0]);w16(ctx+0xa8596+2*slot,(uint16_t)blended[1]);}
            if(e[12]==1&&magnitude>measured_maximum){measured_maximum=magnitude;memcpy(measured,blended,sizeof measured);}
        }
        /* Products wrap at 32 bits before the fixed-point shift. */
        uint32_t red=(r*selected[0])>>12,blue=(b*selected[1])>>12;
        uint32_t rawr=u32(ctx+0x4dbdc+o),rawb=u32(ctx+0x4dbe4+o);
        uint32_t mr=(rawr*measured[0])>>12,mb=(rawb*measured[1])>>12;
        w32(ctx+0x84168+m,red);w32(ctx+0x8416c+m,4096);w32(ctx+0x84170+m,blue);
        w32(ctx+0x84180+m,rawr);w32(ctx+0x84184+m,4096);w32(ctx+0x84188+m,rawb);
        w32(ctx+0x84174+m,mr);w32(ctx+0x84178+m,4096);w32(ctx+0x8417c+m,mb);
        uint32_t result=hb_scene_temperature(ctx,red,blue);w32(ctx+0x841bc+m,result);
        distance=hb_temperature_distance(ctx,result,red,blue);wf(ctx+0x841c4+m,(float)distance);
        w32(ctx+0x4dc44+o,result);w32(ctx+0x4dc48+o,(uint32_t)distance);
        if(!slot){w32(ctx+0xf000,result);w32(ctx+0xf004,(uint32_t)distance);ctx[0xeff8]=ctx[0x4dc3c];w32(ctx+0xeffc,u32(ctx+0x4dc40));}
        w16(ctx+0xa865e +2*slot,(uint16_t)red);w16(ctx+0xa8666+2*slot,(uint16_t)blue);w16(ctx+0xa866e +2*slot,(uint16_t)result);wf(ctx+0xa8676+4*slot,(float)distance);
        result=hb_scene_temperature(ctx,mr,mb);w32(ctx+0x841c0+m,result);
        distance=hb_temperature_distance(ctx,result,mr,mb);wf(ctx+0x841c8+m,(float)distance);ctx[0x84164+m]=1;
    }
    return 0;
}
