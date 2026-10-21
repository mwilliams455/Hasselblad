/* SPDX-License-Identifier: MIT */
#include "hb_parsing.h"
#include "hb_stat_prepare.h"
#include "hb_history.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t cvtu(double v){if(!(v>0))return 0;if(v>=4294967296.0)return UINT32_MAX;return (uint32_t)v;}
static uint32_t interp(uint32_t a,uint32_t b,uint32_t x,uint32_t y,float t,unsigned sort){
    if(sort&&a>=b){uint32_t z=a;a=b;b=z;z=x;x=y;y=z;}
    float p,q;if((float)a>=t){p=0;q=1;}else if((float)b<=t){p=1;q=0;}else{p=t-(float)a;q=(float)b-t;}
    float d=p+q;if(sort&&d==0)return (x+y)>>1;return cvtu((p*(float)y+q*(float)x)/d);
}
static unsigned supported(const unsigned char*c,const unsigned char*k){
    if(u32(c+0x18)>1024||u32(c+0x1c)>1024||(uint64_t)u32(c+0x18)*u32(c+0x1c)>1024||u32(c+0x28)>1024)return 0;
    for(unsigned i=0;i<7;++i)if(k[0x1394d0+164*i]<1||k[0x1394d0+164*i]>8)return 0;
    if(k[0x138774]==1)for(unsigned i=0;i<6;++i){const unsigned char*r=k+0x138778+488*i;
        if(r[1]>4||r[212]>8)return 0;for(unsigned j=0;j<r[212];++j)if(r[215+34*j]>8)return 0;}
    return 1;
}
static void remap(const unsigned char*c,uint32_t ct,uint32_t*r,uint32_t*b){
    unsigned i=ct<=2000?0:ct>10000?80:(ct-2000)/100;const unsigned char*a=c+0x348+16*i,*z=c+0x858+16*i;
    *r=cvtu(((float)*r/(float)u32(a))*(float)u32(z));*b=cvtu(((float)*b/(float)u32(a+4))*(float)u32(z+4));
}
static uint32_t weight_curve(const unsigned char*r,uint16_t value){
    const unsigned char*a=r+2,*b=r+4*r[1]-2;
    if(u16(a)>=value)b=a;else if(u16(b)<=value)a=b;
    else for(unsigned j=1;j<r[1];++j)if(u16(r+2+4*j)>value){b=r+2+4*j;a=b-4;break;}
    return interp(u16(a),u16(b),u16(a+2),u16(b+2),(float)value,0);
}
static uint32_t adjusted_weights(unsigned char*c,const unsigned char*k){
    uint32_t n=u32(c+0x28),width=u32(c+0x18),height=u32(c+0x1c);
    for(unsigned kind=0;kind<6;++kind){const unsigned char*r=k+0x138778+488*kind;
        for(unsigned i=0;i<n;++i){const unsigned char*d=c+0xf450+40*i;uint32_t red=u32(d),blue=u32(d+8);
            if(c[0x990dc]==1)remap(c,u32(d+12),&red,&blue);
            for(unsigned z=0;z<r[1];++z){unsigned char*mask=c+0x3c242+n*kind+i;if(hb_zone_contains(r+4+52*z,red,blue)==246){*mask=1;break;}*mask=0;}
        }
    }
    for(uint32_t y=0;y<height;++y)for(uint32_t x=0;x<width;++x){uint32_t i=y*width+x,total=0;
        for(unsigned kind=1;kind<7;++kind){uint32_t idx=n*kind+i;uint16_t weight=u16(c+0x9c20a+2*idx);const unsigned char*r=k+0x138778+488*(kind-1);
            if(!weight||r[0]!=1)continue;unsigned sum=0,count=0;
            for(int dy=-2;dy<=2;++dy)if((uint32_t)(y+dy)<height)for(int dx=-2;dx<=2;++dx)if((uint32_t)(x+dx)<width){sum+=c[0x3c242+n*(kind-1)+(y+dy)*width+x+dx];++count;}
            uint16_t density=count?(sum<<8)/count:0;unsigned rows=r[212];if(!rows)return 177;
            const unsigned char*a=r+214,*b=a+34*(rows-1);if(density<=a[0])b=a;else if(density>=b[0])a=b;
            else for(unsigned j=1;j<rows;++j)if(density<r[214+34*j]){b=r+214+34*j;a=b-34;break;}
            if(!a[1]||!b[1])return 177;
            uint32_t factor=interp(a[0],b[0],weight_curve(a,weight),weight_curve(b,weight),(float)density,0);
            uint32_t scaled=(factor*(uint32_t)weight)>>8;w16(c+0x3862c+2*idx,scaled);total=(uint16_t)total+scaled;
        }
        uint16_t original=u16(c+0x9c20a+2*i),rest=256-total;w16(c+0x3862c+2*i,rest>original?rest:original);
    }
    return 0;
}
static void classify(unsigned char*c){
    uint32_t n=u32(c+0x28),area=u32(c+0x18)*u32(c+0x1c);
    for(unsigned i=0;i<area;++i){unsigned best=0;uint16_t maximum=u16(c+0x3862c+2*i);
        for(unsigned j=1;j<7;++j){uint16_t v=u16(c+0x3862c+2*(n*j+i));if(v>maximum){maximum=v;best=j;}}
        c[0x3be2c+i]=best;w16(c+0x3c22c+2*best,u16(c+0x3c22c+2*best)+1);
    }
    if(n)for(unsigned i=0;i<7;++i)w16(c+0x3c22c+2*i,((uint32_t)u16(c+0x3c22c+2*i)<<8)/n);
    for(unsigned i=0;i<7;++i){unsigned char*s=c+0xc4e0+12*i;uint32_t first,second;uint16_t value=u16(c+0x3c22c+2*i);
        if(s[0]){first=(int32_t)(u32(s+4)*116+(uint32_t)value*12)/128;second=u32(s+8)+(int32_t)((first-u32(s+8))*6)/128;}
        else{first=second=value;s[0]=1;}w32(s+4,first);w32(s+8,second);w16(c+0x3c22c+2*i,second);
    }
}
static void blend(unsigned char*c,const unsigned char*k){
    float exposure=f32(c+0x37618);
    for(unsigned i=0;i<7;++i){const unsigned char*r=k+0x1394d0+164*i;unsigned n=r[0],lo=0,hi=0;
        if(!(exposure<=(float)r[4])){hi=n-1;if(exposure>=(float)r[4+20*hi])lo=hi;
            else if(n>=2){for(hi=1;hi<n;++hi){if(exposure<=(float)r[4+20*hi])break;lo=hi;}if(hi==n){hi=n-1;lo=n-1;}}else lo=hi=0;}
        const unsigned char*a=r+4+20*lo,*b=r+4+20*hi;
        for(unsigned j=0;j<2;++j)w16(c+0x138+8*i+2*j,interp(a[0],b[0],cvtu((double)f32(a+4+4*j)*256.0),cvtu((double)f32(b+4+4*j)*256.0),exposure,1));
    }
    for(unsigned i=0;i<7;++i)for(unsigned j=0;j<4;++j){unsigned char*d=c+0x3c23a+2*j;uint32_t v=((uint32_t)u16(c+0x138+8*i+2*j)*u16(c+0x3c22c+2*i))>>8;w16(d,u16(d)+v);}
    memcpy(c+0xa8656,c+0x3c23a,8);
}
uint32_t hb_parsing_process(unsigned char*c,unsigned char*k){
    if(!c||!k)return HB_PREP_UNSUPPORTED;if(k[0x138748]!=1)return 0;
    if(u32(c+0x18)*u32(c+0x1c)>1024){k[0x138748]=0;return 0;}
    if(!supported(c,k))return HB_PREP_UNSUPPORTED;
    if(k[0x138774]==1){uint32_t status=adjusted_weights(c,k);if(status)return status;}
    else memcpy(c+0x3862c,c+0x9c20a,0x3800);
    classify(c);blend(c,k);return 0;
}
