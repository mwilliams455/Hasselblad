/* SPDX-License-Identifier: MIT */
#include "hb_temperature.h"
#include "hb_scene_candidates.h"
#include "hb_scene_optimizer.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const unsigned char*p){float v;memcpy(&v,p,4);return v;}
static uint32_t fu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int32_t fs(double v){return isnan(v)?0:v>=2147483647.0?INT32_MAX:v<=-2147483648.0?INT32_MIN:(int32_t)v;}
static int32_t ds(uint32_t a,uint32_t b){int32_t x=(int32_t)a,y=(int32_t)b;return !y?0:x==INT32_MIN&&y==-1?INT32_MIN:x/y;}
static uint32_t half(uint32_t v){if((int32_t)v<0)++v;return (uint32_t)((int32_t)v>>1);}
uint32_t hb_temperature_xy(const hb_temperature_model *model,const float xy[2],float *ct,float *tint){
    if(!model||!model->isotemperature_31x4)return HB_PREP_UNSUPPORTED;
    const float *table=model->isotemperature_31x4;
    double den=1.5-(double)xy[0];den=den+(double)xy[1]*6.0;
    float inv=(float)(1.0/den),u=(float)(((double)xy[0]*2.0)*(double)inv),v=(float)(((double)xy[1]*3.0)*(double)inv);
    float old_dist=0,old_x=0,old_y=0,dist=0,nx=0,ny=0;unsigned i;
    for(i=1;i<=30;++i){
        float slope=table[4*i+3],square=slope*slope;
        float norm=(float)sqrt((double)square+1.0);nx=1.0f/norm;ny=slope*nx;
        float a=nx*(v-table[4*i+2]),b=(u-table[4*i+1])*ny;dist=a-b;
        if(i==30||!(dist>0))break;
        old_dist=dist;old_x=nx;old_y=ny;
    }
    float f=0;if(i!=1){float z=isnan(dist)?dist:dist<0?dist:0;f=-z/(old_dist-z);}
    float g=1.0f-f;
    float ax=old_x*f,bx=nx*g,ay=old_y*f,by=ny*g;
    float tx=ax+bx,ty=ay+by;
    float a=f*table[4*(i-1)],b=g*table[4*i];*ct=1000000.0f/(a+b);
    a=table[4*i+1]*g;b=f*table[4*(i-1)+1];float du=u-(a+b);
    a=table[4*i+2]*g;b=f*table[4*(i-1)+2];float dv=v-(a+b);
    a=tx*tx;b=ty*ty;float norm=sqrtf(a+b);
    a=du*(tx/norm);b=(ty/norm)*dv;*tint=(a+b)*-3000.0f;return 0;
}
static uint32_t matrix_rows(const unsigned char *first,unsigned n,float ct,float out[9]){
    if(!n)return HB_PREP_UNSUPPORTED;
    const unsigned char *last=first+40*(n-1);
    if((float)u32(last)<=ct){memcpy(out,last+4,36);return 0;}
    if((float)u32(first)>=ct){memcpy(out,first+4,36);return 0;}
    float prev=(float)(1.0/(double)u32(first)),wanted=1.0f/ct;
    for(unsigned i=1;i<n;++i){const unsigned char *row=first+40*i;
        float current=(float)(1.0/(double)u32(row));
        if((float)u32(row)>=ct){float a=(wanted-current)/(prev-current),b=1.0f-a;
            for(unsigned j=0;j<9;++j){float x=a*rf(row-36+4*j),y=b*rf(row+4+4*j);out[j]=x+y;}return 0;}
        prev=current;
    }
    return 0;
}
uint32_t hb_temperature_matrix_row(const unsigned char *row,float ct,float out[9]){
    return matrix_rows(row+4,row[2],ct,out);
}
uint32_t hb_temperature_matrix(const unsigned char *cfg,int ae_enabled,float ae,float ct,float out[9]){
    if(!ae_enabled)return matrix_rows(cfg+0x1332c0,cfg[0x1332bc],ct,out);
    unsigned n=cfg[0x133518];if(!n)return HB_PREP_UNSUPPORTED;
    const unsigned char *first=cfg+0x13351c,*a=first,*b=first;
    if(!((float)u16(first)>=ae)){
        b=first+604*(n-1);if((float)u16(b)<=ae)a=b;
        else{a=first;b=first;for(unsigned i=1;i<n;++i){b=first+604*i;if((float)u16(b)>=ae)break;a=b;}}
    }
    float av[9]={0},bv[9]={0};uint32_t st=hb_temperature_matrix_row(a,ct,av);if(st)return st;
    st=hb_temperature_matrix_row(b,ct,bv);if(st)return st;
    uint32_t lo=u16(a),hi=u16(b);float *lp=av,*hp=bv;
    if(lo>=hi){uint32_t t=lo;lo=hi;hi=t;lp=bv;hp=av;}
    float x,y;if((float)lo>=ae){x=1;y=0;}else if((float)hi<=ae){x=0;y=1;}else{y=ae-(float)lo;x=(float)hi-ae;}
    float sum=y+x;for(unsigned j=0;j<9;++j){if(sum==0)out[j]=(lp[j]+hp[j])*0.5f;else{float p=x*lp[j],q=y*hp[j];out[j]=(p+q)/sum;}}
    return 0;
}
uint32_t hb_temperature_calibrated(const unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model,uint32_t r,uint32_t g,uint32_t b,float *ct,float *tint){
    uint32_t minimum=r<g?r:g;minimum=minimum<b?minimum:b;if((double)(float)minimum<=0.1)return 91;
    if(!model||!model->isotemperature_31x4)return HB_PREP_UNSUPPORTED;
    if(ctx[0x990dc]==1&&!cfg[0x133518]){
        uint32_t temperature=hb_scene_temperature(ctx,r,b);unsigned i=temperature<=2000?0:temperature>10000?80:(temperature-2000)/100;
        float rr=(float)r/(float)u32(ctx+0x348+16*i),bb=(float)b/(float)u32(ctx+0x34c+16*i);
        r=fu(rr*(float)u32(ctx+0x858+16*i));b=fu(bb*(float)u32(ctx+0x85c+16*i));
    }
    minimum=r<g?r:g;minimum=minimum<b?minimum:b;
    float vr=(float)minimum/(float)r,vg=(float)minimum/(float)g,vb=(float)minimum/(float)b;
    float xy[2]={0.3457f,0.3585f},previous_x=xy[0],previous_y=xy[1];
    for(unsigned iter=0;iter<30;++iter){
        float temperature,deviation,m[9]={0};uint32_t st=hb_temperature_xy(model,xy,&temperature,&deviation);if(st)return st;
        st=hb_temperature_matrix(cfg,ctx[0x990dc]==1&&cfg[0x133518],rf(ctx+0x990d8),temperature,m);if(st)return st;
        float a=m[0],b0=m[1],c=m[2],d=m[3],e=m[4],f=m[5],g0=m[6],h=m[7],i=m[8];
        float p=e*i,q=f*h,c0=p-q;p=f*g0;q=d*i;float c1=p-q;p=d*h;q=e*g0;float c2=p-q;
        p=a*c0;q=b0*c1;float det=p+q;p=c*c2;det=p+det;
        if((double)det>-0.00001&&(double)det<0.00001)return 92;
        float inv[9];inv[0]=c0/det;p=c*h;q=b0*i;inv[1]=(p-q)/det;p=b0*f;q=c*e;inv[2]=(p-q)/det;
        inv[3]=c1/det;p=a*i;q=c*g0;inv[4]=(p-q)/det;p=c*d;q=a*f;inv[5]=(p-q)/det;
        inv[6]=c2/det;p=b0*g0;q=a*h;inv[7]=(p-q)/det;p=a*e;q=b0*d;inv[8]=(p-q)/det;
        float x=vr*inv[0];p=vg*inv[1];x=x+p;p=vb*inv[2];x=p+x;
        float y=vr*inv[3];p=vg*inv[4];y=y+p;p=vb*inv[5];y=p+y;
        float z=vr*inv[6];p=vg*inv[7];z=z+p;p=vb*inv[8];z=p+z;
        float sum=x+y;sum=z+sum;
        if(sum>0){x=x/sum;y=y/sum;}else{x=0.3457f;y=0.3585f;}
        double change=(double)fabsf(y-previous_y)+(double)fabsf(x-previous_x);
        if(change<0.0000001){xy[0]=x;xy[1]=y;break;}
        if(iter==29){xy[0]=(previous_x+x)*0.5f;xy[1]=(previous_y+y)*0.5f;break;}
        previous_x=x;previous_y=y;xy[0]=x;xy[1]=y;
    }
    return hb_temperature_xy(model,xy,ct,tint);
}
uint32_t hb_temperature_compute(const unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model,uint32_t mode,uint32_t r,uint32_t g,uint32_t b,float *ct,float *tint){
    if(mode==0)return hb_candidate_temperature(ctx,0,r,g,b,ct,tint);
    if(mode==1)return hb_temperature_calibrated(ctx,cfg,model,r,g,b,ct,tint);
    if(mode!=2)return 94;
    if(u32(ctx+0x348)>r){float x,y;uint32_t st=hb_temperature_calibrated(ctx,cfg,model,r,g,b,&x,&y);if(st)return st;*ct=(float)fu(x);*tint=(float)fs(y);return 0;}
    uint32_t lr=u32(ctx+0x848),lb=u32(ctx+0x84c);if(lr>=r)return hb_candidate_temperature(ctx,0,r,g,b,ct,tint);
    uint32_t pr=u32(ctx+0x838),pb=u32(ctx+0x83c),dr=lr-pr,db=lb-pb;
    uint32_t cb=u32(ctx+0x82c)-pb+db;if((int32_t)cb<=1)cb=1;
    if((int32_t)dr<0||(int32_t)db>0)return 93;
    uint32_t cr=u32(ctx+0x828)-pr+dr;if((int32_t)cr<0)cr=0;
    float steps;
    if(cr){float base=(float)(int32_t)(dr+(cr>>1)),p=base*base,q=(float)(int32_t)(((lr-r)*cr)<<1);
        steps=(float)((sqrt((double)(p-q))-(double)base)/(double)(int32_t)cr);
    }else steps=(float)ds(r-lr,dr);
    uint32_t n=fu((double)steps+0.5),prev=n-1,tn=half((n+1)*n),tp=half(prev*n);
    uint32_t next_r=lr+dr*n+tn*cr,prev_r=lr+dr*prev+tp*cr;
    uint32_t limit=(uint32_t)ds((int32_t)db<0?0-db:db,cb),by_n=n,by_t=tn;
    if((int32_t)(db+cb*n)>=0){by_n=limit;by_t=half((limit+1)*limit);}
    uint32_t next_b=lb+by_t*cb+by_n*db,prev_b=lb+prev*db+tp*cb;
    if((int32_t)(db+prev*cb)>=0)prev_b=next_b;
    uint32_t rd=prev_r-next_r,bd=prev_b-next_b,dist=rd*rd+bd*bd;
    uint32_t numerator=(next_r-prev_r)*b+next_b*prev_r-prev_b*next_r+bd*r;
    float temp=steps*100.0f;temp=temp+10000.0f;uint32_t temperature=fu(temp);
    float deviation=(float)((double)(float)(int32_t)numerator/sqrt((double)(int32_t)dist));
    *ct=(float)temperature;*tint=(float)fs(deviation);return 0;
}
