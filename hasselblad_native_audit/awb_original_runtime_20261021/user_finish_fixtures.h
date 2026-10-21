/* SPDX-License-Identifier: MIT -- synthetic test inputs only. */
#ifndef HB_USER_FINISH_FIXTURES_H
#define HB_USER_FINISH_FIXTURES_H
#include <stdint.h>
#include <string.h>
static void hb_finish_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hb_finish_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hb_test_finish_request(unsigned char*c,unsigned t){
    c[0xb1f84]=c[0xb14f0]=c[0xb1cf8]=c[0xb1ff8]=1;
    c[0xb1f85]=(unsigned char)(t*17);c[0xb14f1]=(unsigned char)(t*31);
    c[0xb1ff6]=(unsigned char)(t*7);c[0x42d3]=t%2?c[0xb1ff6]:255;c[0x42d2]=77;
    for(unsigned i=0;i<156;++i)c[0xb1cfc+i]=(unsigned char)(i*13+t*37);
    for(unsigned j=0;j<2;++j)for(unsigned i=1;i<=6;++i)hb_finish_w32(c+0xb1cfc+0x70*j+4*i,4096+t*23+i*71);
    hb_finish_w32(c+0xb1d54,t%2?2000:10000);hb_finish_w32(c+0xb1d58,2000+(t%81)*100);
    hb_finish_w32(c+0xb1ffc,t%2?0:1024);hb_finish_w32(c+0xb2000,0x459c4000); /*5000*/
    hb_finish_w32(c+0xb2004,0xff800000u+t);
    for(unsigned i=0;i<12;++i)hb_finish_w16(c+0xb2008+2*i,(uint16_t)(t%2?256:i));
    unsigned kind=t%64;
    if(kind<12)hb_finish_w32(c+0xb1cfc+0x70*(kind/6)+4+4*(kind%6),0);
    if(kind>=12&&kind<24){static const uint32_t ct[]={0,1999,2000,10000,10001,0xffffffff};hb_finish_w32(c+0xb1d54+4*((kind-12)/6),ct[(kind-12)%6]);}
    if(kind>=24&&kind<36)hb_finish_w16(c+0xb2008+2*(kind-24),257);
    if(kind>=36&&kind<48){static const uint32_t ct[]={0,0x80000000,0x44fa0000,0x461c4000,0x44f9e000,0x461c4400,0x7fc12345,0xffc12345,0x7f800000,0xff800000,1,0xc59c4000};hb_finish_w32(c+0xb2000,ct[kind-36]);}
    if(kind>=48&&kind<52){static const uint32_t counts[]={0,1024,1025,0xffffffff};hb_finish_w32(c+0xb1ffc,counts[kind-48]);}
    if(kind>=52&&kind<56){static const unsigned char flags[]={0,1,2,255};c[0xb1f84]=c[0xb14f0]=c[0xb1cf8]=c[0xb1ff8]=flags[kind-52];}
    if(kind>=56){ /* accepted fixed results with wrapped/zero/nonunity scaling */
        c[0x1a0]=(unsigned char)((kind-56)%3);
        for(unsigned i=0;i<2;++i){hb_finish_w32(c+0x1a4+12*i,i?8000:2000);hb_finish_w32(c+0x1a8+12*i,kind==57?0:kind==58?0xffffffff:4096+t*31);hb_finish_w32(c+0x1ac+12*i,kind==59?0:kind==60?0x80000000:2048+t*17);}
        if(kind==61||kind==62)for(unsigned j=0;j<2;++j)for(unsigned i=1;i<=6;++i)hb_finish_w32(c+0xb1cfc+0x70*j+4*i,kind==61?0xffffffff:0x80000000);
    }
}
#endif
