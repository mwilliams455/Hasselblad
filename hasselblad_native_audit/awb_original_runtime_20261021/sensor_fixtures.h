/* SPDX-License-Identifier: MIT */
#ifndef SENSOR_FIXTURES_H
#define SENSOR_FIXTURES_H
#include <math.h>
#include <stdint.h>
#include <string.h>
static void hs_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hs_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hs_wf(void*p,float v){memcpy(p,&v,4);}
/* Synthetic fixture data; no original sensor model or calibration tables. */
static void hb_test_sensor(unsigned char*c,unsigned char*k,unsigned t){
    memset(c+0xc59c,0,0xd328-0xc59c);memset(k+0x139e2c,0,0x14841c-0x139e2c);
    k[0x139e2c]=k[0x139e2e]=1;c[0x9c1bc]=c[0x9c1bd]=1;hs_w32(c+0x9c1a0,60);hs_w32(c+0x9c1b8,59);hs_wf(c+0x9c1a4,30);
    hs_w32(k+0x139e30,37);hs_w32(k+0x139e34,53);hs_w32(k+0x139e3c,1);hs_w32(k+0x139e40,65535);hs_wf(k+0x139e44,1);
    for(unsigned i=0;i<10;++i)hs_w16(c+0x9c1cc+2*i,500+73*i+(t%7)*11);
    for(unsigned i=0;i<401;++i)for(unsigned j=0;j<10;++j)hs_w16(k+0x139e48+20*i+2*j,(int16_t)((i+7*j)%31)-7);
    for(unsigned i=0;i<3;++i)for(unsigned j=0;j<10;++j)hs_w16(k+0x13bd9c+20*i+2*j,2+i+((j+i)%3));
    k[0x13bdd8]=3;hs_wf(k+0x13bddc,0.7f);hs_w16(k+0x13bdf8,6);
    for(unsigned i=0;i<6;++i){unsigned char*r=k+0x13be10+140*i;for(unsigned j=0;j<3;++j)hs_wf(r+4*j,0.125f*(int)(i+j-2));r[12]=10;for(unsigned j=0;j<10;++j){r[16+8*j]=j+1;hs_wf(r+20+8*j,0.6f+0.05f*(i+j));}}
    hs_w16(k+0x13be0c,2);hs_w16(k+0x13be0e,2);hs_w16(k+0x13be10,2);
    for(unsigned i=0;i<3;++i){hs_wf(k+0x13bdfc+4*i,0.15f*i);hs_wf(k+0x13bde0+4*i,0.3f+i);hs_wf(k+0x13bdec+4*i,-0.25f*i);}
    for(unsigned i=0;i<3;++i){for(unsigned j=0;j<7;++j)hs_wf(c+0xd234+28*i+4*j,0.02f*(int)(i+j-1));for(unsigned j=0;j<4;++j)hs_wf(c+0xd204+16*i+4*j,0.1f*(i+j));}
    for(unsigned i=0;i<11;++i)hs_w16(c+0x3da9e +2*i,3*i);
    if(t>=10){c[0xc5a4]=1;c[0xc5a8]=2;hs_w32(c+0xc62c,4400);for(unsigned z=0;z<2;++z){hs_w32(c+0xc5ac+44*z,3000+3000*z);for(unsigned i=0;i<10;++i)hs_w32(c+0xc5b0+44*z+4*i,3072+256*i+1024*z);}}
    if(t>=20){c[0xc680]=1;for(unsigned i=0;i<10;++i){hs_w32(c+0xc684+4*i,23000+2000*i);hs_w32(c+0xc6ac+4*i,30000+1000*i);}}
    if(t>=30){k[0x1480f0]=1;k[0x1480f4]=t%2;for(unsigned i=0;i<401;++i)hs_w16(k+0x1480f8+2*i,1+(i*131)%65535);}
    if(t>=40){k[0x139e2d]=1;c[0xd288]=1;hs_w32(c+0xd294,5700);}
    if(t>=50){k[0x144a14]=3;hs_wf(c+0x37618,450);
        for(unsigned i=0;i<3;++i){unsigned char*r=k+0x144a18+0x1248*i;r[0]=i;r[4]=3;
            for(unsigned j=0;j<3;++j){unsigned char*a=r+8+0x248*j;hs_w32(a,100+400*j);a[4]=3;
                for(unsigned z=0;z<3;++z){unsigned char*b=a+8+0x48*z;hs_w32(b,2000+3000*z);b[4]=3;
                    for(unsigned y=0;y<3;++y){hs_w32(b+8+8*y,50*y);hs_w16(b+12+8*y,40+30*i+10*j+20*z+5*y);}}}}
    }
    switch(t){
    case 1:k[0x139e2c]=0;break;case 2:k[0x139e2e]=0;break;case 3:c[0xd324]=1;break;
    case 4:k[0x13bdd8]=0;break;case 5:k[0x13bdd8]=1;break;case 6:k[0x13bdd8]=2;break;
    case 7:hs_w16(k+0x13bdf8,0);break;case 8:hs_w16(c+0x9c1dc,0);break;case 9:memset(k+0x13bd9c,0,60);break;
    case 11:c[0xc5a8]=0;break;case 12:c[0xc5a8]=1;break;case 13:hs_w32(c+0xc62c,1000);break;case 14:hs_w32(c+0xc62c,10000);break;
    case 15:hs_w32(c+0xc5b0+8*4,0);hs_w32(c+0xc5b0+44+8*4,0);break;
    case 16:memset(k+0x13bd9c,255,20);break;case 17:memset(k+0x13bdb0,255,20);break;case 18:memset(k+0x13bdc4,255,20);break;
    case 21:hs_w32(k+0x139e30,0);hs_w32(k+0x139e34,0);break;
    case 22:hs_w32(k+0x139e30,128);hs_w32(k+0x139e34,128);break;
    case 23:hs_w32(k+0x139e30,UINT32_MAX);hs_w32(k+0x139e34,513);break;
    case 24:k[0x139e38]=1;c[0x9c1bc]=0;break;case 25:k[0x139e38]=1;c[0xc59d]=2;break;
    case 26:k[0x139e38]=1;c[0xc59d]=3;c[0x9c1bd]=0;break;
    case 27:k[0x139e38]=1;hs_w32(c+0x9c1b8,61);break;
    case 28:k[0x139e38]=1;hs_wf(c+0x9c1a4,0);break;
    case 29:k[0x139e38]=1;hs_wf(c+0x9c1a4,NAN);break;
    case 31:memset(k+0x139e48,0,8020);break;case 32:memset(k+0x1480f8,0,802);break;
    case 33:k[0x139e38]=1;hs_w32(k+0x139e3c,1000);break;
    case 34:k[0x139e38]=1;hs_w32(k+0x139e40,500);break;
    case 35:k[0x139e38]=1;hs_wf(k+0x139e44,0);break;
    case 36:for(unsigned i=0;i<6;++i)k[0x13be1c+140*i]=0;break;
    case 37:for(unsigned i=0;i<6;++i)for(unsigned j=0;j<10;++j)k[0x13be20+140*i+8*j]=2*j;break;
    case 38:hs_wf(k+0x13bddc,NAN);break;case 39:hs_wf(k+0x13bddc,INFINITY);break;
    case 41:hs_w16(c+0x9c1dc,0);break;case 42:memset(k+0x13bd9c,255,60);break;
    case 43:k[0x139e2e]=0;break;case 44:c[0xd324]=1;break;
    case 45:hs_w32(c+0xd288,0xaabbcc01);break;
    case 46:hs_w32(c+0xd324,0xaabbcc01);break;
    case 47:hs_w32(c+0xc5a4,0xaabbcc00);break;
    case 51:hs_wf(c+0x37618,0);break;case 52:hs_wf(c+0x37618,10000);break;
    case 53:hs_wf(c+0x37618,NAN);break;
    default:break;
    }
    if(t>=54)for(unsigned i=0;i<3;++i)for(unsigned j=0;j<3;++j)for(unsigned z=0;z<3;++z)for(unsigned y=0;y<3;++y)hs_w16(k+0x144a18+0x1248*i+8+0x248*j+8+0x48*z+12+8*y,(uint16_t[]){0,9,128,129,200,256,300}[(t-54)%7]);
}
#endif
