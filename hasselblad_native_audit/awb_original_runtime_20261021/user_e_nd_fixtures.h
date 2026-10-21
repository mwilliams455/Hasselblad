/* SPDX-License-Identifier: MIT
 * Test-only generated tables, not firmware calibration. */
#ifndef HB_USER_E_ND_FIXTURES_H
#define HB_USER_E_ND_FIXTURES_H
#include <stdint.h>
#include <string.h>
static void hb_test_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hb_test_wf(void*p,float v){memcpy(p,&v,4);}
static void hb_test_e_nd_request(unsigned char*c,unsigned char*k,unsigned t){
    k[0x16e940]=4;
    for(unsigned i=0;i<4;++i){unsigned char*p=k+0x16e942+52*i;memset(p,0,52);hb_test_w16(p,(uint16_t)(10+10*i));p[2]=8;
        for(unsigned j=0;j<8;++j){hb_test_w16(p+4+6*j,(uint16_t)(1+2*j));hb_test_w16(p+6+6*j,(uint16_t)(3800+100*i+21*j));hb_test_w16(p+8+6*j,(uint16_t)(4200-70*i+13*j));}}
    k[0x16e854]=2;
    for(unsigned i=0;i<2;++i){unsigned char*p=k+0x16e858+116*i;memset(p,0,116);hb_test_w16(p,(uint16_t)(77+i));hb_test_wf(p+4,24.5f+(float)i);hb_test_w16(p+8,2);
        for(unsigned g=0;g<2;++g){unsigned char*q=p+10+52*g;hb_test_w16(q,(uint16_t)(2000+6000*g));hb_test_w16(q+2,2+t%7);
            for(unsigned j=0;j<2+t%7;++j){hb_test_w16(q+4+6*j,(uint16_t)(1+2*j));hb_test_w16(q+6+6*j,(uint16_t)(4000+57*i+31*g+19*j));hb_test_w16(q+8+6*j,(uint16_t)(4200-23*i+17*g-11*j));}}}
    unsigned selected=t%2;const unsigned char*p=k+0x16e858+116*selected;
    c[0xb1f86]=1;hb_test_w16(c+0xb1f88,(uint16_t)(77+selected));hb_test_w16(c+0xb1f8a,2);memcpy(c+0xb1f8c,p+10,104);
    static const uint16_t temperatures[]={0,199,200,209,250,299,300,309,310,65535};hb_test_w16(c+0xb1ff4,temperatures[t%10]);
    for(unsigned g=0;g<2;++g)for(unsigned j=0;j<2+t%7;++j){unsigned char*q=c+0xb1f8c+52*g+6*j;hb_test_w16(q+6,(uint16_t)(3900+43*g+71*j+t%23));hb_test_w16(q+8,(uint16_t)(4300-29*g+37*j+t%17));}
}
#endif
