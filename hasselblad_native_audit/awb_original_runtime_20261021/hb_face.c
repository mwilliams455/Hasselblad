/* SPDX-License-Identifier: MIT */
#include "hb_face.h"
#include "hb_stat_prepare.h"
#include "hb_detect.h"
#include "hb_history.h"
#include "hb_scene_optimizer.h"
#include "hb_scene_controller.h"
#include "hb_atmosphere.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t fu(double x){return !(x>0)?0:x>=4294967295.0?UINT32_MAX:(uint32_t)x;}
static uint32_t du(uint32_t a,uint32_t b){return b?a/b:0;}
static int32_t ds(uint32_t a,uint32_t b){if(!b)return 0;if(a==0x80000000&&b==UINT32_MAX)return INT32_MIN;return (int32_t)a/(int32_t)b;}
static int64_t dl(int64_t a,int64_t b){return b?a/b:0;}
static int64_t ab(int64_t v){return v<0?-v:v;}
static uint32_t norm(uint32_t r,uint32_t b,uint32_t x,uint32_t y){r-=x;b-=y;return r*r+b*b;}
static uint32_t interp(uint32_t a,uint32_t b,uint32_t x,uint32_t y,float t){return hb_scene_interpolate(a,b,x,y,t);}
static uint32_t curve(unsigned char*c,const unsigned char*k,size_t in,float x,size_t out){uint32_t v,status=hb_detect_curve(k+in,x,&v);if(!status)w32(c+out,v);return status;}
static void brackets(const unsigned char*p,unsigned n,unsigned stride,unsigned wide,float x,unsigned*a,unsigned*b){
 *a=0;*b=n-1;float first=wide?u16(p):p[0],last=wide?u16(p+stride*(*b)):p[stride*(*b)];
 if(first>=x)*b=0;else if(last<=x)*a=*b;else for(unsigned i=1;i<n;++i)if((float)(wide?u16(p+stride*i):p[stride*i])>=x){*a=i-1;*b=i;break;}
}
static uint32_t short_curve(const unsigned char*p,unsigned n,int32_t x){
 if(x<=u16(p))return u16(p+2);if(x>=u16(p+4*(n-1)))return u16(p+4*(n-1)+2);
 for(unsigned i=1;i<n;++i)if(x<=u16(p+4*i)){uint32_t a=u16(p+4*(i-1)),b=u16(p+4*i);return ds((b-x)*u16(p+4*(i-1)+2)+(x-a)*u16(p+4*i+2),b-a);}return u16(p+2);
}
uint32_t hb_face_brightness(const unsigned char*p,float ev,uint32_t brightness){unsigned a,b;brackets(p+4,p[2],62,0,ev,&a,&b);
 const unsigned char*x=p+4+62*a,*y=p+4+62*b;return interp(x[0],y[0],short_curve(x+2,x[1],(int16_t)brightness),short_curve(y+2,y[1],(int16_t)brightness),ev);}
