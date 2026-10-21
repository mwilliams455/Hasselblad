/* SPDX-License-Identifier: MIT -- generated test fixtures, no vendor tables. */
#ifndef HB_USER_MANUAL_FIXTURES_H
#define HB_USER_MANUAL_FIXTURES_H
#include <stdint.h>
#include <string.h>
static void hb_manual_w32(void*p,uint32_t x){memcpy(p,&x,4);}
static void hb_manual_w16(void*p,uint16_t x){memcpy(p,&x,2);}
static void hb_manual_wf(void*p,float x){memcpy(p,&x,4);}
static void hb_test_manual_tables(unsigned char*c,unsigned char*k,unsigned t){
    k[0x16e649]=2;
    for(unsigned g=0;g<2;++g){unsigned char*p=k+0x16e64c+260*g;memset(p,0,260);p[0]=(unsigned char)(g?16:4);p[1]=(unsigned char)(1+t%8);
        for(unsigned i=0;i<8;++i){unsigned char*q=p+4+32*i;hb_manual_w32(q,1+2*i+(t%5==0?256:0));q[4]=(unsigned char)(1+t%2);
            for(unsigned j=0;j<2;++j){hb_manual_w32(q+8+12*j,j?9000:1000);hb_manual_w32(q+12+12*j,4096+g*137+i*49+j*241);hb_manual_w32(q+16+12*j,4096+g*43+i*17+j*151);}}}
    k[0x16e940]=(unsigned char)(1+t%8);c[0x27a]=(unsigned char)(1+t%2);c[0x27b]=173;
    for(unsigned i=0;i<8;++i){unsigned char*p=k+0x16e942+52*i;memset(p,0,52);hb_manual_w16(p,(uint16_t)(-30+10*(int)i));p[2]=(unsigned char)(1+(t/8)%8);p[3]=149;
        for(unsigned j=0;j<8;++j){hb_manual_w16(p+4+6*j,(uint16_t)(1+2*j));hb_manual_w16(p+6+6*j,(uint16_t)(4096+i*73+j*47));hb_manual_w16(p+8+6*j,(uint16_t)(4096+i*31+j*71));}
        if(i<2){memcpy(c+0x27c+52*i,p,52);hb_manual_w16(c+0x27c+52*i,(uint16_t)(i?9000:1000));}}
    hb_manual_w32(c+0x1bc,t%3==0?0xffff1388:1000+100*t);hb_manual_wf(c+0x990d4,(float)(t%24));hb_manual_wf(c+0x990d8,(float)(t%20)-2.5f);hb_manual_wf(c+0x990e0,(float)(t%70)-40.5f);
}
static void hb_test_manual_request(unsigned char*c,unsigned char*k,unsigned t){
    hb_test_manual_tables(c,k,t);c[0x24c]=(unsigned char)(t&1);c[0x278]=(unsigned char)((t>>1)&1);c[0x2f4]=(unsigned char)((t>>2)&1);
    hb_manual_w16(c+0xb14f4,(uint16_t)(1+t%64));c[0xb14f2]=(unsigned char)(t%3);c[0xb0ff0]=71;hb_manual_w32(c+0x28,64);hb_manual_w32(c+0xb0ff4,1500+t*103);
    c[0x1a0]=(unsigned char)(t%3);
    for(unsigned j=0;j<2;++j){hb_manual_w32(c+0x1a4+12*j,j?8000:2000);hb_manual_w32(c+0x1a8+12*j,4096+j*149);hb_manual_w32(c+0x1ac+12*j,4096+j*71);}
    for(unsigned i=0;i<64;++i){hb_manual_w16(c+0xb14f6+2*i,(uint16_t)(t%9==0?64+i:t%9==1?65535:t%9==2?0:i));unsigned char*p=c+0x84f48+20*i;
        hb_manual_w32(p,t%11==0?0:3500+i*53+t);hb_manual_w32(p+8,t%13==0?0:4200+i*31+t);hb_manual_w32(p+16,t%17==0?0:1+i%7);}
    if(t%16==0)hb_manual_w16(c+0xb14f4,0);
    if(t%16==1){c[0x24c]=2;c[0x278]=255;c[0x2f4]=3;}
    if(t%16==2){for(unsigned i=0;i<64;++i){hb_manual_w32(c+0x84f48+20*i,0xffffffff);hb_manual_w32(c+0x84f50+20*i,0x80000000);}}
    if(t%16==3){hb_manual_w32(c+0x1a8,0);hb_manual_w32(c+0x1b4,0);c[0x1a0]=2;}
}
#endif
