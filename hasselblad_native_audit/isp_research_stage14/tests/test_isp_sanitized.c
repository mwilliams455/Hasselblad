/* SPDX-License-Identifier: MIT - standalone Stage14 ASan/UBSan smoke test. */
#include "hb_isp_research.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void) {
    uint32_t *source=calloc(49152,sizeof(*source));
    int32_t *ccm_src=calloc(768,sizeof(*ccm_src));
    uint32_t *lut=calloc(6144,sizeof(*lut));
    int32_t *ccm=calloc(96,sizeof(*ccm));
    uint32_t *knots=calloc(257,sizeof(*knots));
    assert(source&&ccm_src&&lut&&ccm&&knots);
    for(size_t p=0;p<8;p++)for(size_t j=0;j<6144;j++) {
        /* Deliberately synthetic two-halfword data in the 12-bit range. */
        uint32_t x=(uint32_t)(100+p*80+(j*13)%3000);
        uint32_t y=(uint32_t)(200+p*40+(j*7)%2700);
        source[p*6144+j]=x|(y<<16);
    }
    for(size_t j=0;j<768;j++)ccm_src[j]=(int32_t)(j%197)-93;
    const uint32_t divs[7]={2,2,3,4,5,6,7};
    hb_isp_research_receipt receipt={0};
    int rc=hb_isp_research_prepare(source,49152,ccm_src,768,divs,
                 4300,0,73,HB_ISP_ROUTE_NORMAL_STILL3,lut,ccm,knots,&receipt);
    assert(rc==HB_ISP_OK && knots[0]==0 && knots[256]==65536);
    assert(receipt.photographic_render_authorized==0 && receipt.main_pixel_sampler_verified==0);
    assert(receipt.unresolved_contracts_mask==255);
    uint32_t mask=0;
    assert(hb_isp_research_main_gate(&mask)==HB_ISP_UNVERIFIED_PHOTOGRAPHIC && mask==255);
    const double rgb[12]={0,0,0,1,1,1,.5,.5,.5,.123,.456,.789};
    double dest[12]={0};
    rc=hb_isp_research_display_candidate(lut,rgb,4,dest,&receipt);
    assert(rc==HB_ISP_OK && receipt.sampled_test_pixels==4);
    for(int i=0;i<12;i++)assert(isfinite(dest[i]) && dest[i]>=0 && dest[i]<=1);
    double bad[3]={1.01,.5,.5};
    double unchanged[3]={-9,-9,-9};
    const hb_isp_research_receipt prior=receipt;
    assert(hb_isp_research_display_candidate(lut,bad,1,unchanged,&receipt)==HB_ISP_BAD_DOMAIN);
    assert(unchanged[0]==-9 && !memcmp(&receipt,&prior,sizeof(prior)));
    uint32_t invalid[7]={0};
    assert(hb_isp_research_prepare(source,49152,ccm_src,768,invalid,
                4300,0,73,0,lut,ccm,knots,&receipt)==HB_ISP_BAD_DOMAIN);
    assert(receipt.sampled_test_pixels==4);
    free(source);free(ccm_src);free(lut);free(ccm);free(knots);
    puts("PASS Stage14 ASan+UBSan synthetic ISP boundary and no-photo gate");
    return 0;
}
