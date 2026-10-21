/* SPDX-License-Identifier: MIT */
#ifndef HB_ROI_FIXTURES_H
#define HB_ROI_FIXTURES_H
#include <stdint.h>
#include <string.h>
#include <math.h>
static void hb_roi_w32(void*p,uint32_t x){memcpy(p,&x,4);}
static void hb_roi_wf(void*p,float x){memcpy(p,&x,4);}
static const unsigned hb_roi_pending[]={0x9fa10,0x9fcc4,0xa0390,0xa111c,0xa1ea8,0xa21b4};
static const unsigned hb_roi_stride[]={68,108,108,108,24,24};
static const unsigned hb_roi_xy[]={4,12,12,12,8,8};
static const unsigned hb_roi_conf[]={20,8,8,8,4,4};
static const unsigned hb_roi_box[]={0xd640,0xd4d8,0xd58c,0xd6f4,0xd7a8,0xd85c};
static void hb_test_roi(unsigned char*c,unsigned char*k,unsigned kind,unsigned variant){
    c[0xd900]=1;c[0xd901]=0;c[0xd9a4]=0;c[0xd902]=0;c[0xdb50]=3;c[0xdb51]=5;
    hb_roi_w32(c+0x9c1a0,120);hb_roi_wf(c+0x9c1a4,30);hb_roi_w32(c+0xb20f8,10000);
    for(unsigned j=0;j<6;++j){
        unsigned char*q=k+0x16e5a0+28*j;memset(q,0,28);q[0]=j==kind;
        hb_roi_w32(q+4,variant%3);hb_roi_w32(q+8,50);hb_roi_wf(q+12,1);hb_roi_wf(q+16,.01f);hb_roi_wf(q+20,.01f);hb_roi_wf(q+24,.2f);
        hb_roi_w32(c+hb_roi_pending[j]-4,105);hb_roi_w32(c+hb_roi_pending[j],1);hb_roi_w32(c+hb_roi_pending[j]+4,3);
        memset(c+hb_roi_box[j]-16,0x6b,180);
        for(unsigned i=0;i<8;++i){unsigned char*p=c+hb_roi_pending[j]+8+i*hb_roi_stride[j];memset(p,0,hb_roi_stride[j]);
            hb_roi_wf(p+hb_roi_xy[j],.2f+i*.01f);hb_roi_wf(p+hb_roi_xy[j]+4,.25f);
            hb_roi_wf(p+hb_roi_xy[j]+8,.1f+i*.05f);hb_roi_wf(p+hb_roi_xy[j]+12,.2f+i*.03f);
            if(j==2||j==3||j==5){hb_roi_wf(p+hb_roi_xy[j],.5f);hb_roi_wf(p+hb_roi_xy[j]+4,.5f);}
            if(j==0)hb_roi_w32(p+hb_roi_conf[j],60+i*5);else hb_roi_wf(p+hb_roi_conf[j],.6f+i*.05f);
        }
    }
    unsigned char*q=k+0x16e5a0+28*kind,*p=c+hb_roi_pending[kind]+8,*xy=p+hb_roi_xy[kind];
    if(variant==1)hb_roi_w32(c+hb_roi_pending[kind]+4,0);
    if(variant==2)hb_roi_w32(c+hb_roi_pending[kind],0);
    if(variant==3)hb_roi_w32(c+hb_roi_pending[kind]-4,90);
    if(variant==4)hb_roi_w32(c+hb_roi_pending[kind]-4,89);
    if(variant==5)hb_roi_w32(c+hb_roi_pending[kind]-4,121);
    if(variant==6)hb_roi_w32(c+hb_roi_pending[kind]+4,8);
    if(variant==7)hb_roi_w32(q+8,100);
    if(variant==8)hb_roi_wf(q+16,1);
    if(variant==9)hb_roi_wf(q+20,1);
    if(variant==10)hb_roi_w32(c+hb_roi_pending[kind],255);
    if(variant>=11&&variant<=16){static const uint32_t z[]={0,9999,10000,19999,20000,UINT32_MAX};hb_roi_w32(c+0xb20f8,z[variant-11]);}
    if(variant>=17&&variant<=22){static const float rates[]={0,-0.0f,-30,INFINITY,-INFINITY,NAN};hb_roi_wf(c+0x9c1a4,rates[variant-17]);}
    if(variant>=23&&variant<=25){static const float ages[]={-1,INFINITY,NAN};hb_roi_wf(q+12,ages[variant-23]);}
    if(variant>=26&&variant<=31){static const float insets[]={0,1,-1,2,INFINITY,NAN};hb_roi_wf(q+24,insets[variant-26]);}
    if(variant>=32&&variant<=47){
        hb_roi_w32(c+hb_roi_pending[kind]+4,1);
        static const float values[]={-0.1f,0,1,1.1f,NAN,INFINITY,-INFINITY,0.000001f};
        hb_roi_wf(xy+(variant<40?0:8),values[(variant-32)%8]);
    }
    if(variant==48){hb_roi_w32(c+hb_roi_pending[kind]+4,1);if(!kind)hb_roi_w32(p+hb_roi_conf[kind],50);else hb_roi_wf(p+hb_roi_conf[kind],.5f);}
    if(variant==49){for(unsigned i=1;i<3;++i)memcpy(p+i*hb_roi_stride[kind],p,hb_roi_stride[kind]);}
    if(variant==50){hb_roi_w32(c+hb_roi_pending[kind]+4,1);if(!kind)hb_roi_w32(p+hb_roi_conf[kind],UINT32_MAX);else hb_roi_wf(p+hb_roi_conf[kind],INFINITY);}
    if(variant==51){hb_roi_w32(c+hb_roi_pending[kind]+4,1);if(!kind)hb_roi_w32(p+hb_roi_conf[kind],0);else hb_roi_wf(p+hb_roi_conf[kind],NAN);}
    if(variant==52){q[0]=0;}
    if(variant==53){q[0]=2;}
    if(variant==54){c[0xd900]=0;}
    if(variant==55){c[0xd900]=2;}
    if(variant==56){c[0xd901]=1;}
    if(variant==57){c[0xd901]=2;}
    if(variant==58){hb_roi_wf(c+0x9c1a4,0);hb_roi_w32(c+hb_roi_pending[kind]-4,120);}
    if(variant==59){hb_roi_w32(c+0x9c1a0,5);hb_roi_w32(c+hb_roi_pending[kind]-4,UINT32_MAX-10);}
    if(variant==60){hb_roi_w32(q+4,UINT32_MAX);}
    if(variant==61){hb_roi_w32(c+hb_roi_pending[kind]+4,1);hb_roi_wf(xy,.9f);hb_roi_wf(xy+8,.5f);}
    if(variant==62){hb_roi_wf(q+16,NAN);hb_roi_wf(q+20,NAN);}
    if(variant==63){hb_roi_w32(q+8,UINT32_MAX);}
}
#endif
