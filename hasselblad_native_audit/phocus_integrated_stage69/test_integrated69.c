/* Independent host ORCHESTRATION oracle. Both sides intentionally invoke the
 * same previously validated Stage61/62/63/67/68 kernels, so byte parity here
 * tests ordering, CFA plane writes, storage/strides and composition ONLY.
 * It is NOT a proof of original vendor CPU, device or full-frame equivalence.
 */
#include "interpolate69.h"
#include "../phocus_gradient_stage61/gradient_maps61.h"
#include "../phocus_interpolation_stage62/interpolation62.h"
#include "../phocus_green_stage63/green63.h"
#include "../phocus_inline_stage67/green_site_mask67.h"
#include "../phocus_coloursite_stage68/colour_site68.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXPLANES 11
static uint32_t random_state=UINT32_C(0x69202501);
static uint32_t rand32(void){random_state^=random_state<<13;
    random_state^=random_state>>17;random_state^=random_state<<5;return random_state;}
typedef struct {
    uint8_t *storage[MAXPLANES];
    void *buffer[MAXPLANES];
    size_t bytes[MAXPLANES];
    HB66Planes p;
    HB69Scratch s;
} Fixture;
static Fixture allocate(int width,int height,int stride,int kind){
    Fixture f={0};
    const size_t n=(size_t)height*stride;
    for(int i=0;i<MAXPLANES;++i){
        size_t bytes=n*(i>=7&&i<=9?sizeof(float):sizeof(uint16_t));
        uint8_t *data=(uint8_t*)malloc(bytes+32);
        assert(data);
        memset(data,0xa5,bytes+32);
        f.storage[i]=data;f.buffer[i]=data+16;f.bytes[i]=bytes;
        memset(f.buffer[i],0,bytes);
    }
    f.p.domain=(HB66Domain){width,height,stride,HB66_SCALAR_FLAGS};
    f.p.raw=f.buffer[0];f.p.red=f.buffer[1];f.p.green=f.buffer[2];
    f.p.blue=f.buffer[3];f.p.mask=f.buffer[4];
    f.s.smoothed_raw=f.buffer[5];f.s.signed_edge=f.buffer[6];
    f.s.horizontal_scale=f.buffer[7];f.s.vertical_scale=f.buffer[8];
    f.s.midgreen_scale=f.buffer[9];f.s.midgreen_codes=f.buffer[10];
    uint16_t *raw=f.buffer[0];
    for(size_t i=0;i<n;++i){
        uint32_t q=rand32();
        if(kind==0)raw[i]=10000;
        else if(kind==1)raw[i]=(uint16_t)((i*97+q%17)%65536);
        else if(kind==2)raw[i]=(uint16_t)(q&65535u);
        else raw[i]=(uint16_t)(((i/(size_t)stride)<(size_t)(height/2))?(i%(size_t)stride<(size_t)(width/2)?100:65000):
                                (i%(size_t)stride<(size_t)(width/2)?32768:1));
    }
    for(int i=1;i<=4;++i){
        uint16_t *u=f.buffer[i];
        for(size_t j=0;j<n;++j)u[j]=(uint16_t)(1000u+i*119u+j%97u);
    }
    return f;
}
static void release(Fixture *f){for(int i=0;i<MAXPLANES;++i)free(f->storage[i]);}
static void guards(const Fixture *f){
    for(int i=0;i<MAXPLANES;++i){
        for(int k=0;k<16;++k){
            assert(f->storage[i][k]==0xa5);
            assert(f->storage[i][f->bytes[i]+16+(size_t)k]==0xa5);
        }
    }
}
static size_t pos(const HB66Planes *p,int x,int y){return (size_t)y*p->domain.stride+x;}
static void reference(Fixture *f,HB69Parameters par){
    HB66Planes *p=&f->p;HB69Scratch *s=&f->s;
    int w=p->domain.width,h=p->domain.height,d=p->domain.stride;
    for(int y=1;y<h-1;++y)
        assert(!hb_gradient_smooth_row61(p->raw+(size_t)y*d,
                 s->smoothed_raw+(size_t)y*d,d,w));
    for(int y=2;y<h-2;++y)
        assert(!hb_gradient_edge_row61(s->smoothed_raw+(size_t)y*d,
                 s->signed_edge+(size_t)y*d,d,w));
    assert(!hb_gradient_scale61(p->raw,w,h,d,2,2,w-2,h-2,
                 par.scale_threshold,s->horizontal_scale,s->vertical_scale));
    assert(!hb_gradient_green61(p->raw,w,h,d,2,2,w-2,h-2,
                 s->horizontal_scale,s->vertical_scale,s->midgreen_scale,
                 s->midgreen_codes));
    memcpy(p->green,p->raw,(size_t)h*d*sizeof(uint16_t));
    for(int y=4;y<h-4;y+=2)for(int x=4;x<w-4;x+=2){
        for(int part=0;part<2;++part){
            int cx=x+part,cy=y+part;size_t i=pos(p,cx,cy);
            int32_t g=0,m=0;int16_t maxgrad=0;
            assert(!hb_colour_site_green68(p->raw+i,s->signed_edge+i,
                s->horizontal_scale+i,s->vertical_scale+i,s->midgreen_scale+i,
                d,par.edge_floor,par.raw_floor,&g,&m,&maxgrad));
            p->green[i]=(uint16_t)(uint32_t)g;
            p->mask[i]=(uint16_t)(uint32_t)m;
            if(part==0){p->red[i]=p->raw[i];p->blue[i]=0;
                size_t g0=pos(p,x+1,y),g1=pos(p,x,y+1);
                p->red[g0]=p->red[g1]=0;
                p->green[g0]=p->raw[g0];p->green[g1]=p->raw[g1];
                p->blue[g0]=p->blue[g1]=0;
            }else{p->red[i]=0;p->blue[i]=p->raw[i];}
        }
    }
    for(int y=6;y<h-6;y+=2)for(int x=6;x<w-6;x+=2){
        size_t r=pos(p,x,y),b=pos(p,x+1,y+1);
        p->blue[r]=p->mask[r]?(uint16_t)hb_blue_at_red62(p->blue+r,
                     p->green+r,p->mask[r],d):0;
        p->red[b]=p->mask[b]?(uint16_t)hb_blue_at_red62(p->red+b,
                     p->green+b,p->mask[b],d):0;
    }
    for(int y=8;y<h-8;y+=2)for(int x=8;x<w-8;x+=2){
        const size_t sites[2]={pos(p,x+1,y),pos(p,x,y+1)};
        for(int j=0;j<2;++j){
            size_t i=sites[j];int16_t a[8],b[8];uint16_t mask=0;
            assert(!hb_green_site_mask67(p->raw+i,s->signed_edge+i,d,
                par.edge_floor,par.raw_floor,a,b,&mask));
            p->mask[i]=mask;
            if(mask){uint16_t red=0,blue=0;
                hb_red_blue_at_green62(p->red+i,p->green+i,p->blue+i,
                                     &red,&blue,mask,d);
                p->red[i]=red;p->blue[i]=blue;
            }else{p->red[i]=p->blue[i]=0;}
        }
    }
}
static void fixture(int width,int height,int stride,int kind){
    Fixture a=allocate(width,height,stride,kind);
    Fixture b=allocate(width,height,stride,kind);
    /* Ensure both inputs are identical but separately allocated. */
    const size_t n=(size_t)height*stride;
    for(int i=0;i<MAXPLANES;++i)memcpy(b.buffer[i],a.buffer[i],a.bytes[i]);
    HB69Parameters param={25.0,50,400};HB69Results result={0};
    const uint16_t *source=a.p.raw;
    uint16_t *original=malloc(n*sizeof(uint16_t));assert(original);
    memcpy(original,source,n*sizeof(uint16_t));
    assert(hb_interpolate69(&a.p,&a.s,param,&result)==0);
    reference(&b,param);
    for(int i=0;i<MAXPLANES;++i){
        if(memcmp(a.buffer[i],b.buffer[i],a.bytes[i])){
            fprintf(stderr,"Stage69 host composition mismatch: buffer %d ",i);
            fprintf(stderr,"%dx%d stride=%d fixture=%d\n",width,height,stride,kind);
            abort();
        }
    }
    assert(memcmp(original,source,n*sizeof(uint16_t))==0);
    assert(result.wiring.events.total_events>0);
    assert(result.real_colour_site_estimates==result.wiring.events.green_colour_estimates);
    assert(result.real_green_site_masks==result.wiring.events.green_site_masks);
    assert(result.real_red_blue_green_calls==result.wiring.green_site_rb_calls);
    assert(result.real_opposite_colour_calls==result.wiring.opposite_colour_calls);
    const uint16_t before=a.p.red[0];
    a.p.domain.flags=0;
    assert(hb_interpolate69(&a.p,&a.s,param,&result)==-2);
    assert(a.p.red[0]==before);
    a.p.domain.flags=0xffff;
    HB69Scratch broken=a.s;
    broken.signed_edge=(int16_t*)a.p.raw;
    assert(hb_interpolate69(&a.p,&broken,param,&result)==-1);
    assert(a.p.red[0]==before);
    param.scale_threshold=0.0;
    assert(hb_interpolate69(&a.p,&a.s,param,&result)==-1);
    assert(a.p.red[0]==before);
    guards(&a);guards(&b);
    free(original);release(&a);release(&b);
}
int main(void){
    const int shapes[][3]={{24,24,24},{32,40,43},{64,64,69},{80,88,96}};
    for(int s=0;s<4;++s)for(int kind=0;kind<4;++kind)
        fixture(shapes[s][0],shapes[s][1],shapes[s][2],kind);
    puts("STAGE69_HOST_COMPOSITION_16_CASES_PASS");
    return 0;
}
