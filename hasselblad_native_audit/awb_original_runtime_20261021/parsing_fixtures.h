/* SPDX-License-Identifier: MIT */
#ifndef PARSING_FIXTURES_H
#define PARSING_FIXTURES_H
#include <math.h>
#include <stdint.h>
#include <string.h>
static void hp_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hp_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hp_wf(void*p,float v){memcpy(p,&v,4);}
/* Synthetic categories, curves and exposure parameters only. */
static void hb_test_parsing(unsigned char*c,unsigned char*k,unsigned t,unsigned keep_geometry){
    unsigned width=8,height=8,n=64;if(keep_geometry){memcpy(&width,c+0x18,4);memcpy(&height,c+0x1c,4);memcpy(&n,c+0x28,4);}
    else{if(t==3)width=height=1;if(t==4)width=1;if(t==5)height=1;if(t==6)width=height=32;if(t==7)width=height=0;if(t==8)width=0;if(t==9)height=0;n=width*height;hp_w32(c+0x18,width);hp_w32(c+0x1c,height);hp_w32(c+0x28,n);}
    memset(k+0x138748,0,0x13994c-0x138748);k[0x138748]=1;k[0x138774]=t>=10;
    memset(c+0xc4e0,0,84);memset(c+0x3c22c,0,22);memset(c+0x3c242,0x37,6144);memset(c+0x3862c,0x63,0x3800);memset(c+0x9c20a,0,0x3800);
    hp_wf(c+0x37618,9.5f);c[0x990dc]=0;
    for(unsigned i=0;i<n;++i){if(!keep_geometry){hp_w32(c+0xf450+40*i,2500+(i%8)*500);hp_w32(c+0xf458+40*i,3000+(i/8)*400);hp_w32(c+0xf45c+40*i,1800+137*i);}
        for(unsigned j=0;j<7;++j)hp_w16(c+0x9c20a+2*(n*j+i),(i+3*j)%9==0?0:17+(17*i+31*j)%230);}
    for(unsigned kind=0;kind<6;++kind){unsigned char*r=k+0x138778+488*kind;r[0]=1;r[1]=2;r[212]=3;
        for(unsigned z=0;z<2;++z){unsigned char*p=r+4+52*z;hp_w32(p,2000+300*kind+800*z);hp_w32(p+4,4500+300*kind+800*z);hp_w32(p+8,2000);hp_w32(p+12,12000);hp_w32(p+20,0);hp_w32(p+28,65535);hp_w32(p+36,0);hp_w32(p+44,65535);}
        for(unsigned j=0;j<3;++j){unsigned char*a=r+214+34*j;a[0]=j*100;a[1]=3;for(unsigned z=0;z<3;++z){hp_w16(a+2+4*z,z*128);hp_w16(a+4+4*z,20+10*kind+30*j+15*z);}}
    }
    for(unsigned i=0;i<7;++i){unsigned char*r=k+0x1394d0+164*i;r[0]=3;
        for(unsigned j=0;j<3;++j){unsigned char*a=r+4+20*j;a[0]=j*10;hp_wf(a+4,0.125f*(i+j));hp_wf(a+8,0.2f*(i+2*j));}
        hp_w16(c+0x138+8*i,71);hp_w16(c+0x13a+8*i,83);hp_w16(c+0x13c+8*i,i*13);hp_w16(c+0x13e +8*i,200-i*17);
    }
    if(t>=20)for(unsigned i=0;i<7;++i){c[0xc4e0+12*i]=1;hp_w32(c+0xc4e4+12*i,80+3*i);hp_w32(c+0xc4e8+12*i,70+5*i);}
    if(t>=30){c[0x990dc]=1;for(unsigned i=0;i<81;++i){hp_w32(c+0x348+16*i,4000+30*i);hp_w32(c+0x34c+16*i,6000-20*i);hp_w32(c+0x858+16*i,4100+21*i);hp_w32(c+0x85c+16*i,6400-31*i);}}
    switch(t){
    case 1:k[0x138748]=2;break;case 2:if(!keep_geometry)hp_w32(c+0x18,1025);break;
    case 11:for(unsigned i=0;i<6;++i)k[0x138778+488*i]=0;break;
    case 12:for(unsigned i=0;i<6;++i)k[0x138779+488*i]=0;break;
    case 13:k[0x13884c]=0;break;case 14:k[0x13884f]=0;break;case 15:k[0x138893]=0;break;
    case 16:for(unsigned i=0;i<6;++i){k[0x13884c+488*i]=1;k[0x13884f+488*i]=1;}break;
    case 17:for(unsigned i=0;i<7168;++i)hp_w16(c+0x9c20a+2*i,0);break;
    case 18:for(unsigned i=0;i<7168;++i)hp_w16(c+0x9c20a+2*i,65535);break;
    case 19:for(unsigned i=0;i<7;++i)hp_w16(c+0x3c22c+2*i,65530);break;
    case 21:k[0x138774]=0;for(unsigned i=0;i<7168;++i)hp_w16(c+0x9c20a+2*i,128);break;
    case 22:hp_wf(c+0x37618,-1);break;case 23:hp_wf(c+0x37618,30);break;
    case 24:hp_wf(c+0x37618,NAN);break;case 25:hp_wf(c+0x37618,INFINITY);break;
    case 26:hp_wf(c+0x37618,-INFINITY);break;case 27:hp_wf(c+0x37618,10);break;
    case 28:for(unsigned i=0;i<7;++i){hp_w32(c+0xc4e4+12*i,UINT32_MAX-37*i);hp_w32(c+0xc4e8+12*i,UINT32_MAX/2+777*i);}break;
    case 29:k[0x138774]=2;break;
    case 31:for(unsigned i=0;i<81;++i)hp_w32(c+0x348+16*i,0);break;
    case 32:for(unsigned i=0;i<81;++i)hp_w32(c+0x34c+16*i,0);break;
    case 33:for(unsigned i=0;i<7;++i){unsigned char*r=k+0x1394d0+164*i;hp_wf(r+8,NAN);hp_wf(r+28,-2);hp_wf(r+48,INFINITY);}break;
    default:break;
    }
    if(t>=34){unsigned count=t==34?1:8;for(unsigned i=0;i<7;++i){unsigned char*r=k+0x1394d0+164*i;r[0]=count;for(unsigned j=0;j<count;++j){unsigned char*a=r+4+20*j;a[0]=3*j;hp_wf(a+4,0.125f*(i+j));hp_wf(a+8,0.25f*(8+i-j));}}
        for(unsigned i=0;i<6;++i){unsigned char*r=k+0x138778+488*i;r[212]=count;r[1]=4;memcpy(r+4+104,r+4,104);for(unsigned j=0;j<count;++j){unsigned char*a=r+214+34*j;a[0]=32*j;a[1]=count;for(unsigned z=0;z<count;++z){hp_w16(a+2+4*z,40*z);hp_w16(a+4+4*z,12*i+8*j+13*z);}}}
        if(t==36)hp_wf(c+0x37618,21);if(t==37)hp_wf(c+0x37618,0);
        if(t==38)for(unsigned i=0;i<7;++i)hp_w16(c+0x3c23a+2*(i%4),65530);
        if(t==39)for(unsigned i=0;i<n;++i){hp_w32(c+0xf450+40*i,UINT32_MAX-i);hp_w32(c+0xf458+40*i,0x80000000+i);}
    }
}
#endif