static uint32_t geometry(unsigned char*c){
 if(c[0xd902]!=1||c[0xe0bb0]==1)return 0;
 uint32_t sw=u32(c),sh=u32(c+4),bx=u32(c+16),by=u32(c+20),gw=u32(c+24),gh=u32(c+28);
 if(!sw||!sh)return 222;if(!bx||!by)return 223;w32(c+44,8);
 for(unsigned i=0;i<8;++i){uint32_t request=u32(c+0xef54+4*i);if(!request)continue;const unsigned char*p=c+0xef74+16*i;
  float x=f32(p),y=f32(p+4),w=f32(p+8),h=f32(p+12),l=(x*(float)sw-(float)u32(c+8))/(float)bx,
   r=((x+w)*(float)sw-(float)u32(c+8))/(float)bx,t=(y*(float)sh-(float)u32(c+12))/(float)by,b=((y+h)*(float)sh-(float)u32(c+12))/(float)by;
  float xe=fminf(floorf(r),(float)(gw-1)),ye=fminf(floorf(b),(float)(gh-1));uint32_t xs=fu(fmaxf(floorf(l),0)),ys=fu(fmaxf(floorf(t),0));float sum[7]={0},area=0;
  for(uint32_t ix=xs;(float)ix<=xe;++ix)for(uint32_t iy=ys;(float)iy<=ye;++iy){float dx=fminf(r,(float)(ix+1))-fmaxf(l,(float)ix),dy=fminf(b,(float)(iy+1))-fmaxf(t,(float)iy);if(dx<=0||dy<=0)continue;
   float a=dx*dy;unsigned j=iy*gw+ix;for(unsigned q=0;q<3;++q)sum[q]+=a*(float)u16(c+0xa24c8+6*j+2*q);for(unsigned q=0;q<4;++q)sum[3+q]+=a*(float)u32(c+0x84f48+20*j+(q==3?16:4*q));area+=a;}
  if(request==1&&(double)area>0.8){c[0x37450+i]=1;unsigned char*d=c+0x37450+40*i;
   for(unsigned q=0;q<3;++q){w32(d+20+4*q,fu(sum[q]/area));w32(d+8+4*q,fu(sum[q+3]/area));}w32(d+44,fu(sum[6]/area));
   float dims[4]={(float)sw,(float)sh,(float)sw,(float)sh};for(unsigned q=0;q<4;++q)w32(c+0x37598+16*i+4*q,fu(f32(p+4*q)*dims[q]));
  }else c[0x37450+i]=0;
 }return 0;
}
static void capture(unsigned char*c,const unsigned char*k){
 unsigned n=u32(c+44),any=0;uint32_t frame=u32(c+0x9c1a0);w32(c+0xdb58,0);for(unsigned i=0;i<n;++i)any|=c[0x37450+i]==1;
 if(any&&((u32(c+0x375a0)>=u32(k+0x164474)&&u32(c+0x375a4)>=u32(k+0x164478))||c[0xe0bb0]==1)){
  w32(c+0xdb54,frame);w32(c+0xdb5c,n);for(unsigned i=0;i<n;++i){c[0xdb61+i]=c[0x37450+i];memcpy(c+0xdb6c+40*i,c+0x37458+40*i,12);w32(c+0xdb90+40*i,u32(c+0x3747c+40*i));memcpy(c+0xdcac+16*i,c+0x37598+16*i,16);for(unsigned q=0;q<4;++q)w16(c+0xa87cf+16*q+2*i,u32(c+0xdcac+16*i+4*q));}c[0xdb60]=1;w32(c+0xdb58,1);
 }else{for(unsigned i=0;i<n;++i)for(unsigned q=0;q<4;++q)w16(c+0xa87cf+16*q+2*i,0);
  if(c[0xdb60]&&(frame<u32(c+0xdb54)||f32(c+0x9c1a4)==0||!((float)(frame-u32(c+0xdb54))/f32(c+0x9c1a4)<f32(k+0x164470)))){c[0xdb60]=0;w32(c+0xdb5c,8);memset(c+0xdb61,0,8);}}
}
static unsigned confidence(const unsigned char*c,const unsigned char*k,uint32_t r,uint32_t b){
 unsigned weight=0;for(unsigned m=0;m<c[0xdea0];++m){const unsigned char*p=c+0xdea4+2004*m,*rows=c+0xdee4+2004*m;
  unsigned knots=k[0x1644b0+364*m],best=80,local=80,mid=0,found=0;uint32_t dist=0x80000000,localdist=0x80000000,prev=0,next=0;
  for(unsigned j=0;j+1<knots;++j){unsigned l=u32(p+4*j),u=u32(p+4*j+4);
   while(u-l>=2){mid=(l+u)>>1;uint32_t d=norm(r,b,u32(rows+24*mid),u32(rows+24*mid+4));prev=norm(r,b,u32(rows+24*(mid-1)),u32(rows+24*(mid-1)+4));
    if(d>prev)u=mid;else{next=norm(r,b,u32(rows+24*(mid+1)),u32(rows+24*(mid+1)+4));l=mid;if(d<=next){found=1;local=mid;localdist=d;break;}}}
   if(!found){if(mid==l+1){local=l;localdist=prev;}if(mid==u-1){local=u;localdist=next;}}
   if(localdist<dist){dist=localdist;best=local;}
  }
  uint32_t radius=u32(rows+24*best+16),d=fu(sqrt((double)dist)),v=radius>=d?256:radius+400>=d?((radius+400-d)<<8)/400:0;if((uint16_t)v>weight)weight=(uint16_t)v;
 }return weight;
}
static void candidates(unsigned char*c,const unsigned char*k){
 unsigned n=u32(c+0xdb5c);w32(c+0xdd30,0);w32(c+0xdd34,n);c[0xdd2c]=n!=0;if(!n)return;
 uint32_t sumr=0,sumb=0,sumw=0,bright[8],bsum=0;
 for(unsigned i=0;i<n;++i){const unsigned char*p=c+0xdb6c+40*i,*raw=c+0x37464+40*i;w16(c+0xa874f+2*i,c[0xdb61+i]);w16(c+0xa875f+2*i,u32(p+36));
  for(unsigned q=0;q<3;++q){w16(c+0xa876f+16*q+2*i,u32(raw+4*q));w16(c+0xa879f+16*q+2*i,u32(p+4*q));}
  if(c[0xdb61+i]){uint32_t r=u32(p),b=u32(p+8),v=confidence(c,k,r,b);w32(c+0xdd38+40*i,r);w32(c+0xdd40+40*i,b);w16(c+0xdd54+40*i,v);v*=u32(k+0x16448c+4*i);sumr+=r*v;sumb+=b*v;sumw+=v;}
  bright[i]=fu(((double)u32(raw)*0.3+(double)u32(raw+4)*0.6)+(double)u32(raw+8)*0.1);bsum+=bright[i];w16(c+0xa8725+2*i,bright[i]);
 }
 if(!sumw)return;uint32_t r=sumr/sumw,b=sumb/sumw;sumr=sumb=sumw=0;
 for(unsigned i=0;i<n;++i){unsigned char*p=c+0xdd38+40*i;if(!u16(p+28))continue;uint32_t x=u32(p),y=u32(p+8);int64_t dx=ab((int64_t)x-r),dy=ab((int64_t)y-b),d=(dx>dy?dx:dy)-u32(k+0x16447c);unsigned v;
  if(d>=400){w16(p+28,0);continue;}if(d>0){v=(102400-d*256)/400;w16(p+28,v);}else v=256;sumr+=x*v;sumb+=y*v;sumw+=v;
 }if(!sumw)return;
 uint32_t mean=bsum/n,value=0,selected=0;for(unsigned i=0;i<n;++i){int32_t d=(int32_t)(bright[i]-mean);uint32_t mag=d<0?0-(uint32_t)d:(uint32_t)d;if((int64_t)(int32_t)mag<(int64_t)u32(k+0x164488)){value+=bright[i];++selected;}}
 if(!selected)c[0xdd2d]=0;else if(u32(k+0x164484)<selected){value/=selected;c[0xdd2d]=1;}
 w32(c+0xde90,value);w32(c+0xde78,sumr/sumw);w32(c+0xde80,sumb/sumw);w32(c+0xde98,sumw);w32(c+0xde9c,sumw>>8);if(sumw>>8)w32(c+0xdd30,1);
 w16(c+0xa8723,value);w16(c+0xa8701,sumr/sumw);w16(c+0xa8703,sumb/sumw);w16(c+0xa8705,u32(c+0xdd30));
}
static uint32_t models(unsigned char*c,const unsigned char*k){
 if(!u32(c+0xdd30)){c[0xee84]=0;return 0;}uint32_t r=u32(c+0xde78),b=u32(c+0xde80),sum=0;
 for(unsigned m=0;m<c[0xdea0];++m){const unsigned char*rows=c+0xdee4+2004*m;unsigned ct=5500;
  for(unsigned j=0;j<10;++j){unsigned row=(ct-2000)/100,old=ct;ct=hb_scene_temperature(c,(u32(rows+24*row+8)*r)>>12,(u32(rows+24*row+12)*b)>>12);if(ab((int32_t)(ct-old))<=49)break;}
  unsigned row=(ct-2000)/100;unsigned char*p=c+0xee4c+28*m;w32(p,u32(c+0xde9c));w32(p+4,(u32(rows+24*row+8)*r)>>12);w32(p+8,(u32(rows+24*row+12)*b)>>12);w32(p+12,ct);w32(p+16,row);w32(p+20,1);
  w32(p+20,du(u32(p)<<8,u32(c+0xdd34)));uint32_t d=fu(sqrt((double)norm(u32(p+4),u32(p+8),u32(c+0xb0bc8),u32(c+0xb0bd0))));w32(p+24,d);sum+=d;
 }
 for(unsigned m=0;m<c[0xdea0];++m){unsigned char*p=c+0xee4c+28*m;w32(p+20,du((sum-u32(p+24))*u32(p+20),sum));}
 uint32_t v,status=hb_detect_curve(k+0x164788,f32(c+0x37618),&v);if(status)return status;w32(c+0xee60,(u32(c+0xee60)*(256-v))>>8);w32(c+0xee7c,(u32(c+0xee7c)*v)>>8);
 uint32_t sr=0,sb=0,sw=0;for(unsigned m=0;m<c[0xdea0];++m){const unsigned char*p=c+0xee4c+28*m;uint32_t w=u32(p+20);sr+=u32(p+4)*w;sb+=u32(p+8)*w;sw+=w;}
 c[0xee84]=sw!=0;if(sw){w32(c+0xeea0,sr/sw);w32(c+0xeea8,sb/sw);w32(c+0xee88,sr/sw);w32(c+0xee90,sb/sw);w16(c+0xa8707,sr/sw);w16(c+0xa8709,sb/sw);}return 0;
}
static uint32_t atmos(unsigned char*c,const unsigned char*k,unsigned second){
 if(!u32(c+0xdd30))return 0;size_t red=second?0xee88:0xeea0,blue=second?0xee90:0xeea8,diag=second?0xa8713:0xa870b;
 uint32_t r=u32(c+red),b=u32(c+blue),ct=hb_scene_temperature(c,r,b),gr=0,gb=0;int32_t tint=hb_temperature_distance(c,ct,r,b);w16(c+diag,ct);w16(c+diag+2,tint);
 uint32_t status=hb_atmosphere_gains(k+(second?0x1678cc:0x1647c8),ct,f32(c+0x37618),(float)tint,&gr,&gb);if(status)return status;r=(r*gr)>>12;b=(b*gb)>>12;w32(c+red,r);w32(c+blue,b);
 if(!second){w32(c+0xeea4,4096);w32(c+0xee8c,4096);w32(c+0xee88,r);w32(c+0xee90,b);}w16(c+diag+4,r);w16(c+diag+6,b);return 0;
}
static uint32_t extent(unsigned char*c,float zoom,uint32_t*position){
 uint32_t width=u32(c+32),height=u32(c+36);float fraction=1.0f-1.0f/zoom,half=fraction*0.5f;uint32_t low[2]={fu((fraction*(float)width)*0.5f),fu((fraction*(float)height)*0.5f)},high[2]={fu((1.0f-half)*(float)width),fu((1.0f-half)*(float)height)},span[2]={fu((float)width/zoom),fu((float)height/zoom)},coverage[2];
 for(unsigned i=0;i<2;++i){uint32_t a=u32(c+0xdcac+4*i),b=a+3*u32(c+0xdcb4+4*i);a=a>low[i]?a:low[i];a=a<high[i]?a:high[i];b=b>low[i]?b:low[i];b=b<high[i]?b:high[i];a=fu((float)a);b=fu((float)b);coverage[i]=du((b-a)<<12,span[i]);}
 uint32_t v=coverage[0]>coverage[1]?coverage[0]:coverage[1];if(v>4096)v=4096;
 uint32_t x=u32(c+0xdcec)-(uint32_t)((int32_t)width/2)+(u32(c+0xdcf4)>>1),y=u32(c+0xdcf0)-(uint32_t)((int32_t)height/2)+(u32(c+0xdcf8)>>1);if((int32_t)x<0)x=0-x;if((int32_t)y<0)y=0-y;x<<=12;y<<=12;uint32_t den=span[0]>>1;uint32_t pos=du(x,den)<du(y,den)?du(y,den):du(x,den);*position=(int32_t)pos<4096?pos:4096;return v;
}
static uint32_t weight(unsigned char*c,const unsigned char*k){
 uint32_t z=u32(c+0xb20f8);if((z>>4)<=624)return 225;float zoom=(float)(z/10000);uint32_t mix=u16(c+0x3da50)+u16(c+0x3da56),brightness=u32(c+0xde90),rr=u32(c+0xb0bbc),bb=u32(c+0xb0bc4);float ev=f32(c+0x37618);
 if(c[0xe0bb0]==1){rr=u16(c+0xe0bb6);bb=u16(c+0xe0bb8);}w16(c+0xa8737,mix);w16(c+0xa873d,rr);w16(c+0xa873f,bb);
 if(c[0xee84]){uint32_t r=u32(c+0xeea0),b=u32(c+0xeea8);int64_t dr=(int64_t)r-rr,db=(int64_t)b-bb;uint32_t xr=dl(ab(dr)*4096,dr>0?r:rr),xb=dl(ab(db)*4096,db>0?b:bb),distance=xr>xb?xr:xb;
  uint32_t count=u32(c+40),sum=0,tolr=(u32(k+0x16ab18)*r)>>12,tolb=(u32(k+0x16ab1c)*b)>>12;
  for(unsigned i=0;i<count;++i){const unsigned char*p=c+0xf450+40*i;int32_t dx=(uint32_t)ab((int64_t)u32(p)-r)-tolr,dy=(uint32_t)ab((int64_t)u32(p+8)-b)-tolb;uint32_t v=256;if(dx>0||dy>0){int32_t d=dx>dy?dx:dy;uint32_t t=500-(uint32_t)d;if((int32_t)t<0)t=0;v=(t<<8)/500;}sum+=v;}
  w16(c+0xa8741,distance);const unsigned char*p=k+0x16ab20;uint32_t value=256;if(p[0]){unsigned a,bx;brackets(p+2,p[0],64,1,(uint16_t)distance,&a,&bx);const unsigned char*x=p+2+64*a,*y=p+2+64*bx;int32_t query=(int16_t)(du(sum<<12,count)>>8);value=interp(u16(x),u16(y),short_curve(x+4,x[2],query),short_curve(y+4,y[2],query),(float)(uint16_t)distance);}w32(c+0xeeac,value);
  uint32_t pos,sz;if(c[0xe0bb0]==1){sz=u16(c+0xe0bb2);pos=u16(c+0xe0bb4);}else sz=extent(c,zoom,&pos);w16(c+0xa8739,sz);w16(c+0xa873b,pos);
  uint32_t s=curve(c,k,0x16aa58,(float)sz,0xeebc);if(s)return s;s=curve(c,k,0x16aad8,(float)(int32_t)pos,0xeeb8);if(s)return s;s=curve(c,k,0x16aa98,(float)u32(c+0xde98),0xeec0);if(s)return s;
 }
 const unsigned char*p=k+0x16aee4;if(p[0]){unsigned a,b;brackets(p+2,p[0],934,1,(uint16_t)mix,&a,&b);const unsigned char*x=p+2+934*a,*y=p+2+934*b;w32(c+0xeec4,interp(u16(x),u16(y),hb_face_brightness(x,ev,brightness),hb_face_brightness(y,ev,brightness),(float)(uint16_t)mix));}
 uint32_t v=u32(c+0xeec4);w16(c+0xa8743,u32(c+0xeeac));w16(c+0xa8745,u32(c+0xeebc));w16(c+0xa8747,u32(c+0xeeb8));w16(c+0xa8749,v);
 v=(v*u32(c+0xeeac))>>8;v=(v*u32(c+0xeebc))>>8;v=(v*u32(c+0xeec0))>>8;v=(v*u32(c+0xeeb8))>>8;w32(c+0xeeac,v);w16(c+0xa874b,v);return 0;
}
void hb_face_smooth(unsigned char*c,const unsigned char*k){
 uint32_t v=u32(c+0xeeac)<<12;w32(c+0xeeac,v);
 if(!k[0x16a9ec]||c[0xe0bb0]==1)w32(c+0xeeb0,v);
 else if(!c[0xef40]||c[0xd338]==1){w32(c+0xef4c,v);w32(c+0xef50,v);w32(c+0xeeb0,v);w32(c+0xef44,u32(k+0x16a9f0));w32(c+0xef48,u32(k+0x16a9f4));c[0xef40]=1;}
 else{uint32_t a=u32(c+0xef44),b=u32(c+0xef48),old=u32(c+0xef50),first=ds(u32(c+0xef4c)*(128-a)+v*a,128),second=old+(uint32_t)ds((first-old)*b,128);w32(c+0xef4c,first);w32(c+0xef50,second);w32(c+0xeeb0,second);}
 w32(c+0xeeac,u32(c+0xeeac)>>12);w32(c+0xeeb0,u32(c+0xeeb0)>>12);
}
static void stability(unsigned char*c,const unsigned char*k){
 if(!u32(c+0xdd30)){w16(c+0xef0c,0);return;}if(!u32(c+0xdb58))return;
 uint32_t now[6]={(uint16_t)(u32(c+0xdcec)+(u32(c+0xdcf4)>>1)),(uint16_t)(u32(c+0xdcf0)+(u32(c+0xdcf8)>>1)),(uint16_t)(3*u32(c+0xdcf4)),(uint16_t)(3*u32(c+0xdcf8)),u32(c+0xee88),u32(c+0xee90)};
 const unsigned offsets[6]={0xeefc,0xef00,0xef04,0xef08,0xeef0,0xeef8};int16_t delta[6]={0};uint16_t n=u16(c+0xef0e);unsigned reset=!n;
 if(n){for(unsigned i=0;i<6;++i){unsigned d=i<4?2+(i&1):i;delta[i]=dl(((int64_t)now[i]-u32(c+offsets[i]))*4096,now[d]);if(ab(delta[i])>=(int32_t)u32(k+0x16a9d0+4*i))reset=1;}if(!reset&&u32(k+0x16a9e8)>n)++n;}
 if(reset){n=1;w16(c+0xef0c,0);}w16(c+0xef0e,n);for(unsigned i=0;i<6;++i)w32(c+offsets[i],now[i]);if(u32(k+0x16a9e8)<=n)w16(c+0xef0c,1);
 w16(c+0xa880f,u16(c+0xef0c));w16(c+0xa8811,n);for(unsigned i=0;i<6;++i)w16(c+0xa8813+2*i,ab(delta[i]));
}
static uint32_t rel(uint32_t a,uint32_t b){return dl(ab((int64_t)a-b)*4096,b);}
static void remember(unsigned char*c,const unsigned char*k){
 uint32_t state=u32(c+0xef34),mode=0;
 if(u16(c+0xef0c)==1){if(state==3||state==4)hb_face_smooth(c,k);else w32(c+0xeeb0,u32(c+0xeeac));memcpy(c+0xeed4,c+0xee88,12);memcpy(c+0xeec8,c+0xeea0,12);memcpy(c+0xeee4,c+0xb0bc8,12);w32(c+0xeee0,u32(c+0xeeb0));mode=2;}
 else if(state==3||state==4){mode=2;w32(c+0xeeb0,u32(c+0xeee0));}
 else if(state==6&&c[0xb0bac]){uint32_t r=u32(c+0xeec8),b=u32(c+0xeed0),tr=(u32(k+0x16a9fc)*r)>>12,tb=(u32(k+0x16aa00)*b)>>12,hits=0,count=u32(c+40);
  for(unsigned i=0;i<count;++i){const unsigned char*p=c+0xf450+40*i;if(ab((int64_t)u32(p)-r)<tr&&ab((int64_t)u32(p+8)-b)<tb)++hits;}uint32_t ratio=du(hits<<12,count),dr=rel(u32(c+0xeee4),u32(c+0xb0bc8)),db=rel(u32(c+0xeeec),u32(c+0xb0bd0));w16(c+0xa882f,ratio);w16(c+0xa8831,dr);w16(c+0xa8833,db);
  unsigned keep=(dr<u32(k+0x16aa04)&&db<u32(k+0x16aa08))||ratio>u32(k+0x16a9f8);dr=rel(u32(c+0xeed4),u32(c+0xee88));db=rel(u32(c+0xeedc),u32(c+0xee90));w16(c+0xa8835,dr);w16(c+0xa8837,db);
  if(u32(c+0xdd30)&&dr<u32(k+0x16aa04)&&db<u32(k+0x16aa08)){mode=keep?2:0;w32(c+0xeeb0,u32(c+0xeee0));}
  else if(keep){mode=1;if(u32(c+0xef10)>u32(k+0x16aa2c)){w32(c+0xeeac,0);hb_face_smooth(c,k);w32(c+0xeee0,u32(c+0xeeb0));}}
  else w32(c+0xeeb0,u32(c+0xeee0));
 }else w32(c+0xeeb0,u32(c+0xeee0));
 w32(c+0xef38,mode);w16(c+0xa881f,mode);w16(c+0xa874d,u32(c+0xeeb0));w16(c+0xa8821,u32(c+0xeee0));for(unsigned i=0;i<3;++i){w16(c+0xa8823+2*i,u32(c+0xeed4+4*i));w16(c+0xa8829+2*i,u32(c+0xeec8+4*i));}
}
static void transitions(unsigned char*c){
 uint32_t s=u32(c+0xef34),stable=u16(c+0xef0c);unsigned diag=s;
 if(stable==1&&!s){s=1;w32(c+0xef1c,0);w32(c+0xef14,0);w32(c+0xef10,0);}
 else if(u32(c+0xef1c)==1&&s==1){s=2;w32(c+0xef10,0);memset(c+0xef20,0,8);memset(c+0xef18,0,8);}
 else if(stable==1&&s==5){s=2;w32(c+0xef24,0);w32(c+0xef20,0);w32(c+0xef28,0);w32(c+0xef18,0);w32(c+0xef10,0);}
 else if((u32(c+0xef20)==1&&s==2)||(stable==1&&s==6)){if(s==2){w32(c+0xef20,0);w32(c+0xef18,0);}else w32(c+0xef30,0);w32(c+0xef2c,0);s=c[0xf028]==1?4:3;if(c[0xef40]==1)c[0xef40]=0;w32(c+0xef10,0);}
 else if(u32(c+0xef2c)==1&&(s==3||s==4)){s=6;memset(c+0xef2c,0,8);w32(c+0xef10,0);}
 else if(s==2&&u32(c+0xef24)==1){s=5;memset(c+0xef24,0,8);w32(c+0xef18,0);w32(c+0xef10,0);}
 else if((s==6&&u32(c+0xef30)==1)||(s==5&&u32(c+0xef28)==1)||(s==1&&stable!=1)){s=0;w32(c+0xef10,0);w32(c+0xef28,0);w32(c+0xef30,0);}
 diag=s;w32(c+0xef34,s);w16(c+0xa8839,diag);
}
static void output(unsigned char*c,const unsigned char*k){
 unsigned s=u32(c+0xef34);uint32_t n=u32(c+0xef10),stable=u16(c+0xef0c);
 if(s==0||s==1||s==5)c[0xee84]=0;else if(s<=6){c[0xee84]=1;memcpy(c+0xee94,c+0xeed4,12);w32(c+0xeeb4,u32(c+0xeee0));}
 if(s==1){uint32_t v=u32(c+0xef14);if(stable==1)w32(c+0xef14,++v);if(v==u32(k+0x16aa0c))w32(c+0xef1c,1);w16(c+0xa883b,v);}
 else if(s==2){uint32_t v=u32(c+0xef18);if(stable==1){n=0;w32(c+0xef18,++v);}else ++n;w32(c+0xef10,n);
  if(n==u32(k+0x16aa14))w32(c+0xef24,1);else if(v==u32(k+0x16aa10))w32(c+0xef20,1);w16(c+0xa883b,v);w16(c+0xa883d,n);}
 else if(s==3||s==4){n=stable==1?0:n+1;w32(c+0xef10,n);if(n==u32(k+(s==3?0x16aa18:0x16aa1c)))w32(c+0xef2c,1);w16(c+0xa883d,n);}
 else if(s==5){w32(c+0xef10,++n);if(n==u32(k+0x16aa20))w32(c+0xef28,1);w16(c+0xa883d,n);}
 else if(s==6){uint32_t mode=u32(c+0xef38);n=mode==2?0:n+1;w32(c+0xef10,n);if(n==u32(k+0x16aa24)||(!mode&&n==u32(k+0x16aa28)))w32(c+0xef30,1);w16(c+0xa883d,n);}
 w16(c+0xa871b,c[0xee84]);w16(c+0xa871d,u32(c+0xeeb4));w16(c+0xa871f,u32(c+0xee94));w16(c+0xa8721,u32(c+0xee9c));
}
static int valid(const unsigned char*c,const unsigned char*k){
 if(u32(c+44)>8||u32(c+0xdb5c)>8||c[0xdea0]>2||u32(c+40)>1024)return 0;
 if(!isfinite(f32(c+0x37618))||!isfinite(f32(c+0x9c1a4))||!isfinite(f32(k+0x164470)))return 0;
 if(c[0xd902]==1&&c[0xe0bb0]!=1){if(!u32(c+24)||!u32(c+28)||(uint64_t)u32(c+24)*u32(c+28)>1024)return 0;for(unsigned i=0;i<32;++i)if(!isfinite(f32(c+0xef74+4*i)))return 0;}
 for(unsigned m=0;m<c[0xdea0];++m){unsigned n=k[0x1644b0+364*m];if(!n||n>16)return 0;for(unsigned j=0;j<n;++j){uint32_t v=u32(c+0xdea4+2004*m+4*j);if(v>80||(j&&v<u32(c+0xdea4+2004*m+4*j-4)))return 0;}}
 const size_t curves[]={0x164788,0x16aa58,0x16aa98,0x16aad8};for(unsigned i=0;i<4;++i)if(k[curves[i]]>8)return 0;
 for(unsigned m=0;m<2;++m){const unsigned char*t=k+(m?0x1678cc:0x1647c8);if(t[0]>8)return 0;for(unsigned e=0;e<t[0];++e){const unsigned char*q=t+4+1568*e;if(!q[4]||q[4]>15)return 0;for(unsigned j=0;j<q[4];++j){const unsigned char*r=q+8+104*j;if(!r[4]||r[4]>8)return 0;}}}
 const unsigned char*p=k+0x16ab20;if(p[0]>15)return 0;for(unsigned i=0;i<p[0];++i)if(!p[4+64*i]||p[4+64*i]>15)return 0;
 p=k+0x16aee4;if(p[0]>4)return 0;for(unsigned i=0;i<p[0];++i){const unsigned char*q=p+2+934*i;if(!q[2]||q[2]>15)return 0;for(unsigned j=0;j<q[2];++j)if(!q[5+62*j]||q[5+62*j]>15)return 0;}
 return 1;
}
uint32_t hb_face_process(unsigned char*c,const unsigned char*k){
 if(!c||!k)return HB_PREP_UNSUPPORTED;if(!k[0x16446c])return 0;
 if(!c[0xdb50]&&c[0xe0bb0]!=1){if(c[0xdb51]){c[0xee84]=0;memset(c+0xef10,0,40);}return 0;}
 if(!valid(c,k))return HB_PREP_UNSUPPORTED;uint32_t s=geometry(c);if(s)return s;capture(c,k);candidates(c,k);s=models(c,k);if(s)return s;s=atmos(c,k,0);if(s)return s;s=atmos(c,k,1);if(s)return s;s=weight(c,k);if(s)return s;
 if(c[0xe0bb0]==1){w32(c+0xeeb4,u32(c+0xeeac));w32(c+0xee94,u32(c+0xee88));w32(c+0xee9c,u32(c+0xee90));w16(c+0xa871b,c[0xee84]);w16(c+0xa874d,u32(c+0xeeac));w16(c+0xa871d,u32(c+0xeeac));w16(c+0xa871f,u32(c+0xee88));w16(c+0xa8721,u32(c+0xee90));return 0;}
 stability(c,k);remember(c,k);transitions(c);output(c,k);return 0;
}
