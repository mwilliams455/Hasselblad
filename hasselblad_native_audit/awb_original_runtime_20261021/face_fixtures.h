/* SPDX-License-Identifier: MIT */
#ifndef HB_FACE_FIXTURES_H
#define HB_FACE_FIXTURES_H
#include <stdint.h>
#include <string.h>
static void hf_w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void hf_w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void hf_wf(void*p,float v){memcpy(p,&v,4);}
static void hf_curve(unsigned char*p,unsigned value){memset(p,0,64);p[0]=2;hf_w32(p+4,10);hf_w32(p+8,value);hf_w32(p+12,value);hf_w32(p+16,0);hf_w32(p+20,65535);hf_w16(p+48,value);hf_w16(p+50,value);}
static void hf_atmos(unsigned char*p,unsigned shift){memset(p,0,12548);p[0]=2;
 for(unsigned e=0;e<2;++e){unsigned char*q=p+4+1568*e;hf_w32(q,e*20);q[4]=2;
  for(unsigned t=0;t<2;++t){unsigned char*r=q+8+104*t;hf_w32(r,2000+t*8000);r[4]=3;
   for(unsigned d=0;d<3;++d){unsigned char*v=r+8+12*d;hf_w32(v,(int32_t)d*2000-2000);hf_w32(v+4,3900+shift+e*90+t*100+d*80);hf_w32(v+8,4200-shift-e*40-t*90-d*30);}}}}
static void hf_weight_tables(unsigned char*k){unsigned char*p=k+0x16ab20;memset(p,0,962);p[0]=3;
 for(unsigned i=0;i<3;++i){unsigned char*q=p+2+64*i;hf_w16(q,i*1200);q[2]=3;for(unsigned j=0;j<3;++j){hf_w16(q+4+4*j,j*2048);hf_w16(q+6+4*j,250-i*30-j*15);}}
 p=k+0x16aee4;memset(p,0,3738);p[0]=3;for(unsigned i=0;i<3;++i){unsigned char*q=p+2+934*i;hf_w16(q,i*128);q[2]=3;for(unsigned e=0;e<3;++e){unsigned char*r=q+4+62*e;r[0]=e*10;r[1]=3;for(unsigned j=0;j<3;++j){hf_w16(r+2+4*j,j*500);hf_w16(r+4+4*j,240-i*10-e*20-j*25);}}}}
