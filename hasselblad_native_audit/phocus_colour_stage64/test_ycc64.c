/* Standalone invariants only; original CPU comparison still required. */
#include "ycc64.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void flat_fixture(void){
    uint16_t y[11*11];int16_t a[11*11],b[11*11];
    for(int i=0;i<121;++i){y[i]=10000;a[i]=1200;b[i]=-2000;}
    for(unsigned mask=0;mask<256;++mask){
        uint16_t yy=0;int16_t ca=0,cb=0,weight=42;
        unsigned n=0;for(unsigned bit=0;bit<8;++bit)n+=(mask>>bit)&1u;
        assert(hb_directional_ycc64(mask|(n<<8),y+60,a+60,b+60,y+60,a+60,b+60,
                                    &yy,&ca,&cb,&weight,11)==0);
        assert(yy==10000);
        assert(weight==0);
        assert(ca==(n?1200:0));
        assert(cb==(n?-2000:0));
    }
}
static void zero_y_passthrough(void){
    uint16_t y[121]={0};int16_t a[121],b[121];
    for(int i=0;i<121;++i){a[i]=1555;b[i]=-2455;}
    uint16_t yy=1;int16_t ca=2,cb=3,w=4;
    assert(hb_directional_ycc64(0x8ff,y+60,a+60,b+60,y+60,a+60,b+60,
                               &yy,&ca,&cb,&w,11)==0);
    assert(yy==0&&ca==1555&&cb==-2455&&w==0);
}
static void input_guards(void){
    uint16_t y[121];int16_t a[121],b[121];
    for(int i=0;i<121;++i){y[i]=(uint16_t)(5000+3*i);a[i]=(int16_t)(-100+i);
       b[i]=(int16_t)(200-i);}
    uint16_t yy=0;int16_t ca=0,cb=0,w=0;
    uint16_t copy_y[121];int16_t copy_a[121],copy_b[121];
    memcpy(copy_y,y,sizeof(y));memcpy(copy_a,a,sizeof(a));memcpy(copy_b,b,sizeof(b));
    assert(hb_directional_ycc64(0x8ff,y+60,a+60,b+60,y+60,a+60,b+60,
                               &yy,&ca,&cb,&w,11)==0);
    assert(!memcmp(copy_y,y,sizeof(y))&&!memcmp(copy_a,a,sizeof(a))&&!memcmp(copy_b,b,sizeof(b)));
    assert(yy==y[60]);
    assert(hb_directional_ycc64(0x8ff,NULL,a+60,b+60,y+60,a+60,b+60,
                               &yy,&ca,&cb,&w,11)==-1);
    assert(hb_directional_ycc64(0x8ff,y+60,a+60,b+60,y+60,a+60,b+60,
                               &yy,&ca,&cb,&w,2)==-1);
}
static void directional_witness(void){
    uint16_t y[121];int16_t a[121],b[121];
    for(int i=0;i<121;++i){y[i]=12000;a[i]=1000;b[i]=-1000;}
    const int centre=60;
    y[centre-1]=6000; y[centre+1]=18000;
    a[centre-1]=2000; a[centre+1]=-1000;
    b[centre-1]=-2000;b[centre+1]=1000;
    y[centre-11]=3000;y[centre+11]=21000;
    a[centre-11]=0;a[centre+11]=2400;
    b[centre-11]=1100;b[centre+11]=-2200;
    y[centre-12]=20000;y[centre+12]=2000;
    y[centre-10]=7000;y[centre+10]=23000;
    struct {uint32_t mask;uint16_t yy,aa,bb,ll;} witnesses[]={
      {0x101,12000,980,64555,936},
      {0x102,12000,1003,64542,256},
      {0x210,12000,500,65036,0},
      {0x300,12000,0,0,0},
      {0x8ff,12000,995,64543,298},
      {0x20f,12000,1983,63561,1192},
      {0xffff,12000,531,65006,159}
    };
    for(unsigned i=0;i<sizeof witnesses/sizeof witnesses[0];++i){
        uint16_t yy=0;int16_t aa=0,bb=0,ll=0;
        assert(hb_directional_ycc64(witnesses[i].mask,y+60,a+60,b+60,
               y+60,a+60,b+60,&yy,&aa,&bb,&ll,11)==0);
        assert(yy==witnesses[i].yy);
        assert((uint16_t)aa==witnesses[i].aa);
        assert((uint16_t)bb==witnesses[i].bb);
        assert((uint16_t)ll==witnesses[i].ll);
    }
}

int main(void){flat_fixture();zero_y_passthrough();input_guards();directional_witness();
 puts("STAGE64_DIRECTIONAL_YCC_C11_CANDIDATE_SELF_TEST_PASS");return 0;}
