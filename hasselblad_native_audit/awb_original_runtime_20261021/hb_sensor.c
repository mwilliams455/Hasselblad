/* SPDX-License-Identifier: MIT */
#include "hb_sensor.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static uint32_t cvtu(double v){if(!(v>0))return 0;if(v>=4294967296.0)return UINT32_MAX;return (uint32_t)v;}
static int32_t cvts(double v){if(isnan(v))return 0;if(v>=2147483648.0)return INT32_MAX;if(v<=-2147483648.0)return INT32_MIN;return (int32_t)v;}
static uint32_t interp(uint32_t a,uint32_t b,uint32_t x,uint32_t y,float t){
    if(a>b){uint32_t z=a;a=b;b=z;z=x;x=y;y=z;}
    float p,q;if((float)a>=t){p=0;q=1;}else if((float)b<=t){p=1;q=0;}else{p=t-(float)a;q=(float)b-t;}
    float d=p+q;return d==0?(x+y)>>1:cvtu((p*(float)y+q*(float)x)/d);
}
uint32_t hb_sensor_calibration(const unsigned char*c,uint32_t ct,void*out){
    if(!out)return 171;if(!c||c[0xc5a8]>2)return HB_PREP_UNSUPPORTED;
    unsigned n=c[0xc5a8];if(!n){for(unsigned i=0;i<10;++i)w32((unsigned char*)out+4*i,4096);return 0;}
    const unsigned char*a=c+0xc5ac,*b=a+44*(n-1);
    if(ct<=u32(a))b=a;else if(ct>=u32(b))a=b;
    else for(unsigned i=1;i<n;++i)if(ct<u32(c+0xc5ac+44*i)){b=c+0xc5ac+44*i;a=b-44;break;}
    for(unsigned i=0;i<10;++i)w32((unsigned char*)out+4*i,a==b?u32(a+4+4*i):interp(u32(a),u32(b),u32(a+4+4*i),u32(b+4+4*i),(float)ct));
    return 0;
}
uint32_t hb_sensor_parameter_pass(unsigned char*c){
    if(!c)return HB_PREP_UNSUPPORTED;
    memcpy(c+0x3daa4,c+0xb2010,8);memcpy(c+0x3da9e,c+0xb200a,8);memcpy(c+0x3daac,c+0xb2018,8);
    memcpy(c+0xa86ce,c+0xc6d4,4);memcpy(c+0xa86c8,c+0xc6e4,2);memcpy(c+0xa86ca,c+0xc6e6,4);return 0;
}
static unsigned supported(const unsigned char*c,const unsigned char*k){
    if(!k[0x139e2c])return 1;
    if((k[0x139e2d]&&c[0xd288])||k[0x139e2e])if(c[0xc5a8]>2)return 0;
    if(!k[0x139e2e]||c[0xd324]==1)return 1;
    unsigned n=k[0x13bdd8],sv=u16(k+0x13bdf8);if(n>3||sv>256)return 0;
    if(k[0x1480f0]&&k[0x1480f4]>1)return 0;
    for(unsigned i=0;i<sv;++i)if(k[0x13be1c+140*i]>15)return 0;
    unsigned start=0;for(unsigned i=0;i<n;++i){unsigned count=u16(k+0x13be0c+2*i);if(start+count>256)return 0;start=(start+count)&255;}
    if(k[0x144a14]>3)return 0;
    for(unsigned i=0;i<k[0x144a14];++i){const unsigned char*r=k+0x144a18+0x1248*i;
        if(r[0]>2||r[4]<1||r[4]>8)return 0;
        for(unsigned j=0;j<r[4];++j){const unsigned char*a=r+8+0x248*j;if(a[4]<1||a[4]>8)return 0;
            for(unsigned z=0;z<a[4];++z){unsigned count=a[8+0x48*z+4];if(count<1||count>8)return 0;}}
    }return 1;
}
static int32_t dot(const unsigned char*m,const unsigned char*v){uint32_t sum=0;for(unsigned i=0;i<10;++i)sum+=(uint32_t)(int32_t)(int16_t)u16(m+2*i)*u32(v+4*i);return (int32_t)sum;}
static float temperature(float x,float y){float n=(float)(((double)x-0.332)/(0.1858-(double)y));return ((437.0f*n+3601.0f)*n+6861.0f)*n+5517.0f;}
static void calibrate_request(unsigned char*c,const unsigned char*k){
    memcpy(c+0xd28c,c+0x9c1c4,4);memcpy(c+0xd290,c+0x9c1c0,4);c[0xd288]=0;w32(c+0xd320,2);
    hb_sensor_calibration(c,u32(c+0xd294),c+0xd298);uint32_t corrected[10];
    for(unsigned i=0;i<10;++i){uint32_t raw=u16(c+0x9c1cc+2*i);w32(c+0xd2c0+4*i,raw);corrected[i]=(u32(c+0xd298+4*i)*raw)>>12;}
    if(!corrected[8]){w32(c+0xd2e8,0);memset(c+0xd2ec,0,40);w32(c+0xd320,3);return;}
    for(unsigned i=0;i<10;++i)w32(c+0xd2ec+4*i,(uint64_t)corrected[i]*65535/corrected[8]);
    int32_t xyz[3];for(unsigned i=0;i<3;++i){int32_t v=dot(k+0x13bd9c+20*i,c+0xd2ec);if(v<10){w32(c+0xd2e8,0);w32(c+0xd320,3);return;}xyz[i]=v/10;}
    int32_t sum=(int32_t)((uint32_t)xyz[0]+(uint32_t)xyz[1]+(uint32_t)xyz[2]);
    if(!sum){w32(c+0xd2e8,0);w32(c+0xd320,3);return;}
    float v[3];for(unsigned i=0;i<3;++i){v[i]=(float)xyz[i]/(float)sum;wf(c+0xd314+4*i,v[i]);}
    float ct=temperature(v[0],v[1]);if(ct<2000)ct=2000;if(ct>10000)ct=10000;w32(c+0xd2e8,cvtu(ct));w32(c+0xd320,4);
}
static void inputs(unsigned char*c,const unsigned char*k){
    c[0xa85de]=c[0x9c1bc];c[0xa85df]=c[0x9c1bd];memcpy(c+0xa8622,c+0x9c1c0,4);memcpy(c+0xa85e0,c+0x9c1c4,4);memcpy(c+0xa85e4,c+0x9c1c8,4);memcpy(c+0xa85e8,c+0x9c1cc,20);
    c[0xc59c]=1;
    if(!k[0x139e38])w32(c+0xc5a0,1024);
    else{uint32_t now=u32(c+0x9c1a0),stamp=u32(c+0x9c1b8);float fps=f32(c+0x9c1a4),age=fps?(float)(now-stamp)/fps:0;
        unsigned bad=now<stamp||age>f32(k+0x139e44)||!c[0x9c1bc]||!c[0x9c1bd];
        for(unsigned i=0;i<10;++i){uint32_t raw=u16(c+0x9c1cc+2*i);bad|=raw<u32(k+0x139e3c)||raw>u32(k+0x139e40);}
        if(bad){c[0xc59c]=0;if(!c[0xc59d])c[0xc59d]=1;}else if(c[0xc59d])--c[0xc59d];
        w32(c+0xc5a0,1024-(uint32_t)c[0xc59d]*1024);
    }
    if(c[0xc59c]){if(c[0xc5a4])hb_sensor_calibration(c,u32(c+0xc62c),c+0xc604);else for(unsigned i=0;i<10;++i)w32(c+0xc604+4*i,4096);
        for(unsigned i=0;i<10;++i){uint32_t raw=u16(c+0x9c1cc+2*i);w32(c+0xc630+4*i,c[0xc5a4]?(raw*u32(c+0xc604+4*i))>>12:raw);}}
    w16(c+0xa869e,u32(c+0xc62c));memcpy(c+0xa86a0,c+0xc630,40);for(unsigned i=0;i<10;++i)w16(c+0xa85fc+2*i,u32(c+0xc604+4*i));
    if(c[0xc59c]){uint32_t denominator=u32(c+0xc650);if(!denominator){c[0xc59c]=0;w32(c+0xc5a0,0);}else for(unsigned i=0;i<10;++i)w32(c+0xc658+4*i,(uint64_t)u32(c+0xc630+4*i)*65535/denominator);}
}
static void spectral(unsigned char*c,const unsigned char*k){
    if(c[0xc59c]&&u32(c+0xc5a0)){
        if(c[0xc680]){uint32_t a=u32(k+0x139e30),b=u32(k+0x139e34);
            for(unsigned i=0;i<10;++i){uint32_t first=(int32_t)(u32(c+0xc658+4*i)*a+u32(c+0xc684+4*i)*(128-a))/128;
                uint32_t second=u32(c+0xc6ac+4*i)+(int32_t)((first-u32(c+0xc6ac+4*i))*b)/128;w32(c+0xc684+4*i,first);w32(c+0xc6ac+4*i,second);}}
        else{memcpy(c+0xc684,c+0xc658,40);memcpy(c+0xc6ac,c+0xc658,40);c[0xc680]=1;}
    }
    if(!u32(c+0xc5a0))return;
    uint32_t max=1;for(unsigned j=0;j<401;++j){int32_t v=dot(k+0x139e48+20*j,c+0xc6ac);uint32_t value=v<0?0:(uint32_t)v;w32(c+0xc6ec+4*j,value);if(value>max)max=value;}
    for(unsigned j=0;j<401;++j)w32(c+0xc6ec+4*j,(uint64_t)u32(c+0xc6ec+4*j)*65535/max);
    int32_t dx=dot(k+0x13bd9c,c+0xc6ac),dy=dot(k+0x13bdb0,c+0xc6ac),dz=dot(k+0x13bdc4,c+0xc6ac);
    int32_t xyz[3]={dx/10,dy/10,dz/10},sum=(int32_t)((uint32_t)xyz[0]+(uint32_t)xyz[1]+(uint32_t)xyz[2]);
    if(xyz[0]<0||dy<=-10||!sum){w32(c+0xc5a0,0);return;}
    float v[3];for(unsigned i=0;i<3;++i){v[i]=(float)xyz[i]/(float)sum;wf(c+0xc6d8+4*i,v[i]);}
    float ct=temperature(v[0],v[1]);if(ct>10000)ct=10000;if(ct<2000)ct=2000;wf(c+0xc6d4,ct);w32(c+0xc62c,cvtu(ct));
    uint32_t a=u32(c+0xc6cc),b=u32(c+0xc6d0);w16(c+0xc6e4,a?cvts(((double)b*0.5*256.0)/((double)a*2.7)):0);
    w16(c+0xc6e6,b?cvts((double)(u32(c+0xc6ac)<<8)/((double)b*0.5)):0);
    memcpy(c+0xa86d2,c+0xc6d8,12);memcpy(c+0xa86ce,c+0xc6d4,4);memcpy(c+0xa86c8,c+0xc6e4,2);memcpy(c+0xa86ca,c+0xc6e6,2);
}
static void similarity(unsigned char*c,const unsigned char*k){
    w16(c+0xc6e8,0);if(!u32(c+0xc5a0)||!k[0x1480f0])return;
    uint64_t a=0,b=0;for(unsigned i=0;i<401;++i){uint64_t x=u32(c+0xc6ec+4*i),y=u16(k+0x1480f8+2*i);a+=x*x;b+=y*y;}
    uint32_t na=cvtu(sqrt((double)a)),nb=cvtu(sqrt((double)b));double d=0;
    for(unsigned i=0;i<401;++i){double v=(double)u32(c+0xc6ec+4*i)/(double)na-(double)u16(k+0x1480f8+2*i)/(double)nb;d+=v*v;}
    w16(c+0xc6e8+2*k[0x1480f4],cvts(256.0/(sqrt(d)+1.0)));memcpy(c+0xa86cc,c+0xc6e8,2);
}
static void probabilities(unsigned char*c,unsigned n){
    if(n==2){uint32_t a=cvtu((double)fabsf(f32(c+0xcd40))*256.0);w32(c+0xcd60,a);w32(c+0xcd64,256-a);return;}
    float p[3]={0},q[3][3]={{0}},qp[3]={0};
    for(unsigned i=0;i<n;++i){p[i]=(float)(1.0/(double)n);for(unsigned j=0;j<n;++j){float a=f32(c+0xcd3c+12*j+4*i);if(j!=i)q[i][i]+=a*a;if(j<i)q[i][j]=q[j][i];else if(j>i)q[i][j]=-(a*f32(c+0xcd3c+12*i+4*j));}}
    float eps=(float)(0.005/(double)n);
    for(unsigned iter=0;iter<100;++iter){float pq=0,error=0;for(unsigned i=0;i<n;++i){qp[i]=0;for(unsigned j=0;j<n;++j)qp[i]+=q[i][j]*p[j];pq+=qp[i]*p[i];}
        for(unsigned i=0;i<n;++i){float e=fabsf(qp[i]-pq);if(e>error)error=e;}if(error<eps)break;
        for(unsigned i=0;i<n;++i){float diff=(pq-qp[i])/q[i][i],scale=diff+1,twice=qp[i]+qp[i];p[i]+=diff;
            for(unsigned j=0;j<n;++j)if((double)fabsf(scale)<1e-6){qp[j]=p[j]=0;}else{qp[j]=(qp[j]+diff*q[i][j])/scale;p[j]/=scale;}
            pq=((pq+diff*(twice+q[i][i]*diff))/scale)/scale;
        }
    }
    uint32_t sum=0;for(unsigned i=1;i<n;++i){uint32_t v=cvtu((double)fabsf(p[i])*256.0);w32(c+0xcd60+4*i,v);sum=(uint16_t)sum+v;}
    if((uint16_t)sum>256){memset(c+0xcd60,0,12);w32(c+0xcd60,256);}else w32(c+0xcd60,256-(uint16_t)sum);
}
static void classifier(unsigned char*c,const unsigned char*k){
    memset(c+0xcd78,0,0x8c);if(!u32(c+0xc5a0))return;c[0xcd80]=10;
    for(unsigned i=0;i<10;++i){c[0xcd84+8*i]=i+1;wf(c+0xcd88+8*i,(float)u32(c+0xc6ac+4*i)/(float)u32(c+0xc6cc));}
    memset(c+0xce04,0,0x400);unsigned n=k[0x13bdd8],sv=u16(k+0x13bdf8);float gamma=f32(k+0x13bddc);
    for(unsigned z=0;z<sv;++z){const unsigned char*r=k+0x13be10+140*z;unsigned i=0,j=0;float d=0;
        while(i<10&&j<r[12]){unsigned a=c[0xcd84+8*i],b=r[16+8*j];float v;
            if(a==b){v=f32(c+0xcd88+8*i)-f32(r+20+8*j);++i;++j;}else if(a>b){v=f32(r+20+8*j);++j;}else{v=f32(c+0xcd88+8*i);++i;}d+=v*v;}
        wf(c+0xce04+4*z,(float)exp((double)(-(gamma*d))));
    }
    unsigned starts[3]={0};for(unsigned i=1;i<n;++i)starts[i]=(starts[i-1]+u16(k+0x13be0c+2*(i-1)))&255;
    unsigned pair=0;for(unsigned i=0;i<n;++i)for(unsigned j=i+1;j<n;++j,++pair){float sum=0;
        for(unsigned z=0;z<u16(k+0x13be0c+2*i);++z){unsigned idx=starts[i]+z;sum+=f32(k+0x13be10+140*idx+4*j)*f32(c+0xce04+4*idx);}
        for(unsigned z=0;z<u16(k+0x13be0c+2*j);++z){unsigned idx=starts[j]+z;sum+=f32(k+0x13be14+140*idx+4*i)*f32(c+0xce04+4*idx);}
        sum-=f32(k+0x13bdfc+4*pair);wf(c+0xcd30+4*pair,sum);
        float v=f32(k+0x13bdec+4*pair)+f32(k+0x13bde0+4*pair)*sum;double e=exp((double)(v>=0?-v:v));float p=(float)((v>=0?e:1.0)/(e+1.0));
        p=fminf(fmaxf(p,0.00001f),0.99999f);wf(c+0xcd3c+12*i+4*j,p);wf(c+0xcd3c+12*j+4*i,1.0f-p);
    }
    probabilities(c,n);for(unsigned i=0;i<3;++i)w16(c+0xa8616+2*i,u32(c+0xcd60+4*i));
}
static void bracket(const unsigned char*base,unsigned n,unsigned stride,float input,const unsigned char**lo,const unsigned char**hi){
    *lo=base;*hi=base+stride*(n-1);if(input<=(float)u32(*lo))*hi=*lo;else if(input>=(float)u32(*hi))*lo=*hi;
    else{*hi=base+stride;for(unsigned i=1;i<n;++i)if(input<=(float)u32(base+stride*i)){*hi=base+stride*i;*lo=*hi-stride;break;}}
}
static uint32_t inner_adjust(const unsigned char*r,uint16_t value){
    const unsigned char*a=r+8,*b=r+8*r[4];if(u32(a)>=value)b=a;else if(u32(b)<=value)a=b;
    else{b=a+8;for(unsigned i=1;i<r[4];++i)if(u32(r+8+8*i)>=value){b=r+8+8*i;a=b-8;break;}}
    return interp(u32(a),u32(b),u16(a+4),u16(b+4),(float)value);
}
static uint32_t adjust_value(const unsigned char*c,const unsigned char*r){
    const unsigned char*a,*b;float ct=f32(c+0xc6d4);bracket(r+8,r[4],0x48,ct,&a,&b);
    return interp(u32(a),u32(b),inner_adjust(a,u16(c+0xc6e4)),inner_adjust(b,u16(c+0xc6e4)),ct);
}
static void adjustment(unsigned char*c,const unsigned char*k){
    if(!u32(c+0xc5a0))return;unsigned count=k[0x144a14];if(!count){memcpy(c+0xcd6c,c+0xcd60,12);return;}
    uint32_t previous=0;for(unsigned i=0;i<count;++i){const unsigned char*r=k+0x144a18+0x1248*i,*a,*b;unsigned id=r[0];float input=f32(c+0x37618);
        bracket(r+8,r[4],0x248,input,&a,&b);uint32_t value=interp(u32(a),u32(b),adjust_value(c,a),adjust_value(c,b),input),weight=u32(c+0xcd60+4*id);
        if(value<=128)previous=(value*weight)>>7;else if(value<=256)previous=weight+((value-129)*(256-weight))/127;
        w32(c+0xcd6c+4*id,previous);w16(c+0xa8610+2*id,value);
    }
    uint32_t weights[3],sum=0;for(unsigned i=0;i<3;++i){weights[i]=u32(c+0xcd6c+4*i);if(weights[i]<10)weights[i]=0;sum+=weights[i];}
    if(!sum){weights[0]=256;sum=256;}for(unsigned i=0;i<3;++i){uint32_t v=(weights[i]<<8)/sum;w32(c+0xcd6c+4*i,v);w16(c+0xa861c+2*i,v);}
}
uint32_t hb_sensor_process(unsigned char*c,const unsigned char*k){
    if(!c||!k||!supported(c,k))return HB_PREP_UNSUPPORTED;if(!k[0x139e2c])return 0;
    if(k[0x139e2d]&&c[0xd288])calibrate_request(c,k);
    if(!k[0x139e2e])return 0;if(c[0xd324]==1){c[0xd324]=0;return hb_sensor_parameter_pass(c);}
    inputs(c,k);spectral(c,k);similarity(c,k);classifier(c,k);adjustment(c,k);
    if(u32(c+0xc5a0))for(unsigned i=0;i<3;++i)for(unsigned j=0;j<11;++j){float coeff=f32(c+(j<7?0xd234+28*i+4*j:0xd204+16*i+4*(j-7)));
        uint32_t v=(uint32_t)cvts(coeff*(float)u32(c+0xcd6c+4*i)+(float)u16(c+0x3da9e +2*j));w16(c+0x3da9e +2*j,v<256?v:256);}
    return 0;
}
