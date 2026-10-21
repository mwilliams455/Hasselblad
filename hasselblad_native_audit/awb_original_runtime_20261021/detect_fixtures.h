/* SPDX-License-Identifier: MIT */
#ifndef DETECT_FIXTURES_H
#define DETECT_FIXTURES_H
#include <stdint.h>
#include <math.h>
#include <string.h>
static void hd_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hd_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hd_wf(void*p,float v){memcpy(p,&v,4);}
static void hd_zone(unsigned char*p,unsigned lo,unsigned hi,unsigned weight){memset(p,0,52);hd_w32(p,lo);hd_w32(p+4,hi);hd_w32(p+8,0);hd_w32(p+12,20000);hd_w32(p+28,20000);hd_w32(p+44,20000);p[48]=weight;}
static void hd_curve(unsigned char*p,unsigned seed){memset(p,0,64);p[0]=3;hd_w32(p+4,40);hd_w32(p+8,10);hd_w32(p+12,240);for(unsigned j=0;j<3;++j){hd_w32(p+16+4*j,40+j*100);hd_w16(p+48+2*j,40+(seed+37*j)%180);}}
static void hb_test_detect(unsigned char*c,unsigned char*k,unsigned t,unsigned keep_stats){
    uint32_t geometry[3];memcpy(geometry,c+0x18,8);memcpy(geometry+2,c+0x28,4);
    memset(k+0x1348f4,0,0x138748-0x1348f4);memset(c+0xc374,0,0x130);memset(c+0xc4cc,0,20);memset(c+0x38620,0,12);memset(c+0x3da42,0,0x72);
    k[0x138748]=(t%3)==2;k[0x13994c]=3;for(unsigned j=0;j<3;++j){k[0x13994e +4*j]=j*100;hd_w16(k+0x139950+4*j,j*128);}
    hd_w16(c+0x3c23a,196);hd_w16(c+0x3c23c,60);
    hd_w32(c+0xc5a0,t%4==3?40:0);hd_w32(c+0xc370,t%2);hd_wf(c+0xc6d4,(float)(t*11%300));hd_w16(c+0xc6e4,t*7%257);hd_w16(c+0xc6e6,t*13%257);
    for(unsigned j=0;j<8;++j)hd_w16(c+0xc6e8+2*j,(j*30+t)%257);
    if(!keep_stats){hd_w32(c+0x18,8);hd_w32(c+0x1c,8);hd_w32(c+0x28,64);hd_wf(c+0x37618,(float)(t%29)-2);c[0x990dc]=(t%5)==4;
        hd_w32(c+0xb0bb0,3900+t%7*100);hd_w32(c+0xb0bb8,5000);hd_w32(c+0xb0c04,2000+(t*193)%8001);
        for(unsigned i=0;i<1024;++i){unsigned char*p=c+0xf450+40*i;hd_w32(p,2000+i%16*400);hd_w32(p+8,3000+i/16*120);hd_w32(p+12,1800+i*97%8400);hd_w32(p+20,i%5);c[0x3be2c+i]=i%7;}
        for(unsigned i=0;i<81;++i){hd_w32(c+0x348+16*i,4000+20*i);hd_w32(c+0x34c+16*i,6000-20*i);hd_w32(c+0x858+16*i,4200+17*i);hd_w32(c+0x85c+16*i,5800-15*i);}
    }
    for(unsigned i=0;i<6;++i){hd_w16(c+0x9c1ac+2*i,16+i*13+(t%8));
        for(unsigned j=0;j<7;++j)hd_wf(c+0x90+28*i+4*j,(float)((i+j+t)%7)/7.0f);
        for(unsigned j=0;j<4;++j)hd_wf(c+0x30+16*i+4*j,(float)((2*i+j+t)%5)/5.0f);
        if(t>=12){c[0xc374+12*i]=1;hd_w32(c+0xc378+12*i,i*11+70);hd_w32(c+0xc37c+12*i,i*15+30);}}
    for(unsigned i=0;i<11;++i){hd_w16(c+0x3da42+2*i,(t+i)%13);hd_w16(c+0x3da70+2*i,(t+i)%11);hd_w16(c+0x3da9e +2*i,40+i*3);}
    k[0x1348f4]=t%4!=0;
    for(unsigned i=0;i<5;++i){unsigned char*p=k+0x1348f8+1208*i;p[0]=1;p[1]=p[2]=p[3]=2;
        for(unsigned j=0;j<2;++j){hd_zone(p+4+52*j,3500+500*j,4300+500*j,1);hd_zone(p+212+52*j,2000+200*i,5000+500*j,1+j);hd_zone(p+420+52*j,2000+500*j,6000+500*j,2-j);}
        p[628]=3;for(unsigned j=0;j<3;++j){unsigned char*r=p+632+72*j;hd_w32(r,j*200);r[4]=3;for(unsigned a=0;a<3;++a){hd_w32(r+8+8*a,a*128);hd_w32(r+12+8*a,64+20*i+40*j+10*a);}}}
    k[0x136548]=1;k[0x136549]=1;k[0x13654d]=5;k[0x13654e]=18;k[0x13654f]=2;hd_zone(k+0x136550,2200,4100,1);hd_zone(k+0x136584,4000,6200,2);
    k[0x1366f0]=t>=20;k[0x1366f1]=t%3;
    for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;p[0]=i;p[4]=t%3;p[5]=(t%7)==1;p[8]=1;p[48]=1;p[52]=i+1;p[56]=5;p[57]=18;
        hd_w32(p+44,t%2);hd_w32(p+60,3500);hd_w32(p+64,7000);
        for(unsigned j=0;j<4;++j){hd_w32(p+12+8*j,30);hd_w32(p+16+8*j,450);}
        p[68]=p[69]=2;p[1384]=p[1385]=2;
        for(unsigned j=0;j<2;++j){hd_zone(p+72+52*j,2000,5000+j*500,1);hd_zone(p+488+52*j,6000,8000+j*200,1);hd_zone(p+1388+52*j,2200,6000+j*500,1);hd_zone(p+1804+52*j,5800,8000+j*200,1);}
        unsigned ramps[]={904,912,920,2220,2228,2236,2372};for(unsigned j=0;j<7;++j){hd_w32(p+ramps[j],20);hd_w32(p+ramps[j]+4,j==0||j==1||j==3||j==4?450:230);}
        unsigned curves[]={928,992,1056,1120,1184,1248,1320,2244,2308};for(unsigned j=0;j<9;++j)hd_curve(p+curves[j],i*10+j*13);
        p[1312]=1;p[1316]=2;p[2380]=1;p[2384]=4;p[2804]=7;
        for(unsigned g=0;g<2;++g){unsigned char*q=p+(g?2804:2384);for(unsigned j=0;j<q[0];++j){unsigned char*r=q+4+104*j;hd_w32(r,j);r[4]=3;for(unsigned a=0;a<3;++a){hd_w32(r+8+12*a,a*128);hd_w32(r+12+12*a,180+i*35+j*7+a*20);hd_w32(r+16+12*a,(int32_t)(a*200-j*50));}}}
        hd_w32(c+0xc45c+4*i,t%3);hd_w32(c+0xc44c+4*i,100+50*i);hd_w32(c+0xc454+4*i,t%15);
    }k[0x1366f2]=2;
    k[0x138294]=t>=40;c[0xc4cc]=t%4;c[0xc4ce]=t%2;
    for(unsigned i=0;i<4;++i){unsigned char*p=k+0x138298+212*i;p[0]=2;hd_zone(p+4,2000+i*500,4000+i*500,1);hd_zone(p+56,4000+i*500,6500+i*500,1);
        p=k+0x1385e8+88*i;for(unsigned j=0;j<4;++j)hd_w16(p+2*j,20+i*10+j*25);hd_w16(p+8,50+i*15);hd_w16(p+10,2+i);hd_w16(p+12,3+i);}
    hd_curve(k+0x138600,73);
    if(t>=96){unsigned n=t%2?8:1;
        for(unsigned i=0;i<5;++i){unsigned char*p=k+0x1348f8+1208*i;p[1]=p[2]=p[3]=4;
            memcpy(p+108,p+4,104);memcpy(p+316,p+212,104);memcpy(p+524,p+420,104);p[628]=n;
            for(unsigned j=0;j<n;++j){unsigned char*r=p+632+72*j;hd_w32(r,j*64);r[4]=n;for(unsigned a=0;a<n;++a){hd_w32(r+8+8*a,a*40);hd_w32(r+12+8*a,17+20*i+17*j+13*a);}}
        }
        for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;unsigned curves[]={928,992,1056,1120,1184,1248,1320,2244,2308};
            for(unsigned j=0;j<9;++j){unsigned char*r=p+curves[j];r[0]=n;for(unsigned a=0;a<n;++a){hd_w32(r+16+4*a,10+a*37);hd_w16(r+48+2*a,27+a*23);}}
            for(unsigned g=0;g<2;++g){unsigned char*q=p+(g?2804:2384);for(unsigned j=0;j<q[0];++j){unsigned char*r=q+4+104*j;r[4]=n;for(unsigned a=0;a<n;++a){hd_w32(r+8+12*a,10+a*37);hd_w32(r+12+12*a,200+a*20);hd_w32(r+16+12*a,(int32_t)(a*300-j*100));}}}
        }
        k[0x13994c]=n;for(unsigned j=0;j<n;++j){k[0x13994e +4*j]=30*j;hd_w16(k+0x139950+4*j,8+j*30);}
        unsigned char*r=k+0x138600;r[0]=n;for(unsigned a=0;a<n;++a){hd_w32(r+16+4*a,10+a*37);hd_w16(r+48+2*a,27+a*23);}
    }
    switch(t){
    case 1:k[0x1348f4]=2;break;case 2:k[0x13994c]=0;break;case 3:k[0x134b6c]=0;break;case 5:k[0x134b74]=0;break;
    case 6:for(unsigned i=0;i<5;++i)k[0x1348f8+1208*i]=0;break;
    case 7:for(unsigned i=0;i<5;++i)k[0x1348f9+1208*i]=0;break;
    case 8:for(unsigned i=0;i<6;++i)hd_w16(c+0x9c1ac+2*i,0);break;
    case 9:hd_w32(c+0xb0bb0,4401);break;case 10:hd_w32(c+0xb0bb0,7000);break;
    case 11:for(unsigned i=0;i<6;++i){c[0xc374+12*i]=1;hd_w32(c+0xc378+12*i,UINT32_MAX-77*i);hd_w32(c+0xc37c+12*i,0x80000000+999*i);}break;
    case 13:hd_w32(c+0x18,33);hd_w32(c+0x1c,16);hd_w32(c+0x28,528);break;
    case 14:hd_w32(c+0x18,16);hd_w32(c+0x1c,33);hd_w32(c+0x28,528);break;
    case 15:hd_w32(c+0x18,0);hd_w32(c+0x1c,0);hd_w32(c+0x28,0);break;
    case 16:memset(c+0x30,0,264);memset(c+0x3da42,0,22);break;
    case 17:hd_w32(c+0xc5a0,1);memset(c+0x30,0,264);memset(c+0x3da70,0,68);break;
    case 21:hd_w32(c+0xc444,3841);break;
    case 22:for(unsigned i=0;i<2;++i)k[0x1366f8+3536*i]=255;break;
    case 23:for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;p[68]=p[69]=p[1384]=p[1385]=0;}break;
    case 24:for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;unsigned off[]={928,992,1056,1120,1184,1248,1320,2244,2308};for(unsigned j=0;j<9;++j)p[off[j]]=0;}break;
    case 25:for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;p[2384]=p[2804]=0;}break;
    case 26:k[0x1366f2]=0;break;
    case 41:k[0x138600]=0;break;
    case 42:hd_w32(c+0xc4d0,100);hd_w32(c+0xc4d4,100);break;
    case 43:hd_w32(c+0xc4dc,100);break;
    case 96:hd_w32(c+0x18,32);hd_w32(c+0x1c,32);hd_w32(c+0x28,1024);break;
    case 97:hd_w32(c+0x18,64);hd_w32(c+0x1c,16);hd_w32(c+0x28,1024);break;
    case 98:hd_w32(c+0x18,16);hd_w32(c+0x1c,64);hd_w32(c+0x28,1024);break;
    case 99:hd_w32(c+0xc5a0,UINT32_MAX);break;
    case 100:for(unsigned i=0;i<6;++i)hd_w16(c+0x9c1ac+2*i,65535);break;
    case 101:for(unsigned i=0;i<6;++i)for(unsigned j=0;j<7;++j)hd_wf(c+0x90+28*i+4*j,-0.75f);break;
    case 102:hd_wf(c+0x90,NAN);hd_wf(c+0x94,INFINITY);hd_wf(c+0x98,-INFINITY);break;
    case 103:for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;for(unsigned g=0;g<2;++g){unsigned char*q=p+(g?2804:2384);for(unsigned j=0;j<q[0];++j)for(unsigned a=0;a<8;++a){hd_w32(q+16+104*j+12*a,UINT32_MAX-100*a);hd_w32(q+20+104*j+12*a,UINT32_MAX-1000*a);}}}break;
    case 104:hd_wf(c+0x37618,NAN);break;
    case 105:hd_wf(c+0x37618,INFINITY);break;
    case 106:hd_wf(c+0x37618,-INFINITY);break;
    case 107:k[0x1348f4]=1;for(unsigned i=0;i<5;++i)k[0x134b74+1208*i]=0;hd_w32(c+0xb0bb0,4000);break;
    case 108:k[0x1348f4]=1;for(unsigned i=0;i<5;++i)k[0x134b6c+1208*i]=0;hd_w32(c+0xb0bb0,4000);break;
    case 109:for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;for(unsigned a=0;a<8;++a)hd_w32(p+944+4*a,100);}break;
    case 110:for(unsigned i=0;i<2;++i){unsigned char*p=k+0x1366f4+3536*i;for(unsigned a=0;a<8;++a)hd_w32(p+944+4*a,300-40*a);}break;
    case 111:for(unsigned i=0;i<81;++i){hd_w32(c+0x348+16*i,0);hd_w32(c+0x34c+16*i,0);}c[0x990dc]=1;break;
    default:break;
    }
    if(keep_stats){memcpy(c+0x18,geometry,8);memcpy(c+0x28,geometry+2,4);}
}
#endif
