/* SPDX-License-Identifier: MIT */
#include "hb_roi_sync.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static uint32_t unsigned_conversion(float v){
    if(!(v>0))return 0;if(v>=4294967296.0f)return UINT32_MAX;return (uint32_t)v;
}
static unsigned model_supported(const unsigned char*c,const hb_roi_sync_model*m){
    if(!m)return 0;
    for(unsigned i=0;i<3;++i){
        if(!memchr(m->sensor_names[i],0,16))return 0;
        if(!memchr(c+0xda54+84*i,0,16)||!memchr(c+0xda64+84*i,0,16))return 0;
    }return 1;
}
static const char*name(uint32_t id,const hb_roi_sync_model*m){
    return id==12?m->sensor_names[0]:id==15?m->sensor_names[1]:id==19?m->sensor_names[2]:NULL;
}
static unsigned matches(const char*n,const unsigned char*r){return !strcmp(n,(const char*)r)||!strcmp(n,(const char*)r+16);}
static void write_boxes(unsigned char*c,const float*boxes,uint32_t active){
    for(unsigned i=0;i<8;++i){w32(c+0xd9b0+4*i,active);memcpy(c+0xd9d0+16*i,boxes+4*i,16);}
}
uint32_t hb_roi_sync_matrix(unsigned char*c,const unsigned char*k,const hb_roi_sync_model*m){
    if(!c||!k||!model_supported(c,m))return HB_PREP_UNSUPPORTED;
    uint32_t iw=u32(c+0x9c194),ih=u32(c+0x9c198),ow=u32(c),oh=u32(c+4);
    if(!iw||!ih||!ow||!oh)return UINT32_MAX;
    const char*source=name(u32(c+0x9c19c),m),*target=name(u16(k+2)&63,m);
    if(!source||!target)return UINT32_MAX;
    const unsigned char*r=NULL;
    for(unsigned i=0;i<3;++i){const unsigned char*p=c+0xda54+84*i;if(matches(source,p)&&matches(target,p)){r=p;break;}}
    if(!r)return UINT32_MAX;
    uint32_t aw=u32(r+32),ah=u32(r+36),nw=u32(r+40),nh=u32(r+44);
    if(!aw||!ah||!nw||!nh)return UINT32_MAX;
    float h[6];for(unsigned i=0;i<6;++i)h[i]=f32(r+48+4*i);
    if(fabsf(h[0])<0.00001f)return UINT32_MAX;
    if(k[0x16eae5]>c[0x9c184]){write_boxes(c,&m->fixed[0][0],1);return 0;}
    uint32_t dx=unsigned_conversion((float)(aw>>1)-(float)(iw>>1));
    uint32_t dy=unsigned_conversion((float)(ah>>1)-(float)(ih>>1));
    float low[2],span[2],norm[2]={(float)nw,(float)nh},output[2]={(float)ow,(float)oh};
    float crop[2]={(float)unsigned_conversion((float)(nw>>1)-(float)(ow>>1)),(float)unsigned_conversion((float)(nh>>1)-(float)(oh>>1))};
    float x0=(float)dx,y0=(float)dy,x1=(float)(aw-dx),y1=(float)(ah-dy);
    /* Preserve the original pairwise extrema, rather than replacing them
     * with a different four-corner bounding-box algorithm. */
    low[0]=fminf(h[2]+(h[0]*x0+h[1]*y0),h[2]+(h[0]*x0+h[1]*y1))/norm[0];
    low[1]=fminf(h[5]+(h[3]*x0+h[4]*y0),h[5]+(h[3]*x1+h[4]*y0))/norm[1];
    span[0]=fmaxf(h[2]+(h[0]*x1+h[1]*y0),h[2]+(h[0]*x1+h[1]*y1))/norm[0]-low[0];
    span[1]=fmaxf(h[5]+(h[3]*x0+h[4]*y1),h[5]+(h[3]*x1+h[4]*y1))/norm[1]-low[1];
    for(unsigned i=0;i<8;++i){w32(c+0xd9b0+4*i,1);
        for(unsigned axis=0;axis<2;++axis){
            float lo=((span[axis]*m->templates[i][axis]+low[axis])*norm[axis]-crop[axis])/output[axis];
            float hi=((span[axis]*m->templates[i][axis+2]+low[axis])*norm[axis]-crop[axis])/output[axis];
            wf(c+0xd9d0+16*i+4*axis,lo);wf(c+0xd9d8+16*i+4*axis,hi-lo);
        }
    }return 0;
}
uint32_t hb_roi_sync_calculate(unsigned char*c,const unsigned char*k,const hb_roi_sync_model*m){
    if(!c||!k||!model_supported(c,m)||k[0x16eaf0]>6)return HB_PREP_UNSUPPORTED;
    uint32_t id=u32(c+0x9c19c);
    if(id&&k[0x16eae4]){
        if(hb_roi_sync_matrix(c,k,m)==0){c[0xda50]=1;w16(c+0xd9a8,1);return 0;}
        for(unsigned i=0;i<k[0x16eaf0];++i){const unsigned char*p=k+0x16eaf4+136*i;
            if(u32(p)!=id)continue;
            for(unsigned j=0;j<8;++j){uint32_t x=u32(p+8+16*j),y=u32(p+12+16*j),right=u32(p+16+16*j),bottom=u32(p+20+16*j);
                w32(c+0xd9b0+4*j,1);wf(c+0xd9d0+16*j,(float)x/10000.0f);wf(c+0xd9d4+16*j,(float)y/10000.0f);
                wf(c+0xd9d8+16*j,(float)(right-x)/10000.0f);wf(c+0xd9dc+16*j,(float)(bottom-y)/10000.0f);
            }c[0xda50]=1;w16(c+0xd9a8,1);return 0;
        }
    }
    write_boxes(c,&m->fallback[0][0],0);return 0;
}
uint32_t hb_roi_sync_process(unsigned char*c,const unsigned char*k,const hb_roi_sync_model*m){
    if(!c||!k)return HB_PREP_UNSUPPORTED;
    unsigned active=k[0x16eae4]==1&&!c[0x990dc];
    if(active&&(!model_supported(c,m)||k[0x16eaf0]>6))return HB_PREP_UNSUPPORTED;
    c[0xd9ac]=k[0x16eae4];w16(c+0xd9a8,0);if(!active)return 0;
    uint32_t status=hb_roi_sync_calculate(c,k,m);if(status)return status;
    if(c[0xda50]==1){memcpy(c+0xb2054,c+0xd9b0,164);c[0xda50]=0;c[0xb20f4]=c[0xb2050]=1;}
    return 0;
}
