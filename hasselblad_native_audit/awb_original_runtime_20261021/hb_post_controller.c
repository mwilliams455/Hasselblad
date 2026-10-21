/* SPDX-License-Identifier: MIT */
#include "hb_post_controller.h"
#include "hb_scene_controller.h"
#include "hb_scene_optimizer.h"
#include "hb_history.h"
#include "hb_atmosphere.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <stddef.h>
#include <string.h>
static uint32_t u32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const unsigned char*p){float v;memcpy(&v,p,4);return v;}
static void w32(unsigned char*p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char*p,uint16_t v){memcpy(p,&v,2);}
static void wf(unsigned char*p,float v){memcpy(p,&v,4);}
static uint32_t fu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int32_t fs(double v){return isnan(v)?0:v>=2147483647.0?INT32_MAX:v<=-2147483648.0?INT32_MIN:(int32_t)v;}
static uint32_t maxu(uint32_t a,uint32_t b){return a>b?a:b;}
static uint32_t sd128(uint32_t v){return (uint32_t)((int32_t)v/128);}
static void golden(unsigned char*p,uint32_t scale){
    for(unsigned i=0;i<6;++i)w32(p+0x74+4*i,(u32(p+4+4*i)*scale)/4096);
    p[0x70]=p[0];
}
uint32_t hb_post_inverse(const unsigned char*c,const unsigned char*k,const hb_temperature_model*m,uint32_t ct,float tint,uint32_t scale,uint32_t out[3]){
    if(!m||!m->isotemperature_31x4)return HB_PREP_UNSUPPORTED;
    const float*t=m->isotemperature_31x4;float wanted=1000000.0f/(float)ct;
    unsigned i=0;while(i<29&&!(wanted<t[4*(i+1)]))++i;
    const float*a=t+4*i,*b=a+4;float f=(b[0]-wanted)/(b[0]-a[0]);double g=1.0-(double)f;
    float n0=(float)sqrt((double)(a[3]*a[3])+1.0),n1=(float)sqrt((double)(b[3]*b[3])+1.0);
    float nx=(float)(g*(double)(1.0f/n1)+(double)(f*(1.0f/n0)));
    float ny=(float)(g*(double)(b[3]/n1)+(double)(f*(a[3]/n0)));
    float norm=sqrtf(nx*nx+ny*ny),mat[9];
    uint32_t st=hb_temperature_matrix(k,c[0x990dc]==1&&k[0x133518],rf(c+0x990d8),(float)ct,mat);if(st)return st;
    float u=(tint/-3000.0f)*(nx/norm)+(float)(g*(double)b[1]+(double)(f*a[1]));
    float v=(tint/-3000.0f)*(ny/norm)+(float)(g*(double)b[2]+(double)(f*a[2]));
    double den=(double)u+(double)v*-4.0+2.0;
    float x=(float)(((double)u*1.5)/den),y=(float)((double)v/den),z=(1.0f-x)-y,rgb[3];
    for(unsigned j=0;j<3;++j){float p=mat[3*j]*x,q=mat[3*j+1]*y;float s=p+q;rgb[j]=mat[3*j+2]*z+s;}
    float maximum=rgb[0]>rgb[1]?rgb[0]:rgb[1];maximum=maximum>rgb[2]?maximum:rgb[2];
    for(unsigned j=0;j<3;++j){float ratio=10;if(!((double)rgb[j]<0.00001)){float r=maximum/rgb[j];if(!(r>10))ratio=r;}out[j]=fu(ratio*(float)scale);}return 0;
}
static void remap(const unsigned char*c,uint32_t ct,uint32_t*r,uint32_t*b){
    unsigned i=ct<=2000?0:ct>10000?80:(ct-2000)/100;
    *r=fu(((float)*r/(float)u32(c+0x348+16*i))*(float)u32(c+0x858+16*i));
    *b=fu(((float)*b/(float)u32(c+0x34c+16*i))*(float)u32(c+0x85c+16*i));
}
uint32_t hb_post_category(unsigned char*c,const unsigned char*k){
    uint32_t mode=u32(c+0x194),result=0;
    if(mode>2)result=u16(c+0xa84de + 2*c[0x194]);
    else if(mode<2){uint32_t r=u32(c+0xb0b20),b=u32(c+0xb0b28),n=u32(k+0x139970),count=u32(c+0x28),cat=8,bestdist=0,bestscore=0;
        if(n>9||count>4096)return HB_PREP_UNSUPPORTED;
        if(c[0x990dc]==1)remap(c,hb_scene_temperature(c,r,b),&r,&b);
        for(unsigned i=0;i<n;++i){const unsigned char*z=k+0x139978+0x38*i;uint32_t dist=0,hits=0;w32(c+0xb1408+4*i,0);
            if(hb_zone_contains(z,r,b)==246){int32_t a=(int32_t)(r-u32(z)),d=(int32_t)(u32(z+4)-r),e=(int32_t)(b-u32(z+8)),f=(int32_t)(u32(z+12)-b);dist=(uint32_t)(a<d?a:d)+(uint32_t)(e<f?e:f);if(dist>bestdist){bestdist=dist;cat=u32(z-4);}}
            for(unsigned j=0;j<count;++j){const unsigned char*p=c+0xf450+40*j;if(!u32(p+20))continue;uint32_t rr=u32(p),bb=u32(p+8);if(c[0x990dc]==1)remap(c,u32(p+12),&rr,&bb);hits+=hb_zone_contains(z,rr,bb)==246;}
            uint32_t q=dist*100;/* The original selects 100 below this threshold. */
            q=q<151500?100:(uint32_t)(((uint64_t)q*0x057619f1)>>37);
            uint32_t score=hits+q;if(bestscore<score){bestscore=score;cat=i;}w32(c+0xb1408+4*i,hits);
        }if(cat<9)result=u16(c+0xa84cc+2*cat);
    }
    w32(c+0xb0cb4,result);w32(c+0xb0d50,result);w32(c+0xb0b7c,result);return 0;
}
/* All hierarchy axes have eight storage slots. Endpoint pairs intentionally
 * invoke interpolation too, preserving its equal-knot arithmetic. */
