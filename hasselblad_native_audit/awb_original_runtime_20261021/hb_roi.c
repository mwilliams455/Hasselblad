/* SPDX-License-Identifier: MIT */
#include "hb_roi.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static int32_t signed_conversion(float x){
    if(x!=x)return 0;
    if(x>=2147483648.0f)return INT32_MAX;
    if(x<=-2147483648.0f)return INT32_MIN;
    return (int32_t)x;
}
typedef struct{unsigned pending,record,stride,confidence,xy,box,center;} roi_kind;
static const roi_kind kinds[]={
    {0x9fa10,0x9fa18,68,20,4,0xd640,0},
    {0x9fcc4,0x9fccc,108,8,12,0xd4d8,0},
    {0xa0390,0xa0398,108,8,12,0xd58c,1},
    {0xa111c,0xa1124,108,8,12,0xd6f4,1},
    {0xa1ea8,0xa1eb0,24,4,8,0xd7a8,0},
    {0xa21b4,0xa21bc,24,4,8,0xd85c,1}
};
static void clear_box(unsigned char*p){
    memset(p,0,164);
    for(unsigned i=0;i<8;++i){wf(p+0x28+16*i,1);wf(p+0x2c+16*i,1);}
}
uint32_t hb_roi_reinitialize(unsigned char*c){
    if(!c)return HB_PREP_UNSUPPORTED;
    for(unsigned j=0;j<6;++j){w32(c+kinds[j].pending,0);clear_box(c+kinds[j].box);}
    clear_box(c+0xb2054);clear_box(c+0xef54);clear_box(c+0xd904);
    c[0xb20f4]=c[0xb2050]=1;c[0xd901]=0;return 0;
}
static void rectangle(const unsigned char*p,const roi_kind*d,float*v){
    for(unsigned i=0;i<4;++i)v[i]=f32(p+d->xy+4*i);
    if(d->center){v[0]=v[0]-v[2]*0.5f;v[1]=v[1]-v[3]*0.5f;
        v[0]=v[0]<=0?0:v[0];v[1]=v[1]<=0?0:v[1];}
}
static float overlap(const float*v,float lo,float hi){
    float x=v[0]>=lo?v[0]:lo;x=hi<=x?hi:x;
    float y=v[1]>=lo?v[1]:lo;y=hi<=y?hi:y;
    float right=v[2]+v[0],bottom=v[3]+v[1];
    right=lo>=right?lo:right;right=hi<=right?hi:right;
    bottom=lo>=bottom?lo:bottom;bottom=hi<=bottom?hi:bottom;
    float w=right-x,h=bottom-y;w=w>=0?w:0;h=h>=0?h:0;return w*h;
}
static unsigned valid_rectangle(const float*v){
    for(unsigned i=0;i<4;++i)if(!(v[i]>=0&&v[i]<=1))return 0;
    return (double)(v[2]+v[0])-1<=0.000001 && (double)(v[3]+v[1])-1<=0.000001;
}
static void grid(unsigned char*c,unsigned base,const float*v,float inset,unsigned shifted_bottom){
    float dx=v[2]*inset,dy=v[3]*inset,w=v[2]-dx,h=v[3]-dy;
    float x=(float)((double)dx*0.5+(double)v[0]);
    float y=(float)((double)dy*0.5+(double)v[1]);
    wf(c+base-16,x);wf(c+base-12,y);wf(c+base-8,w);wf(c+base-4,h);
    float cw=w/3.0f,ch=h/3.0f;
    float x0=cw*0.0f+x,y0=ch*0.0f+y,x1=cw+x,x2=(cw+cw)+x;
    float y1=ch+y,y2=(ch+ch)+y;
    float bottom0=shifted_bottom?cw*0.5f+x0:x0;
    float bottom1=shifted_bottom?cw*0.5f+x1:x1;
    const float xs[]={x0,x1,x2,x0,x1,x2,bottom0,bottom1};
    const float ys[]={y0,y0,y0,y1,y1,y1,y2,y2};
    for(unsigned i=0;i<8;++i){w32(c+base+4*i,1);wf(c+base+32+16*i,xs[i]);wf(c+base+36+16*i,ys[i]);wf(c+base+40+16*i,cw);wf(c+base+44+16*i,ch);}
}
uint32_t hb_roi_process(unsigned char*c,const unsigned char*k){
    if(!c||!k)return HB_PREP_UNSUPPORTED;
    if(c[0xd900]!=1)return 0;
    if(c[0xd901]==1)return hb_roi_reinitialize(c);
    for(unsigned j=0;j<6;++j)if(u32(c+kinds[j].pending+4)>8)return HB_PREP_UNSUPPORTED;
    w16(c+0xd4c4,0);
    for(unsigned j=0;j<6;++j){
        const roi_kind*d=kinds+j;const unsigned char*q=k+0x16e5a0+28*j;
        if(!q[0]||u16(c+0xd4c4)==1)continue;
        uint32_t zoom=u32(c+0xb20f8);if(zoom<10000)return 225;
        float scale=(float)(zoom/10000),age=(float)(u32(c+0x9c1a0)-u32(c+d->pending-4))/f32(c+0x9c1a4);
        c[0xdb51]=c[0xdb50];c[0xdb50]=u32(c+d->pending)!=0;clear_box(c+d->box);
        float ttl=f32(q+12);if(age<=ttl)w16(c+0xd4c4,1);
        uint32_t count=u32(c+d->pending+4);
        /* ARM b.le also takes unordered, unlike C's <=. */
        if(u32(c+d->pending)&&count&&!(age>ttl)){
            w32(c+d->pending,0);float lo=(1.0f-1.0f/scale)*0.5f,hi=1.0f-lo,best=0;unsigned selected=0;
            for(unsigned i=0;i<count;++i){
                const unsigned char*p=c+d->record+i*d->stride;
                if(j==0){if(u32(p+d->confidence)<=u32(q+8))continue;}
                else if(!(f32(p+d->confidence)*100.0f>(float)u32(q+8)))continue;
                float v[4];rectangle(p,d,v);
                if(!(v[2]*scale>f32(q+16))||!(v[3]*scale>f32(q+20)))continue;
                float area=overlap(v,lo,hi);if(area>best){best=area;selected=i;}
            }
            const unsigned char*p=c+d->record+selected*d->stride;
            w16(c+0xa8735,j==0?(uint16_t)u32(p+d->confidence):(uint16_t)signed_conversion(f32(p+d->confidence)*100.0f));
            if((double)best>0.000001){float v[4];rectangle(p,d,v);if(valid_rectangle(v))grid(c,d->box,v,f32(q+24),j!=0);}
            w16(c+0xd4c4,1);
        }
        c[d->box+160]=1;memcpy(c+0xd904,c+d->box,164);c[d->box+160]=0;
        c[0xd9a4]=1;c[0xd902]=u32(q+4)==1;
    }
    if(c[0xd9a4]==1){
        if(c[0xd902]==1){memcpy(c+0xef54,c+0xd904,164);c[0xd9a4]=0;c[0xeff4]=1;}
        else{memcpy(c+0xb2054,c+0xd904,164);c[0xd9a4]=0;c[0xb20f4]=c[0xb2050]=1;}
    }
    return 0;
}
