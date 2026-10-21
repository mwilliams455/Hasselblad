/* SPDX-License-Identifier: MIT -- synthetic statistics only. */
#ifndef HB_STAT_DIFFERENCE_FIXTURES_H
#define HB_STAT_DIFFERENCE_FIXTURES_H
#include <stdint.h>
#include <string.h>
static void hb_diff_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hb_diff_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hb_test_difference(unsigned char*c,unsigned char*k,unsigned char*r,unsigned t){
    static const unsigned counts[]={1,2,3,32,64,1024};
    unsigned n=counts[(t/80)%6],kind=t%80;
    hb_diff_w32(c+0x18,8);hb_diff_w32(c+0x1c,8);hb_diff_w32(c+0x28,n);hb_diff_w32(c+0x2c,0);
    memset(c+0x98f48,0,0x180);c[0xdb60]=0;hb_diff_w32(c+0xeeac,0);
    c[0xef3c]=79;hb_diff_w16(c+0xef3e,0);c[0xd328]=(unsigned char)((t/4)%4);c[0xd329]=(unsigned char)(t%4);c[0xd32a]=0;
    k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;hb_diff_w32(k+0x1531b0,100);
    hb_diff_w32(c+0x9c1a0,t);hb_diff_w32(c+0x9c1a4,0x41f00000); /*30*/
    r[0x1c]=0;r[0x20]=1;r[0x1d]=r[0x22]=0;
    hb_diff_w16(c+0xb6962,0);hb_diff_w32(c+0xb6964,0xfffffffe);c[0xb6960]=0;
    for(unsigned i=0;i<n;++i){
        hb_diff_w32(c+0x84f48+20*i,4096+i%7*83);hb_diff_w32(c+0x84f4c+20*i,4096);hb_diff_w32(c+0x84f50+20*i,5000-i%5*73);c[0x84f58+20*i]=255;
        hb_diff_w32(c+0xf450+40*i,4096+i%7*83);hb_diff_w32(c+0xf458+40*i,5000-i%5*73);
    }
    if(kind<4){k[0x1531a8]=kind<2?0:2;k[0x1531ac]=kind>=2?0:255;hb_diff_w32(c+0x28,0);}
    else if(kind<8){static const unsigned char flags[]={0,1,2,255};r[0x1c]=flags[kind-4];r[0x20]=0;if(kind==5)hb_diff_w32(c+0x28,0);}
    else if(kind<20){hb_diff_w32(c+0x2c,12);c[0x98f48+32*(kind-8)]=(unsigned char)(kind*17);hb_diff_w32(c+0x28,0);}
    else if(kind<28){static const uint16_t timers[]={0x8000,0xffff,0,1,2,29,30,0x7fff};hb_diff_w16(c+0xef3e,timers[kind-20]);}
    else if(kind<32){c[0xdb60]=(unsigned char)(kind==28?1:kind==29?255:0);hb_diff_w32(c+0xeeac,kind==30?1:kind==31?0xffffffff:0);}
    else if(kind<40){static const unsigned char periods[]={0,0,0,1,2,3,255,255};static const uint32_t frames[]={0,1,0xffffffff,1,3,4,256,0xffffffff};k[0x1531ad]=periods[kind-32];hb_diff_w32(c+0x9c1a0,frames[kind-32]);}
    else if(kind<56){
        static const uint32_t values[]={0,1,0x7fffffff,0x80000000,0xffffffff,4096,100,101};
        for(unsigned i=0;i<n;++i){hb_diff_w32(c+0x84f48+20*i,values[(kind-40)%8]);hb_diff_w32(c+0x84f50+20*i,values[(kind-39)%8]);hb_diff_w32(c+0xf450+40*i,values[(kind-37)%8]);hb_diff_w32(c+0xf458+40*i,values[(kind-34)%8]);}
        hb_diff_w32(k+0x1531b0,kind>=48?0xffffffff:0);
    }else if(kind<64){static const uint32_t rates[]={0xff800000,0x41efffff,0x41f00000,0x41f00001,0x7f800000,0x7fc12345,0,0x80000000};hb_diff_w32(c+0x9c1a4,rates[kind-56]);hb_diff_w32(k+0x1531b0,0);hb_diff_w32(c+0x84f48,0x80000000);}
    else if(kind<72){static const uint16_t periods[]={0,1,2,0xffff};hb_diff_w16(c+0xb6962,periods[(kind-64)%4]);hb_diff_w32(c+0xb6964,kind>=68?0xffffffff:kind-64);c[0xb6960]=(unsigned char)((t/80)%5);}
    else{ /* Exact average threshold, one above/below, and truncating division. */
        for(unsigned i=0;i<n;++i)hb_diff_w32(c+0x84f48+20*i,4096+i%7*83+100+(kind-72)%3);
        hb_diff_w32(k+0x1531b0,101);if(kind>=76)hb_diff_w32(c+0x84f48,4096);
    }
}
#endif