static int bracket(const unsigned char*p,unsigned n,size_t stride,float x,int signed_axis,unsigned*lo,unsigned*hi){
    if(!n||n>8)return 0;*lo=*hi=0;
    float first=signed_axis?(float)(int32_t)u32(p):(float)u32(p);
    float last=signed_axis?(float)(int32_t)u32(p+(n-1)*stride):(float)u32(p+(n-1)*stride);
    if(x<=first)return 1;if(x>=last){*lo=*hi=n-1;return 1;}
    for(unsigned i=1;i<n;++i){float v=signed_axis?(float)(int32_t)u32(p+i*stride):(float)u32(p+i*stride);if(x<=v){*lo=i-1;*hi=i;return 1;}}return 0;
}
static int bracket_integer(const unsigned char*p,unsigned n,size_t stride,uint32_t x,int sign,unsigned*lo,unsigned*hi){
    if(!n||n>8)return 0;*lo=*hi=0;
    uint32_t first=u32(p),last=u32(p+(n-1)*stride);
    if(sign?(int32_t)x<=(int32_t)first:x<=first)return 1;
    if(sign?(int32_t)x>=(int32_t)last:x>=last){*lo=*hi=n-1;return 1;}
    for(unsigned i=1;i<n;++i){uint32_t v=u32(p+i*stride);if(sign?(int32_t)x<=(int32_t)v:x<=v){*lo=i-1;*hi=i;return 1;}}return 0;
}
uint32_t hb_post_gate(const unsigned char*c,unsigned slot,const unsigned char*row,uint32_t*out){
    unsigned n=row[4];if(!n){*out=256;return 0;}if(n>8||slot>1)return HB_PREP_UNSUPPORTED;
    uint32_t x=u16(c+0x3da54+2*slot);unsigned lo=0,hi=0;
    if(x>=row[8+8*(n-1)])lo=hi=n-1;else if(x>row[8]){hi=1;while(hi<n&&x>row[8+8*hi])++hi;if(hi==n)return 148;lo=hi-1;}
    *out=hb_scene_interpolate(row[8+8*lo],row[8+8*hi],u32(row+12+8*lo),u32(row+12+8*hi),(float)x);return 0;
}
static uint32_t merge_tree(const unsigned char*c,const unsigned char*row,unsigned depth,uint32_t*out,uint32_t*special){
    static const size_t strides[]={0x1a48,0x348,0x68,12},selectors[]={0xb0c04,0x8415c,0x84160,0x84154};
    unsigned n=row[4],lo,hi;if(!n){*out=*special=0;return 0;}float x=(float)u32(c+selectors[depth]);
    if(!bracket_integer(row+8,n,strides[depth],u32(c+selectors[depth]),0,&lo,&hi))return n>8?HB_PREP_UNSUPPORTED:148;
    const unsigned char*a=row+8+lo*strides[depth],*b=row+8+hi*strides[depth];uint32_t av[2],bv[2],st;
    if(depth==3){av[0]=u32(a+4);av[1]=u32(a+8);bv[0]=u32(b+4);bv[1]=u32(b+8);}
    else{st=merge_tree(c,a,depth+1,av,av+1);if(st)return st;st=merge_tree(c,b,depth+1,bv,bv+1);if(st)return st;}
    *out=hb_scene_interpolate(u32(a),u32(b),av[0],bv[0],x);*special=hb_scene_interpolate(u32(a),u32(b),av[1],bv[1],x);return 0;
}
uint32_t hb_post_merge_row(const unsigned char*c,const unsigned char*row,uint32_t*a,uint32_t*b){return merge_tree(c,row,0,a,b);}
static uint32_t iso_tree(const unsigned char*row,const uint32_t x[3],unsigned depth,uint32_t*out,uint32_t*blue){
    static const size_t strides[]={0x348,0x68,12};unsigned n=row[4],lo,hi;if(!n)return depth==2?200:198;
    float wanted=depth==2?(float)(int32_t)x[depth]:(float)x[depth];
    if(!bracket_integer(row+8,n,strides[depth],x[depth],depth==2,&lo,&hi))return n>8?HB_PREP_UNSUPPORTED:198;
    const unsigned char*a=row+8+lo*strides[depth],*b=row+8+hi*strides[depth];uint32_t av[2],bv[2],st;
    if(depth==2){av[0]=u32(a+4);av[1]=u32(a+8);bv[0]=u32(b+4);bv[1]=u32(b+8);}
    else{st=iso_tree(a,x,depth+1,av,av+1);if(st)return st;st=iso_tree(b,x,depth+1,bv,bv+1);if(st)return st;}
    *out=hb_scene_interpolate(u32(a),u32(b),av[0],bv[0],wanted);*blue=hb_scene_interpolate(u32(a),u32(b),av[1],bv[1],wanted);return 0;
}
uint32_t hb_post_iso_row(const unsigned char*row,uint32_t iso,uint32_t ct,int32_t tint,uint32_t*r,uint32_t*b){uint32_t x[]={iso,ct,(uint32_t)tint};return iso_tree(row,x,0,r,b);}
uint32_t hb_post_smooth(unsigned char*s,uint32_t a,uint32_t b,const unsigned char*in,unsigned char*out,uint32_t scale){
    for(unsigned i=0;i<6;++i){size_t first=8+4*(i%3)+24*(i/3),second=first+12;
        uint32_t x=sd128(u32(s+first)*(128-a)+u32(in+4+4*i)*a);w32(s+first,x);
        x=u32(s+second)+sd128((x-u32(s+second))*b);w32(s+second,x);w32(out+4+4*i,x);
    }golden(out,scale);return 0;
}
static void coeff(unsigned char*c,const unsigned char*k,size_t off,int saved){
    w32(c+0x4314,u32(k+off));w32(c+0x4318,u32(k+off+4));w32(c+0x42dc,u32(k+off+8));w32(c+0x42e0,u32(k+off+12));
    if(saved){w32(c+0x4350,u32(k+off+8));w32(c+0x4354,u32(k+off+12));}
}
static void pair(unsigned char*c,uint32_t a,uint32_t b,int saved){w32(c+0x4314,a);w32(c+0x4318,b);w32(c+0x42dc,a);w32(c+0x42e0,b);if(saved){w32(c+0x4350,a);w32(c+0x4354,b);}}
static void transition(unsigned char*c,const unsigned char*k){
    if(u32(c+0x4360)==1)c[0x42c9]=1;
    if(c[0x42c9]==1){c[0x42c9]=0;w16(c+0x42cc,0);if(u32(c+0x42d4)!=1){w32(c+0x42d4,1);coeff(c,k,0x60,1);}}
    uint32_t timer=u16(c+0x42cc);if(timer<240)w16(c+0x42cc,(uint16_t)(timer+1));else if(u32(c+0x42d4)){w32(c+0x42d4,0);coeff(c,k,0x44,1);}
    w32(c+0x434c,0);w32(c+0x4360,0);
}
uint32_t hb_post_publish(unsigned char*c,const unsigned char*k,const unsigned char*reawb){
    unsigned mode=c[0x194];
    if(mode>=10||(reawb&&reawb[0x1c]==1&&!reawb[0x21])||u32(c+0xb2020)==1||u16(c+0xa84f2+2*mode)!=1){
        for(unsigned i=0;i<2;++i){unsigned char*out=c+0xb0c48+0x9c*i;memcpy(out+4,c+0xb0b14,24);memcpy(out+0x74,c+0xb0b84,24);}c[0x42c8]=0;return 0;
    }
    uint32_t metric=u32(c+0x434c);
    if(!c[0x42c8]||c[0xd338]==1){
        for(unsigned j=0;j<2;++j){unsigned char*s=c+(j?0x42dc:0x4314);for(unsigned i=0;i<6;++i){size_t first=8+4*(i%3)+24*(i/3);uint32_t v=u32(c+0xb0b14+4*i);w32(s+first,v);w32(s+first+12,v);}memcpy(c+0xb0c48+0x9c*j,c+0xb0b10,0x9c);}
        coeff(c,k,0x44,1);w16(c+0x4358,(uint16_t)metric);w16(c+0x435a,(uint16_t)metric);w32(c+0x42cc,240);w16(c+0x42d0,2);c[0x42c9]=0;w32(c+0x42d4,0);w32(c+0x4360,0);w32(c+0x435c,0);c[0x42c8]=1;return 0;
    }
    if(k[0x5c]==1){
        if(k[0x138294]==1){unsigned cat=c[0xc4cc];if(cat||c[0xc4ce]!=1){if(cat>8)return HB_PREP_UNSUPPORTED;pair(c,u32(k+0x1385f8+0x58*cat),u32(k+0x1385fc+0x58*cat),1);w32(c+0x434c,u32(c+0xc44c));w32(c+0x4360,cat!=0);}else transition(c,k);}
        else{uint32_t state=u32(c+0xc434)?1:u32(c+0x84158)?0:2;w32(c+0x435c,state);
            if(state==2){w16(c+0x42cc,240);if(!u32(c+0x4360))w32(c+0x434c,0);else if(u32(c+0x4360)==1)w32(c+0x434c,u32(c+0xc43c));}
            else if(state==1){w16(c+0x42cc,240);if(u32(c+0x42d4)){w32(c+0x42d4,0);coeff(c,k,0x44,1);}w32(c+0x434c,u32(c+0xc44c));w32(c+0x4360,1);}else transition(c,k);
        }
    }else if(k[0x16446c]==1){uint32_t s=u32(c+0xef34);if(s>6)s=7;w32(c+0x4364,s);if(u32(c+0x4368)!=s){c[0x42ca]=1;w32(c+0x4368,s);}
        if(c[0x42ca]==1){c[0x42ca]=0;if(u32(c+0x42d8)!=s){w32(c+0x42d8,s);if(s<2||s==7)coeff(c,k,0x44,0);else{static const size_t offsets[]={0,0,0x16aa30,0x16aa40,0x16aa48,0x16aa38,0x16aa50};pair(c,u32(k+offsets[s]),u32(k+offsets[s]+4),0);}}}
    }else if(c[0x42d2]==1||c[0x42d3]==1){if(c[0x42d2]){if(c[0x42d3]==1)pair(c,u32(k+0x54),u32(k+0x58),0);else coeff(c,k,0x44,0);c[0x42d2]=0;}}
    else if(!c[0x990dc]){w16(c+0x42d0,2);c[0x42cf]=0;coeff(c,k,0x44,0);}
    else{if(c[0x42cf]){w16(c+0x42d0,0);c[0x42cf]=0;}uint32_t timer=u16(c+0x42d0);if(timer<=1){w16(c+0x42d0,(uint16_t)(timer+1));pair(c,128,128,0);}else coeff(c,k,0x44,0);}
    static const size_t from[]={0xb0b14,0xb0b1c,0x431c,0x4324,0x4328,0x4330};for(unsigned i=0;i<6;++i)w16(c+0xa85c2+2*i,(uint16_t)u32(c+from[i]));
    hb_post_smooth(c+0x4314,u32(c+0x4314),u32(c+0x4318),c+0xb0b10,c+0xb0c48,u32(k+0x80));
    uint32_t a=u32(c+0x42dc),b=u32(c+0x42e0);hb_post_smooth(c+0x42dc,a,b,c+0xb0b10,c+0xb0ce4,u32(k+0x80));
    uint32_t first=sd128(a*metric+(128-a)*u16(c+0x4358)),old=u16(c+0x435a),second=old+sd128((first-old)*b);w16(c+0x4358,(uint16_t)first);w16(c+0x435a,(uint16_t)second);
    uint32_t dr=u32(c+0x42e4)-u32(c+0xb0b14),db=u32(c+0x42ec)-u32(c+0xb0b1c);if((int32_t)dr<0)dr=0-dr;if((int32_t)db<0)db=0-db;
    c[0x42ce]=(int32_t)dr>127||(int32_t)db>=128;w16(c+0xa86ff,(uint16_t)second);return 0;
}
static uint32_t select_normal(unsigned char*c){
    unsigned char*a=c+0x84164,*b=a+0x74,*ha=c+0x40f8,*hb=ha+0x74;
    uint32_t wa=u16(c+0x3da50),wb=u16(c+0x3da52),st=0;
    if(a[0]&&b[0]){st=hb_post_blend_normal(c,wa,wb,a,b);if(st)return st;w32(c+0x4168,wa);w32(c+0x41dc,wb);memcpy(ha,a,0x70);memcpy(hb,b,0x70);}
    else if(b[0]){if(ha[0]){st=hb_post_blend_normal(c,u32(c+0x4168),wb,ha,b);if(st)return st;w32(c+0x4168,u32(c+0x4168)/2);w32(c+0x41dc,wb);}else memcpy(c+0x84128,b,44);memcpy(hb,b,0x70);}
    else if(a[0]){if(hb[0]){st=hb_post_blend_normal(c,wa,u32(c+0x41dc),a,hb);if(st)return st;w32(c+0x41dc,u32(c+0x41dc)/2);w32(c+0x4168,wa);}else memcpy(c+0x84128,a,44);memcpy(ha,a,0x70);}
    w32(c+0x84158,wa+wb);w32(c+0x8415c,maxu(u32(c+0x841cc),u32(c+0x84240)));return 0;
}
static uint32_t select_special(unsigned char*c,const unsigned char*k){
    uint32_t sums[9]={0},total=0,gate=0,metric=0;
    for(unsigned i=0;i<2;++i){unsigned slot=i+2;const unsigned char*cfg=k+0x15a30+0x2bd0*i;unsigned char*p=c+0x84164+0x74*slot,*old=c+0x40f8+0x74*slot;uint32_t weight=u32(p+112);if(cfg[0]!=1||!weight)continue;
        const unsigned char*source=p;int raw_measured=0;
        if(p[0])memcpy(old,p,0x74);
        else if(cfg[8]&&u32(c+0x8415c)&&u32(c+0x84158)){
            unsigned n=cfg[20],lo,hi;uint32_t factor=256;
            if(n){if(!bracket_integer(cfg+24,n,0x48,u32(c+0x8415c),0,&lo,&hi))return HB_PREP_UNSUPPORTED;
                const unsigned char*a=cfg+24+0x48*lo,*b=cfg+24+0x48*hi;uint32_t av,bv,st=hb_post_gate(c,i,a,&av);if(st)return st;st=hb_post_gate(c,i,b,&bv);if(st)return st;factor=hb_scene_interpolate(u32(a),u32(b),av,bv,(float)u32(c+0x8415c));}
            uint32_t product=u16(c+0x3da50+2*slot)*factor;w16(c+0x3da50+2*slot,(uint16_t)(product>>8));if(!(product&0xffff00))continue;
            for(unsigned j=0;j<2;++j){w32(p+4+12*j,u32(cfg+12));w32(p+8+12*j,4096);w32(p+12+12*j,u32(cfg+16));}memcpy(old,p,0x74);p[0]=1;raw_measured=1;
        }else{if(!old[0])continue;source=old;raw_measured=1;}
        for(unsigned j=0;j<9;++j)sums[j]+=u32(source+4+4*(raw_measured&&j>=6?j-3:j))*weight;
        total+=weight;gate=maxu(gate,u16(c+0x3da50+2*slot));metric=maxu(metric,u32(p+104));
    }
    if(total){for(unsigned j=0;j<6;++j)if(!sums[j])return 150;for(unsigned j=0;j<9;++j)w32(c+0x84100+4*j,sums[j]/total);c[0x840fc]=1;w32(c+0x84154,gate);w32(c+0x84160,metric);}return 0;
}
static uint32_t merge(unsigned char*c,const unsigned char*k){
    uint32_t normal=1,special=0;unsigned n=k[0xca078],lo,hi;
    if(n){float ev=rf(c+0x37618);if(!bracket(k+0xca07c,n,0xd248,ev,0,&lo,&hi))return HB_PREP_UNSUPPORTED;const unsigned char*a=k+0xca07c+0xd248*lo,*b=k+0xca07c+0xd248*hi;uint32_t av[2],bv[2],st=hb_post_merge_row(c,a,av,av+1);if(st)return st;st=hb_post_merge_row(c,b,bv,bv+1);if(st)return st;normal=hb_scene_interpolate(u32(a),u32(b),av[0],bv[0],ev);special=hb_scene_interpolate(u32(a),u32(b),av[1],bv[1],ev);}
    uint32_t total=normal+special;if(!total)return 149;
    w32(c+0x84150,normal);w32(c+0x84124,special);w16(c+0xa862e,(uint16_t)normal);w16(c+0xa8630,(uint16_t)special);
    static const size_t diag[]={0x8412c,0x84134,0x84100,0x84108};for(unsigned i=0;i<4;++i)w16(c+0xa8626+2*i,(uint16_t)u32(c+diag[i]));
    unsigned char*out=c+0xb0b10,*a=c+0x84128,*b=c+0x840fc;int va=a[0]==1&&normal,vb=b[0]==1&&special;out[0]=1;
    if(va&&vb){for(unsigned i=0;i<6;++i)w32(out+4+4*i,(u32(a+4+4*i)*normal+u32(b+4+4*i)*special)/total);memcpy(c+0xc564,a,44);memcpy(c+0xc538,b,44);}
    else if(va)memcpy(out,a,44);else if(vb)memcpy(out,b,44);else out[0]=0;
    if(k[0x16446c]&&c[0xee84]){if(!out[0])memcpy(out,c+0xb0bac,0x9c);uint32_t w=u32(c+0xeeb4);if(w-1<=255){w32(out+4,(uint32_t)(((uint64_t)(256-w)*u32(out+4)+(uint64_t)w*u32(c+0xee94))>>8));w32(out+12,(uint32_t)(((uint64_t)(256-w)*u32(out+12)+(uint64_t)w*u32(c+0xee9c))>>8));w32(out+8,4096);out[0]=1;}}
    if(c[0xd338]==1){memcpy(out,c+0xd33c,0x9c);memcpy(c+0xb0bac,c+0xd33c,0x9c);}return 0;
}
static uint32_t combined(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    unsigned char*p=c+0xb0b10;
    if(!p[0]){memcpy(p,c+0xb0bac,0x9c);p[0]=0;c[0xb0c48]=c[0xb0ce4]=0;memcpy(c+0xeff8,c+0xf010,24);return 247;}
    for(unsigned i=0;i<2;++i){float ct,tint;uint32_t st=hb_temperature_calibrated(c,k,m,u32(p+4+12*i),u32(p+8+12*i),u32(p+12+12*i),&ct,&tint);if(st)return st;w32(p+0x58+4*i,fu(ct));wf(p+0x60+4*i,tint);}
    w32(p+0x68,maxu(u32(c+0x8415c),u32(c+0x84160)));w32(p+0x6c,0);golden(p,u32(k+0x80));w32(c+0x1bc,u32(p+0x5c));
    if(p[0]==1){memcpy(c+0xb0bac,p,0x9c);memcpy(c+0xf010,c+0xeff8,24);}return 0;
}
static uint32_t manual(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    if(c[0xd47c]!=1)return 0;uint32_t ct=u16(c+0xd484),prevct=u16(c+0xd47e),a[3],b[3];float tint=(float)(int32_t)u32(c+0xd488),prevtint=(float)(int32_t)u32(c+0xd480);
    uint32_t st=hb_post_inverse(c,k,m,ct,tint,4096,a);if(st)return st;st=hb_post_inverse(c,k,m,prevct,prevtint,4096,b);if(st)return st;
    if(c[0xb0b10]!=1&&!(u32(c+0xb0b68)-ct<=500&&u32(c+0xb0b78)>199)){
        memcpy(c+0xb0b14,a,12);memcpy(c+0xb0b20,b,12);w32(c+0xb0b68,ct);w32(c+0xb0b6c,prevct);wf(c+0xb0b70,tint);wf(c+0xb0b74,prevtint);w32(c+0xb0b7c,u32(c+0xd490));golden(c+0xb0b10,u32(k+0x80));memcpy(c+0xb0bac,c+0xb0b10,0x9c);memcpy(c+0xf010,c+0xeff8,24);
    }c[0xd47c]=0;return 0;
}
static uint32_t iso_correction(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    if(!c[0xd4a4])return 0;float ct,tint;uint32_t st=hb_temperature_compute(c,k,m,0,u32(c+0xb0b20),4096,u32(c+0xb0b28),&ct,&tint);if(st)return st;
    unsigned n=k[0x153ec0];if(!n||n>8)return HB_PREP_UNSUPPORTED;float ev=rf(c+0x990d4);const unsigned char*first=k+0x153ec4;unsigned lo=0,hi=0;
    if(ev>=rf(first+0x1a48*(n-1)))lo=hi=n-1;else if(ev>=rf(first)){hi=1;while(hi<n&&ev>rf(first+0x1a48*hi))++hi;if(hi==n)return HB_PREP_UNSUPPORTED;lo=hi-1;}
    const unsigned char*a=first+0x1a48*lo,*b=first+0x1a48*hi;uint32_t av[2],bv[2],iso=fu((float)fu(exp2((double)rf(c+0x990d0)))*3.125f);
    st=hb_post_iso_row(a,iso,fu(ct),fs(tint),av,av+1);if(st)return st;
    /* Both calls use the lower row in the pinned original. */
    st=hb_post_iso_row(a,iso,fu(ct),fs(tint),bv,bv+1);if(st)return st;
    for(unsigned i=0;i<2;++i){uint32_t correction=(uint32_t)hb_atmosphere_interpolate_signed(fs(rf(a)),fs(rf(b)),(int32_t)av[i],(int32_t)bv[i],ev);size_t off=0xb0b14+8*i;w32(c+off,(u32(c+off)*correction)>>12);}return 0;
}
static void diagnostics(unsigned char*c,const unsigned char*k,int extended){
    static const size_t src[]={0x1c0,0x1c4,0x218,0x21c,0x244,0x248,0x270,0x274,0x2ec,0x2f0,0x300,0x304,0xb0c4c,0xb0c54};
    static const size_t dst[]={0xa851e,0xa8520,0xa8522,0xa8524,0xa8526,0xa8528,0xa8848,0xa884a,0xa884c,0xa884e,0xa8850,0xa8852,0xa8510,0xa8512};
    for(unsigned i=0;i<14;++i)w16(c+dst[i],(uint16_t)u32(c+src[i]));w32(c+0xa85ce,u32(k+12));c[0xa851c]=c[0x194];
    if(extended){w16(c+0xa8516,(uint16_t)u32(c+0xb0c58));w16(c+0xa8518,(uint16_t)u32(c+0xb0c60));}
    else{w16(c+0xa8514,(uint16_t)u32(c+0xb0ca0));w32(c+0xa85d2,u32(c+0xb0ca8));}
}
uint32_t hb_post_process(unsigned char*c,unsigned char*k,const hb_temperature_model*m,const unsigned char*reawb){
    uint32_t mode=u32(c+0x194),st=0;if(mode==2)return hb_post_mode2(c,k);
    if(mode>2){st=hb_post_category(c,k);if(st)goto done;st=hb_post_result_ct(c,k,m);if(st)goto done;st=hb_post_publish(c,k,reawb);if(st)goto done;}
    else{
        memset(c+0xb0b10,0,0x9c);st=select_normal(c);if(st)goto done;st=select_special(c,k);if(st)goto done;st=merge(c,k);if(st)goto done;
        st=combined(c,k,m);if(st&&!(st==247&&c[0xd47c]==1))goto done;
        if(k[0x16eae4]&&!c[0x990dc]&&c[0x9c184]&&c[0x9c184]<k[0x16eae5]){st=hb_post_sync(c,k,m);if(st==HB_PREP_UNSUPPORTED)return st;}
        for(unsigned i=0;i<6;++i)if(!u32(c+0xb0b14+4*i))goto done;
        if(c[0xb0b10]==1)c[0xb0c48]=c[0xb0ce4]=c[0xa851d]=1;
        st=hb_post_category(c,k);if(st)goto done;st=manual(c,k,m);if(st)goto done;st=iso_correction(c,k,m);if(st)goto done;
        st=hb_post_publish(c,k,reawb);if(st)goto done;st=hb_post_result_ct(c,k,m);if(st)goto done;
    }
    hb_post_golden_snapshot(c);st=hb_post_end_temperature(c);if(st)goto done;st=hb_post_end_unit(c);if(st)goto done;st=hb_post_recalibrate(c);if(st)goto done;st=hb_post_normalize(c,k);if(st)goto done;st=hb_post_color_mode(c,k);if(st)goto done;diagnostics(c,k,mode<2);
done:return st==HB_PREP_UNSUPPORTED?st:hb_post_validate(c);
}
uint32_t hb_post_sensor_tint(const unsigned char*p,int32_t tint,uint16_t*ct,int16_t*out){
    int32_t x=(int16_t)tint;unsigned n=p[2],lo=0,hi=0;if(!n||n>8)return HB_PREP_UNSUPPORTED;
    if(x>(int16_t)u16(p+4+6*(n-1)))lo=hi=n-1;
    else if(x>=(int16_t)u16(p+4)&&n>1){hi=1;while(hi<n&&x>(int16_t)u16(p+4+6*hi))++hi;if(hi==n)hi=0;else lo=hi-1;}
    const unsigned char*a=p+4+6*lo,*b=p+4+6*hi;
    if(lo==hi){*ct=u16(a+2);*out=(int16_t)u16(a+4);return 0;}
    float f=(float)(x-(int16_t)u16(a))/(float)((int16_t)u16(b)-(int16_t)u16(a)),g=1.0f-f;
    *ct=(uint16_t)fs(g*(float)u16(a+2)+f*(float)u16(b+2));*out=(int16_t)fs(g*(float)(int16_t)u16(a+4)+f*(float)(int16_t)u16(b+4));return 0;
}
uint32_t hb_post_sensor_transform(unsigned char*c,const unsigned char*k,uint32_t sensor,uint32_t ct,int32_t tint){
    if(!c[0xd32c])return 247;w16(c+0xd32e,(uint16_t)ct);w16(c+0xd330,(uint16_t)tint);
    unsigned n=k[0x1531e6],i=0;if(n>5)return HB_PREP_UNSUPPORTED;while(i<n&&u32(k+0x1531e8+0x210*i)!=sensor)++i;if(i==n)return 247;
    const unsigned char*p=k+0x1531ee + 0x210*i;n=p[-2];if(!n||n>10)return HB_PREP_UNSUPPORTED;unsigned lo=0,hi=0;uint32_t x=(uint16_t)ct;
    if(x>u16(p+0x34*(n-1)))lo=hi=n-1;else if(x>=u16(p)&&n>1){hi=1;while(hi<n&&x>u16(p+0x34*hi))++hi;if(hi==n)hi=0;else lo=hi-1;}
    const unsigned char*a=p+0x34*lo,*b=p+0x34*hi;uint16_t ca=0,cb=0;int16_t ta=0,tb=0;uint32_t st=hb_post_sensor_tint(a,tint,&ca,&ta);if(st)return st;
    if(lo!=hi){st=hb_post_sensor_tint(b,tint,&cb,&tb);if(st)return st;float f=(float)(x-u16(a))/(float)(u16(b)-u16(a)),g=1.0f-f;ca=(uint16_t)fs(g*(float)ca+f*(float)cb);ta=(int16_t)fs(g*(float)ta+f*(float)tb);}
    w16(c+0xd332,ca);w16(c+0xd334,(uint16_t)ta);return 0;
}
static double sync_distance(const unsigned char*c,unsigned i,uint32_t r,uint32_t b){double x=(double)r-u32(c+0x348+16*i),y=(double)b-u32(c+0x34c+16*i);return x*x+y*y;}
uint32_t hb_post_sync_zones(const unsigned char*c,const unsigned char*k,uint32_t ct[8],unsigned char valid[8],float weight[8],const uint32_t r[8],const uint32_t b[8]){
    unsigned n=k[0xc88];if(!n||n>15)return HB_PREP_UNSUPPORTED;
    for(unsigned j=0;j<8;++j){if(!r[j]||!b[j])continue;double best=2147483648.0,previous=best,dprev=0,dnext=0;unsigned index=80,prior_index=80,mid=0,found=0;
        for(unsigned s=1;s<n;++s){unsigned lo=u32(c+0x308+4*(s-1)),hi=u32(c+0x308+4*s),candidate=prior_index;double d=previous;if(lo>hi||hi>80)return HB_PREP_UNSUPPORTED;int local=0;
            if(hi-lo>=2){while(hi-lo>1){mid=(lo+hi)>>1;d=sync_distance(c,mid,r[j],b[j]);dprev=sync_distance(c,mid-1,r[j],b[j]);if(d>dprev){hi=mid;continue;}dnext=sync_distance(c,mid+1,r[j],b[j]);if(d<=dnext){found=1;candidate=mid;local=1;break;}lo=mid;}}
            if(!local){if(found){candidate=prior_index;d=previous;}else if(mid==lo+1){candidate=lo;d=dprev;}else if(mid==hi-1){candidate=hi;d=dnext;}else{candidate=prior_index;d=previous;}}
            prior_index=candidate;previous=d;if(d<best){best=d;index=candidate;}
        }
        double distance=sqrt(best),radius=(double)u32(c+0x350+16*index);if(distance>radius)continue;
        ct[j]=2000+100*index;valid[j]=1;double v=1.0-distance/radius;if(v>1)v=1;if(v<0)v=0;weight[j]=(float)v;
    }return 0;
}
uint32_t hb_post_sync_shift(const unsigned char*c,const unsigned char*k,uint32_t gain[3],uint32_t target_r,uint32_t target_b,const uint32_t other_r[8],const uint32_t other_b[8],const uint32_t current[3]){
    unsigned n=c[0x2c];if(n>8)return HB_PREP_UNSUPPORTED;int active=0;for(unsigned i=0;i<n;++i)active|=c[0x98f48+32*i]==1;if(!active)return 0;
    uint32_t r[8]={0},b[8]={0},ct[8]={0};unsigned char valid[8]={0};float weight[8]={0};for(unsigned i=0;i<n;++i){r[i]=u32(c+0x98f4c+32*i);b[i]=u32(c+0x98f54+32*i);}uint32_t st=hb_post_sync_zones(c,k,ct,valid,weight,r,b);if(st)return st;
    float total=0,ar=0,ab=0,br=0,bb=0;for(unsigned i=0;i<n;++i){if(c[0x98f48+32*i]!=1||!r[i]||!b[i]||!other_r[i]||!other_b[i])continue;float v=(float)valid[i];total=total+weight[i]*v;ar=ar+weight[i]*((float)r[i]*v);ab=ab+weight[i]*((float)b[i]*v);br=br+weight[i]*((float)other_r[i]*v);bb=bb+weight[i]*((float)other_b[i]*v);}
    if(total<=0){memcpy(gain,current,12);return 0;}
    float x=(float)target_r/(br/total),y=(float)gain[0]/(ar/total);gain[0]=fu((x/y)*(float)gain[0]);
    x=(float)target_b/(bb/total);y=(float)gain[2]/(ab/total);gain[2]=fu((x/y)*(float)gain[2]);return 0;
}
uint32_t hb_post_sync(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    if(!u32(c+0xb0b78))return 0;uint32_t ct=u16(c+0x9c18c);float tint=rf(c+0x9c190);uint32_t current[]={u32(c+0xb0b14),u32(c+0xb0b18),u32(c+0xb0b1c)},gain[3];
    uint32_t st=hb_post_sensor_transform(c,k,u32(c+0x9c19c),ct,fs(tint));if(st==HB_PREP_UNSUPPORTED)return st;if(!st){ct=u16(c+0xd332);tint=(float)(int16_t)u16(c+0xd334);}
    st=hb_post_inverse(c,k,m,ct,tint,4096,gain);if(st)return st;uint32_t r[8],b[8];for(unsigned i=0;i<8;++i){r[i]=u32(c+0x9c144+4*i);b[i]=u32(c+0x9c164+4*i);}
    st=hb_post_sync_shift(c,k,gain,u16(c+0x9c186),u16(c+0x9c18a),r,b,current);if(st)return st;
    float rd=((float)current[0]-(float)gain[0])/(float)current[0],bd=((float)current[2]-(float)gain[2])/(float)current[2],low=rf(k+0x16eae8),high=rf(k+0x16eaec);
    if(rd>low||bd>low){if(rd>high&&bd>high){float den=high-low;if(rd>low)gain[0]=fu(((rd-low)*(float)current[0])/den+((high-rd)*(float)gain[0])/den);if(bd>low)gain[2]=fu(((bd-low)*(float)current[2])/den+((high-bd)*(float)gain[2])/den);}else{gain[0]=current[0];gain[2]=current[2];}}
    float unused_ct,unused_tint,actual_ct,actual_tint;st=hb_temperature_calibrated(c,k,m,u32(c+0x84168),u32(c+0x8416c),u32(c+0x84170),&unused_ct,&unused_tint);if(st)return st;
    st=hb_temperature_calibrated(c,k,m,gain[0],gain[1],gain[2],&actual_ct,&actual_tint);if(st)return st;
    uint32_t d=ct-(uint32_t)fs(actual_ct);if((int32_t)d<0)d=0-d;if(d>=250)actual_ct=(float)(ct>=fu(actual_ct)?ct-250:ct+250);
    if(!(fabsf(tint-actual_tint)<4))actual_tint=tint>=actual_tint?tint-4:tint+4;
    st=hb_post_inverse(c,k,m,fu(actual_ct),actual_tint,4096,gain);if(st)return st;w32(c+0xb0b14,gain[0]);w32(c+0xb0b1c,gain[2]);return 0;
}
