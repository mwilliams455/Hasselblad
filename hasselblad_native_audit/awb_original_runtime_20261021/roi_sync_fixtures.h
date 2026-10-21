/* SPDX-License-Identifier: MIT */
#ifndef HB_ROI_SYNC_FIXTURES_H
#define HB_ROI_SYNC_FIXTURES_H
#include "hb_roi_sync.h"
#include <math.h>
#include <string.h>
static void hb_sync_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hb_sync_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hb_sync_wf(void*p,float v){memcpy(p,&v,4);}
/* Private model data is loaded from the initialized oracle, never embedded. */
static void hb_test_sync_model(hb_roi_sync_model*m,uintptr_t bias){
    memset(m,0,sizeof *m);
    const uintptr_t names[]={0x6b35f7,0x6b3654,0x6b365c};
    for(unsigned i=0;i<3;++i)memcpy(m->sensor_names[i],(const void*)(bias+names[i]),7);
    memcpy(m->templates,(const void*)(bias+0x6d1870),sizeof m->templates);
    for(unsigned i=0;i<8;++i){
        m->fixed[i][0]=m->templates[i][0];m->fixed[i][1]=m->templates[i][1];
        m->fixed[i][2]=m->templates[i][2]-m->templates[i][0];m->fixed[i][3]=m->templates[i][3]-m->templates[i][1];
        memcpy(m->fallback[i],(const void*)(bias+0x6c7d00),16);
    }
}
static void hb_test_sync(unsigned char*c,unsigned char*k,const hb_roi_sync_model*m,unsigned t){
    hb_sync_w32(c,4000);hb_sync_w32(c+4,3000);hb_sync_w32(c+0x9c194,4000);hb_sync_w32(c+0x9c198,3000);
    hb_sync_w32(c+0x9c19c,12);hb_sync_w16(k+2,15);k[0x16eae4]=1;k[0x16eae5]=1;c[0x9c184]=1;c[0x990dc]=0;
    memset(c+0xd9a8,0x63,172);c[0xda50]=0;k[0x16eaf0]=6;
    memset(c+0xb2054,0x35,164);c[0xb20f4]=c[0xb2050]=0;
    for(unsigned i=0;i<3;++i){unsigned char*r=c+0xda54+84*i;memset(r,0,84);
        memcpy(r,m->sensor_names[i%3],16);memcpy(r+16,m->sensor_names[(i+1)%3],16);
        hb_sync_w32(r+32,6000);hb_sync_w32(r+36,4000);hb_sync_w32(r+40,6000);hb_sync_w32(r+44,4000);
        hb_sync_wf(r+48,1);hb_sync_wf(r+64,1);hb_sync_wf(r+80,1);
    }
    for(unsigned i=0;i<6;++i){unsigned char*p=k+0x16eaf4+136*i;memset(p,0,136);hb_sync_w32(p,100+i);
        for(unsigned j=0;j<8;++j){hb_sync_w32(p+8+16*j,100+j*37);hb_sync_w32(p+12+16*j,200+i*63);hb_sync_w32(p+16+16*j,9000-j*41);hb_sync_w32(p+20+16*j,8000-i*89);}
    }
    unsigned char*r=c+0xda54;
    if(t==1){hb_sync_wf(r+56,317.25f);hb_sync_wf(r+68,-112.5f);}
    if(t==2){hb_sync_wf(r+52,-.3f);hb_sync_wf(r+60,.2f);}
    if(t==3){hb_sync_wf(r+48,.1f);hb_sync_wf(r+52,1);hb_sync_wf(r+60,-1);hb_sync_wf(r+64,.1f);}
    if(t==4){hb_sync_wf(r+48,-.75f);hb_sync_wf(r+64,-1.25f);}
    if(t==5){hb_sync_w32(r+40,4096);hb_sync_w32(r+44,2048);hb_sync_w32(c,3200);hb_sync_w32(c+4,2400);}
    if(t==6){hb_sync_w32(r+32,2000);hb_sync_w32(r+36,1000);}
    if(t==7){hb_sync_w32(r+32,6003);hb_sync_w32(r+36,4001);hb_sync_w32(c,4001);hb_sync_w32(c+4,3003);hb_sync_w32(c+0x9c194,3999);}
    if(t==8){hb_sync_w32(r+32,UINT32_MAX);hb_sync_w32(r+36,UINT32_MAX);hb_sync_w32(r+40,UINT32_MAX);hb_sync_w32(r+44,UINT32_MAX);}
    if(t==9){hb_sync_wf(r+52,.25f);hb_sync_wf(r+60,-.125f);}
    if(t==10||t==11){unsigned i=t-9;memcpy(c+0xda54+84*i,r,84);memset(r,0,32);if(t==11)memset(c+0xda54+84,0,32);}
    if(t==12)for(unsigned i=0;i<3;++i)memset(c+0xda54+84*i,0,32);
    if(t==13){memcpy(r,m->sensor_names[1],16);memcpy(r+16,m->sensor_names[0],16);}
    if(t==14)hb_sync_w16(k+2,12);
    if(t==15)hb_sync_w32(c+0x9c19c,62);
    if(t==16)hb_sync_w16(k+2,62);
    if(t==17)hb_sync_w16(k+2,15+64);
    if(t>=18&&t<=23){static const float a[]={0,.000009f,.00001f,NAN,INFINITY,-INFINITY};hb_sync_wf(r+48,a[t-18]);}
    if(t>=24&&t<=27){const unsigned a[]={0x9c194,0x9c198,0,4};hb_sync_w32(c+a[t-24],0);}
    if(t>=28&&t<=31)hb_sync_w32(r+32+4*(t-28),0);
    if(t==32)hb_sync_wf(r+52,NAN);
    if(t==33)hb_sync_wf(r+60,NAN);
    if(t==34)hb_sync_wf(r+56,INFINITY);
    if(t==35){hb_sync_wf(r+52,-0.0f);hb_sync_wf(r+60,-0.0f);}
    if(t==36)k[0x16eae5]=2;
    if(t==37){k[0x16eae5]=c[0x9c184]=2;}
    if(t==38){k[0x16eae5]=255;c[0x9c184]=254;}
    if(t==39){hb_sync_w32(c+0x9c19c,104);}
    if(t==40)hb_sync_w32(c+0x9c19c,0);
    if(t==41)k[0x16eae4]=0;
    if(t==42)k[0x16eae4]=2;
    if(t==43)c[0x990dc]=1;
    if(t==44||t==45){hb_sync_w32(c+0x9c19c,0);c[0xda50]=(unsigned char)(t-43);}
    if(t>=46&&t<=51){hb_sync_w32(c+0x9c19c,100+t-46);}
    if(t==52){hb_sync_w32(c+0x9c19c,105);k[0x16eaf0]=5;}
    if(t==53){hb_sync_w32(c+0x9c19c,105);k[0x16eaf0]=0;}
    if(t==54){hb_sync_w32(c+0x9c19c,100);hb_sync_w32(k+0x16eafc,UINT32_MAX);}
    if(t==55){hb_sync_w32(c+0x9c19c,100);hb_sync_w32(k+0x16eafc,9000);hb_sync_w32(k+0x16eb04,100);}
    if(t==56){hb_sync_w32(c+0x9c19c,100);hb_sync_w32(k+0x16eb08,UINT32_MAX);}
    if(t==57){hb_sync_w32(c+0x9c19c,100);hb_sync_w32(k+0x16eaf4+136,100);}
    if(t==58){hb_sync_w32(c+0x9c19c,19);hb_sync_w16(k+2,15);}
    if(t==59){hb_sync_w32(c+0x9c19c,19);hb_sync_w16(k+2,12);}
    if(t==60){hb_sync_w32(r+40,2000);hb_sync_w32(r+44,1000);}
    if(t==61){hb_sync_wf(r+48,1.75f);hb_sync_wf(r+64,.375f);}
    if(t==62){k[0x16eae5]=2;hb_sync_wf(r+48,NAN);}
    if(t==63){k[0x16eae5]=2;hb_sync_wf(r+48,0);}
    if(t>=64){
        for(unsigned j=0;j<6;++j){int v=(int)((t*1237+j*891)%1009)-504;hb_sync_wf(r+48+4*j,(float)v/(j%3==2?1.3f:247.0f));}
        hb_sync_w32(c+0x9c194,1000+(t*71)%7000);hb_sync_w32(c+0x9c198,1000+(t*43)%5000);
        hb_sync_w32(c,1000+(t*19)%6000);hb_sync_w32(c+4,1000+(t*83)%4000);
    }
}
#endif
