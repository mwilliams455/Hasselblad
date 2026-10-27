#include "frame97.h"
#include "chroma97.h"
#include "../phocus_integrated_stage69/interpolate69.h"
#include "../phocus_noise_stage65/noise65.h"
#include "../phocus_output_stage74/output74.h"
#include <pthread.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

enum { RAW,RED,GREEN,BLUE,MASK,SMOOTH,EDGE,HORIZONTAL,VERTICAL,SCALE,MIDGREEN,
       Y,C1,C2,SMOOTH_Y,MEDIAN_C1,MEDIAN_C2,OUT_Y,OUT_C1,OUT_C2,OUT_AUX,ITEMS };
typedef struct {
    const uint16_t *input;
    uint16_t *assembled;
    int raw_width,width,offset,rows,tile_width,index,workers,status; double nr,nb;
} Job;

/* Stage96 scheduling and neutral adapter plus bounded local chroma correction.
 * The recovered Phocus kernels and raw demosaic are unchanged. This adapter
 * is not a claim of equivalence to an observed native Phocus input graph. */
static void *render_job(void *argument) {
    Job *j=argument;
    const int tw=j->tile_width,sw=tw+64,sh=128;
    const size_t sites=(size_t)sw*sh;
    const double scale=fmin(1.0,fmin(j->nr,j->nb));
    const double gain[3]={scale/j->nr,scale,scale/j->nb};
    const double restore[3]={j->nr/scale,1.0/scale,j->nb/scale};
    const int hw=tw+4,hh=68;
    void *v[ITEMS]={0};uint16_t *tile=malloc((size_t)tw*64*6),*halo=malloc((size_t)hw*hh*6);
    j->status=-3;
    if(!tile||!halo)goto done;
    for(int i=0;i<ITEMS;i++) {
        v[i]=malloc(sites*((i>=HORIZONTAL&&i<=SCALE)?4:2));
        if(!v[i])goto done;
    }
    for(int x=j->index*tw;x<j->width;x+=j->workers*tw) {
        const int anchor=x<j->width-tw?x:j->width-tw;
        const int skip=x-anchor,copy=j->width-x<tw?j->width-x:tw;
        for(int i=0;i<ITEMS;i++)memset(v[i],0,sites*((i>=HORIZONTAL&&i<=SCALE)?4:2));
        for(int y=0;y<sh;y++)memcpy((uint16_t*)v[RAW]+(size_t)y*sw,
            j->input+(size_t)y*j->raw_width+anchor,(size_t)sw*2);
        HB66Planes planes={{sw,sh,sw,0xffffu},v[RAW],v[RED],v[GREEN],v[BLUE],v[MASK]};
        HB69Scratch scratch={v[SMOOTH],v[EDGE],v[HORIZONTAL],v[VERTICAL],v[SCALE],v[MIDGREEN]};
        HB69Results results;
        if(hb_interpolate69(&planes,&scratch,(HB69Parameters){1.0,32,200},&results)) {j->status=-4;goto done;}
        /* Every input factor is <=1: balancing cannot clip an input plane.
         * Native chroma zero must represent the DNG's neutral, not equal
         * sensor responses. Restore camera RGB before the existing colour path. */
        for(int channel=0;channel<3;channel++) {
            uint16_t *plane=v[RED+channel];
            for(size_t i=0;i<sites;i++)plane[i]=(uint16_t)floor(plane[i]*gain[channel]+0.5);
        }
        HBNoiseContext65 noise={.width=sw,.height=sh,.stride=sw,.flags=0xffffu,
            .optimized_view=0,.strength=0,.red=v[RED],.green=v[GREEN],.blue=v[BLUE],
            .y=v[Y],.c1=v[C1],.c2=v[C2],.direction_mask=v[MASK],.smooth_y=v[SMOOTH_Y],
            .median_c1=v[MEDIAN_C1],.median_c2=v[MEDIAN_C2],.out_y=v[OUT_Y],
            .out_c1=v[OUT_C1],.out_c2=v[OUT_C2],.out_aux=v[OUT_AUX]};
        HBNoiseCounters65 counters;
        if(hb_color_noise65(&noise,&counters)) {j->status=-5;goto done;}
        if(hb74_convert_roi(v[OUT_Y],v[OUT_C1],v[OUT_C2],sw,sh,sw,30,30,hw,hh,1.0,halo,(size_t)hw*hh*3)) {j->status=-6;goto done;}
        for(size_t i=0;i<(size_t)hw*hh;i++)for(int channel=0;channel<3;channel++)
            halo[3*i+channel]=(uint16_t)fmin(65535.0,floor(halo[3*i+channel]*restore[channel]+0.5));
        if(hb97_chroma_roi(halo,(size_t)hw*hh*3,hw,hh,j->nr,j->nb,tile,(size_t)tw*64*3)) {j->status=-7;goto done;}
        /* Censored prepared Bayer samples cannot support a colour correction.
         * Keep Stage96 exactly in their two-pixel neighbourhood as well as
         * the RGB-domain clipping guard inside hb97_chroma_roi. */
        for(int yy=0;yy<64;yy++)for(int xx=0;xx<tw;xx++) {
            int censored=0;
            for(int dy=-2;dy<=2&&!censored;dy++)for(int dx=-2;dx<=2;dx++) {
                uint16_t value=((uint16_t*)v[RAW])[(size_t)(yy+32+dy)*sw+xx+32+dx];
                if(value==0||value==65535){censored=1;break;}
            }
            if(censored)memcpy(tile+((size_t)yy*tw+xx)*3,halo+((size_t)(yy+2)*hw+xx+2)*3,6);
        }
        for(int y=0;y<j->rows;y++)memcpy(j->assembled+((size_t)y*j->width+x)*3,
            tile+((size_t)(y+j->offset)*tw+skip)*3,(size_t)copy*6);
    }
    j->status=0;
done:
    for(int i=0;i<ITEMS;i++)free(v[i]);
    free(halo);free(tile);return NULL;
}

