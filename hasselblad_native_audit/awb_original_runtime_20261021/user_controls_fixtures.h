/* SPDX-License-Identifier: MIT -- generated test inputs only. */
#ifndef HB_USER_CONTROLS_FIXTURES_H
#define HB_USER_CONTROLS_FIXTURES_H
#include "user_manual_fixtures.h"
static void hb_test_control_request(unsigned char*c,unsigned char*k,unsigned t){
    hb_test_manual_request(c,k,t);c[0x24c]=(unsigned char)(t&1);c[0x278]=(unsigned char)((t>>1)&1);c[0x2f4]=(unsigned char)((t>>2)&1);
    hb_manual_w16(c+0xb14f4,0);c[0xb14f2]=0;c[0xc534]=83;c[0x1a0]=2;
    for(unsigned j=0;j<2;++j){hb_manual_w32(c+0x1a4+12*j,j?8000:2000);hb_manual_w32(c+0x1a8+12*j,4096+j*149);hb_manual_w32(c+0x1ac+12*j,4096+j*71);}
    for(unsigned i=0xb0eb8;i<0xb0ff0;++i)c[i]=(unsigned char)(i*17+t*31);
    for(unsigned i=0;i<81;++i){hb_manual_w32(c+0xd68+16*i,4000+i*23);hb_manual_w32(c+0xd6c+16*i,8000-i*41);hb_manual_wf(c+0x1278+8*i,-10.0f+(float)i*0.25f);}
    uint32_t mode=t%7==6?7:t%2;hb_manual_w32(k+0x18,mode);hb_manual_w32(k+0x1c,mode);hb_manual_w32(k+0x80,t%5==0?0:t%5==1?0xffffffff:1024+t*53);
    static const uint32_t temperatures[]={0,1999,2000,2050,3500,5500,10000,10001,0xffffffff};
    hb_manual_w32(c+0xb14c8,temperatures[t%9]);hb_manual_w32(c+0xb14d0,mode==0?2000+(t%81)*100:temperatures[t%9]);hb_manual_wf(c+0xb14d4,(float)((int)(t%201)-100)/3.0f);
    hb_manual_w32(c+0xb14dc,3500+t*53);hb_manual_w32(c+0xb14e0,4096);hb_manual_w32(c+0xb14e4,4300+t*31);
    c[0xb14c4]=c[0xb14cc]=c[0xb14d8]=1;c[0xb14e8]=1;hb_manual_w32(c+0xb14ec,t%4);hb_manual_w32(c+0x194,(t/4)%4);
    if(t%16==0)c[0xb14c4]=0;if(t%16==1)c[0xb14cc]=2;if(t%16==2)c[0xb14d8]=255;
    if(t%16==3)hb_manual_w32(c+0xb14dc,0);if(t%16==4)hb_manual_w32(c+0xb14e0,0);if(t%16==5)hb_manual_w32(c+0xb14e4,0);
    if(t%16==6){hb_manual_w32(c+0x1a8,0);hb_manual_w32(c+0x1b4,0);}
    if(t%16==7){hb_manual_w32(k+0x18,0);hb_manual_w32(k+0x1c,0);hb_manual_w32(c+0xd68+16*30,0);hb_manual_w32(c+0xb14c8,5000);hb_manual_w32(c+0xb14d0,5000);}
    if(t%16==8){k[0x1332bc]=1;memset(k+0x1332c4,0,36);}
    if(t%16==9){hb_manual_w32(c+0xb14dc,0xffffffff);hb_manual_w32(c+0xb14e0,0x80000000);hb_manual_w32(c+0xb14e4,0x7fffffff);}
    if(t%16==10){for(unsigned i=0;i<2;++i)for(unsigned j=0;j<8;++j)hb_manual_w16(c+0x282+52*i+6*j,0);c[0x278]=1;}
}
static void hb_test_control_failure(unsigned char*c,unsigned char*k,unsigned t){
    hb_test_control_request(c,k,1);c[0xb14c4]=c[0xb14cc]=c[0xb14d8]=1;
    hb_manual_w32(k+0x18,1);hb_manual_w32(k+0x1c,1);hb_manual_w32(c+0xb14c8,5000);hb_manual_w32(c+0xb14d0,5000);hb_manual_wf(c+0xb14d4,0);
    c[0x2f4]=c[0x278]=c[0x24c]=0;hb_manual_wf(c+0x990d8,1);hb_manual_wf(c+0x990e0,20);
    if(t<2){hb_manual_w32(c+0x1a8+4*t,0);hb_manual_w32(c+0x1b4+4*t,0);}
    else if(t<4){c[0x2f4]=1;for(unsigned i=0;i<2;++i)for(unsigned j=0;j<8;++j)hb_manual_w16(k+0x16e948+52*i+6*j+2*(t-2),0);}
    else if(t<6){c[0x278]=1;for(unsigned i=0;i<2;++i)for(unsigned j=0;j<8;++j)hb_manual_w16(c+0x282+52*i+6*j+2*(t-4),0);}
    else{c[0x24c]=1;for(unsigned i=0;i<2;++i)for(unsigned j=0;j<8;++j)for(unsigned q=0;q<2;++q)hb_manual_w32(k+0x16e65c+260*i+32*j+12*q+4*(t-6),0);}
}
#endif
