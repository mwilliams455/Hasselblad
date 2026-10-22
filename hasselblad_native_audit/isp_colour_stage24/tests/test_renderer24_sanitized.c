/* SPDX-License-Identifier: MIT
 * Synthetic inputs only, test transactional/guard behaviour under sanitizers.
 */
#include "hb24_renderer.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
int main(void){
    const double D50[3]={.9642,1.,.8249};
    const double fm[9]={.9642,0,0,0,1,0,0,0,.8249};
    const double cc[9]={1,0,0,0,1,0,0,0,1};
    const double neutral[3]={1,1,1};
    hb24_context ctx={0};hb24_receipt receipt={0};
    int st=hb24_build(fm,fm,cc,cc,NULL,neutral,HB19_SRGB,&ctx,&receipt);
    assert(st==HB24_OK && ctx.schema==24 && receipt.photographic_render_authorized==0);
    double white[3];
    for(int i=0;i<3;i++)white[i]=ctx.camera_to_xyz_d50[i*3+0]+ctx.camera_to_xyz_d50[i*3+1]+ctx.camera_to_xyz_d50[i*3+2];
    for(int i=0;i<3;i++)assert(fabs(white[i]-D50[i])<1e-12);
    double x[3*1024],y[3*1024];
    for(unsigned i=0;i<1024;i++)for(unsigned ch=0;ch<3;ch++){
       x[3*i+ch]=i%2 ? .75 : -.125; y[3*i+ch]=55.;
    }
    st=hb24_process(&ctx,x,1024,y,HB24_PCS_ONLY,NULL,0,NULL,NULL,0,&receipt);
    assert(st==HB24_OK && receipt.pixel_count==1024 && receipt.photographic_render_authorized==0);
    assert(receipt.true_hasselblad_ccm_pixel_proven==0 && receipt.existing_phone_renderer_modified==0);
    double baseline=y[0];
    assert(isfinite(baseline)&&baseline<0);
    hb24_receipt previous=receipt;
    for(unsigned i=0;i<1024;i++)for(unsigned ch=0;ch<3;ch++)y[3*i+ch]=55.;
    st=hb24_process(&ctx,x,1025,y,HB24_PCS_ONLY,NULL,0,NULL,NULL,0,&receipt);
    assert(st==HB24_BAD_SIZE && y[0]==55. && memcmp(&receipt,&previous,sizeof(receipt))==0);
    double bad[3]={NAN,1.,0.};double dst[3]={42,42,42};
    st=hb24_process(&ctx,bad,1,dst,HB24_PCS_ONLY,NULL,0,NULL,NULL,0,&receipt);
    assert(st!=HB24_OK && dst[0]==42. && memcmp(&receipt,&previous,sizeof(receipt))==0);
    double single[3]={.3,.5,.8};double copy[3];memcpy(copy,single,sizeof(copy));
    st=hb24_process(&ctx,single,1,single,HB24_PCS_ONLY,NULL,0,NULL,NULL,0,&receipt);
    assert(st==HB24_OVERLAP && memcmp(single,copy,sizeof(single))==0);
    uint32_t lut[6144]={0};uint8_t perm[3]={0,1,2};
    st=hb24_process(&ctx,x,1024,y,HB24_MAIN_HYPOTHESIS,lut,6144,perm,perm,0,&receipt);
    assert(st==HB24_UNVERIFIED_DOMAIN && y[0]==55.);
    for(unsigned i=0;i<1024;i++)for(unsigned ch=0;ch<3;ch++)x[3*i+ch]=.5;
    st=hb24_process(&ctx,x,1024,y,HB24_MAIN_HYPOTHESIS,lut,6144,perm,perm,0,&receipt);
    assert(st==HB24_OK && receipt.uses_stage21_MAIN_hypothesis==1);
    assert(receipt.true_hasselblad_lut_pixel_proven==0 && receipt.photographic_render_authorized==0);
    puts("PASS Stage24 guarded synthetic native composition: not HNCS");
    return 0;
}