int hb97_render_band(const uint16_t *band,size_t input_count,int raw_width,
    int row_offset,int row_count,int workers,uint16_t *output,size_t output_capacity,double nr,double nb) {
    if(!isfinite(nr)||!isfinite(nb)||nr<0.0625||nr>16.0||nb<0.0625||nb>16.0)return -2;
    if(!band||!output||raw_width<128||raw_width>8192||row_offset<0||row_offset>63||
       row_count<1||row_count>64-row_offset||workers<1||workers>4)return -1;
    const int width=(raw_width-64)&~1,tw=width>=256?256:64;
    const size_t in=(size_t)raw_width*128,n=(size_t)width*row_count*3;
    if(input_count<in||output_capacity<n)return -1;
    const uintptr_t a=(uintptr_t)band,b=(uintptr_t)output;
    if(a>UINTPTR_MAX-in*2||b>UINTPTR_MAX-n*2||!(a+in*2<=b||b+n*2<=a))return -1;
    uint16_t *assembled=malloc(n*2);if(!assembled)return -3;
    const int tiles=(width+tw-1)/tw;
    if(workers>tiles)workers=tiles;
    Job jobs[4];pthread_t threads[4];int started[4]={0};
    for(int i=0;i<workers;i++) {
        jobs[i]=(Job){band,assembled,raw_width,width,row_offset,row_count,tw,i,workers,-3,nr,nb};
        if(i && pthread_create(&threads[i],NULL,render_job,&jobs[i])==0)started[i]=1;
        else if(i)render_job(&jobs[i]);
    }
    render_job(&jobs[0]);
    for(int i=1;i<workers;i++)if(started[i])pthread_join(threads[i],NULL);
    int status=0;
    for(int i=0;i<workers;i++)if(jobs[i].status)status=jobs[i].status;
    if(!status)memcpy(output,assembled,n*2);
    free(assembled);return status;
}
