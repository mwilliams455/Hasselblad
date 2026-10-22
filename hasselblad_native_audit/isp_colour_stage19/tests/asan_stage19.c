/* SPDX-License-Identifier: MIT. Stage19 synthetic-only ASan/UBSan smoke. */
#include "hb_colour_stage19.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    const double D50[3] = {0.9642,1.0,0.8249};
    for(int gamut=0;gamut<2;gamut++) {
        double m[9];hb19_output_receipt r={0};
        assert(hb19_build_output_matrix(gamut,m,&r)==HB19_OK);
        assert(r.schema==19 && r.photographic_render_authorized==0);
        assert(r.vendor_hncs_colour_applied==0 && r.original_main_ccm_pixel_verified==0);
        double a[12]={ D50[0],D50[1],D50[2], -.1,.2,2.,
                       2.,3.,4., .5,1.,1.1 };
        double y[12];
        for(int i=0;i<12;i++)y[i]=-22.0;
        assert(hb19_apply_output_matrix(m,a,4,y)==HB19_OK);
        for(int i=0;i<3;i++)assert(fabs(y[i]-1)<1e-10);
        assert(hb19_apply_output_matrix(m,a,4,a)==HB19_OVERLAP);
        assert(hb19_apply_output_matrix(m,a,0,y)==HB19_BAD_INPUT);
        for(int i=0;i<12;i++)assert(isfinite(y[i]));
        double bad[12];memcpy(bad,a,sizeof(bad));bad[4]=NAN;
        double backup[12];memcpy(backup,y,sizeof(y));
        assert(hb19_apply_output_matrix(m,bad,4,y)==HB19_BAD_INPUT);
        assert(memcmp(y,backup,sizeof(y))==0);
        hb19_phocus_selector p={0};
        assert(hb19_select_phocus_wb(3100.8,&p)==HB19_OK);
        assert(p.truncated_kelvin==3100&&p.lut_effective_kelvin==3100);
        assert(p.original_phocus_payload_present==0&&p.hncs_render_authorized==0);
        assert(hb19_select_phocus_wb(NAN,&p)==HB19_BAD_INPUT);
    }
    puts("PASS Stage19 ASan/UBSan synthetic linear-PCS and Phocus-selector guards");
    return 0;
}