/* Synthetic records only. Original initialized calibration is supplied privately. */
static void hb_test_face(unsigned char*c,unsigned char*k,unsigned t){
 k[0x16446c]=1;c[0xdb50]=1;c[0xdb51]=1;c[0xd902]=0;c[0xe0bb0]=0;
 memset(c+0xdb54,0,0x168);memset(c+0xdd2c,0,0x174);memset(c+0xee4c,0,0x108);
 hf_w32(c,640);hf_w32(c+4,480);hf_w32(c+8,0);hf_w32(c+12,0);hf_w32(c+16,160);hf_w32(c+20,120);hf_w32(c+24,4);hf_w32(c+28,4);hf_w32(c+32,640);hf_w32(c+36,480);hf_w32(c+40,16);hf_w32(c+44,8);
 hf_w32(c+0xb20f8,10000);hf_w32(c+0x9c1a0,100);hf_wf(c+0x9c1a4,30);hf_wf(c+0x37618,10);hf_wf(k+0x164470,1);
 hf_w32(k+0x164474,1);hf_w32(k+0x164478,1);hf_w32(k+0x16447c,200);hf_w32(k+0x164484,0);hf_w32(k+0x164488,10000);
 c[0xdea0]=2;for(unsigned m=0;m<2;++m){k[0x1644b0+364*m]=2;hf_w32(c+0xdea4+2004*m,0);hf_w32(c+0xdea8+2004*m,80);for(unsigned j=0;j<81;++j){unsigned char*p=c+0xdee4+2004*m+24*j;hf_w32(p,5000-j*40+200*m);hf_w32(p+4,1800+j*40+100*m);hf_w32(p+8,3800+300*m);hf_w32(p+12,4200-200*m);hf_w32(p+16,800);}}
 hf_atmos(k+0x1647c8,0);hf_atmos(k+0x1678cc,100);hf_curve(k+0x164788,128);hf_curve(k+0x16aa58,240);hf_curve(k+0x16aa98,250);hf_curve(k+0x16aad8,230);k[0x16ab20]=0;k[0x16aee4]=0;hf_w32(c+0xeec4,256);hf_w32(c+0xb0bbc,3700);hf_w32(c+0xb0bc4,3300);hf_w32(c+0xb0bc8,3800);hf_w32(c+0xb0bcc,4096);hf_w32(c+0xb0bd0,3400);
 for(unsigned i=0;i<8;++i){c[0x37450+i]=i<3;unsigned char*p=c+0x37458+40*i;hf_w32(p,3700+40*i);hf_w32(p+4,4096);hf_w32(p+8,3300+35*i);hf_w32(p+12,100+i*50);hf_w32(p+16,150+i*50);hf_w32(p+20,200+i*50);hf_w32(p+36,128);hf_w32(k+0x16448c+4*i,256);
  hf_w32(c+0x37598+16*i,80+40*i);hf_w32(c+0x3759c+16*i,40+20*i);hf_w32(c+0x375a0+16*i,90);hf_w32(c+0x375a4+16*i,80);
  hf_w32(c+0xef54+4*i,1);hf_wf(c+0xef74+16*i,0.05f*i);hf_wf(c+0xef78+16*i,0.05f*i);hf_wf(c+0xef7c+16*i,0.3f);hf_wf(c+0xef80+16*i,0.35f);
 }
 for(unsigned j=0;j<16;++j){hf_w32(c+0xf450+40*j,3600+j*40);hf_w32(c+0xf458+40*j,3200+j*50);for(unsigned q=0;q<3;++q){hf_w32(c+0x84f48+20*j+4*q,3300+j*30+q*200);hf_w16(c+0xa24c8+6*j+2*q,100+j*11+q*30);}hf_w32(c+0x84f58+20*j,64+j);}
 for(unsigned i=0;i<6;++i)hf_w32(k+0x16a9d0+4*i,400);hf_w32(k+0x16a9e8,2);k[0x16a9ec]=1;hf_w32(k+0x16a9f0,30);hf_w32(k+0x16a9f4,20);for(unsigned i=0;i<9;++i)hf_w32(k+0x16aa0c+4*i,3+i);
 if(t>=53){hf_weight_tables(k);hf_w16(c+0x3da50,(t*31)%257);hf_w16(c+0x3da56,(t*17)%257);hf_wf(c+0x37618,(float)((int)(t%31)-5));hf_w32(c+0xb20f8,10000*(1+t%4));}
 if(t>=53&&t<69){for(unsigned i=0;i<8;++i){hf_w32(c+0x37464+40*i,50+(t-53)*120+i*23);hf_w32(c+0x37468+40*i,50+(t-53)*120+i*23);hf_w32(c+0x3746c+40*i,50+(t-53)*120+i*23);}}
 if(t>=69&&t<85){unsigned n=1+(t%4);for(unsigned m=0;m<2;++m){k[0x1644b0+364*m]=n;for(unsigned j=0;j<n;++j)hf_w32(c+0xdea4+2004*m+4*j,j*80/(n>1?n-1:1));}hf_w32(c+0x37458,2000+(t-69)*400);hf_w32(c+0x37460,6000-(t-69)*250);}
 if(t>=85&&t<117){hf_w32(c+0xef34,(t-85)%8);hf_w16(c+0xef0e,4);hf_w16(c+0xef0c,(t/8)%2);hf_w32(c+0xdb58,1);hf_w32(c+0xeed4,3700);hf_w32(c+0xeed8,4096);hf_w32(c+0xeedc,3300);hf_w32(c+0xeee0,190);hf_w32(c+0xeeac,180);hf_w32(c+0xeeb0,170);hf_w32(c+0xef10,t%12);c[0xb0bac]=t%2;c[0xef40]=1;hf_w32(c+0xef44,30);hf_w32(c+0xef48,20);hf_w32(c+0xef4c,600000);hf_w32(c+0xef50,500000);}
 if(t==0)k[0x16446c]=0;
 if(t==1)c[0xdb50]=c[0xdb51]=0;
 if(t==2){c[0xdb50]=0;memset(c+0xef10,0x31,40);c[0xee84]=1;}
 if(t==3){c[0xd902]=1;hf_w32(c,0);}
 if(t==4){c[0xd902]=1;hf_w32(c+16,0);}
 if(t==5)hf_w32(c+0xb20f8,9999);
 if(t==6){memset(c+0x37450,0,8);hf_w32(c+0xdb5c,0);}
 if(t==7)c[0xdea0]=0;
 if(t>=8&&t<16){c[0xd902]=1;hf_wf(c+0xef74,-0.2f);hf_wf(c+0xef78,-0.1f);if(t==9)hf_w32(c+0xef54,0);if(t==10)hf_w32(c+0xef54,2);if(t==11)hf_wf(c+0xef7c,0.0f);if(t==12)hf_wf(c+0xef7c,-0.2f);if(t==13)hf_wf(c+0xef74,1.5f);if(t==14)hf_w32(c+8,60);if(t==15)hf_w32(c+0xb20f8,30000);}
 if(t>=16&&t<24){c[0xe0bb0]=1;hf_w16(c+0xe0bb2,(t-16)*600);hf_w16(c+0xe0bb4,(t-16)*400);hf_w16(c+0xe0bb6,3500);hf_w16(c+0xe0bb8,3200);}
 if(t>=24&&t<32){memset(c+0x37450,0,8);c[0xdb60]=1;hf_w32(c+0xdb54,t==24?101:99);hf_w32(c+0xdb5c,8);memset(c+0xdb61,0,8);if(t==25)hf_wf(c+0x9c1a4,0);if(t==26)hf_wf(k+0x164470,0);}
 if(t>=32&&t<40){hf_w32(c+0xef34,t-32);hf_w32(c+0xef38,t%3);c[0xb0bac]=1;hf_w32(c+0xeec8,3600);hf_w32(c+0xeed0,3200);hf_w32(c+0xeed4,3700);hf_w32(c+0xeed8,4096);hf_w32(c+0xeedc,3300);hf_w32(c+0xeee0,200);hf_w32(c+0xeee4,3800);hf_w32(c+0xeeec,3400);}
 if(t==40)k[0x164788]=0;
 if(t==41)k[0x16aa58]=0;
 if(t==42)k[0x16aa98]=0;
 if(t==43)k[0x16aad8]=0;
 if(t==44){k[0x1644b0]=1;k[0x16461c]=1;}
 if(t>=45&&t<53){hf_w32(c+44,t-45);}
}
#endif
