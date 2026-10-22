/* Synthetic bounds/safety check, no firmware or camera data. */
#include "../src/hb_dng_pcs_bridge.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static int error(int n) {fprintf(stderr,"guard %d failed\n",n);return n;}
int main(void) {
    const double f[9]={.63,.13,.24,.22,.76,.02,-.04,-.46,1.33};
    const double cc[9]={1.03,.01,.0,.01,1.,-.01,.01,-.02,1.02};
    const double ab[3]={1.,1.,1.},n[3]={.60,1.,.37};
    double out[9]={0};hb_dng_pcs_receipt receipt={0};
    int st=hb_dng_pcs_build(f,f,cc,cc,ab,n,out,&receipt);
    if(st!=0||receipt.photographic_render_authorized!=0||receipt.schema!=18)return error(1);
    double xyz[3]={0},rgb[3]={.4,1.2,-.1};
    if(hb_dng_pcs_apply(out,rgb,1,xyz)!=0 || !isfinite(xyz[0]) || !isfinite(xyz[1]) || !isfinite(xyz[2]))return error(2);
    double snapshot[3];memcpy(snapshot,rgb,sizeof rgb);
    if(hb_dng_pcs_apply(out,rgb,1,rgb)!=HB_DNG_PCS_OVERLAP || memcmp(snapshot,rgb,sizeof rgb)!=0)return error(3);
    const double d50[3]={.9642,1.,.8249};double neutral_xyz[3]={0};
    if(hb_dng_pcs_apply(out,n,1,neutral_xyz)!=0)return error(4);
    for(int i=0;i<3;i++)if(fabs(neutral_xyz[i]-d50[i])>1e-9)return error(5);
    double nonfinite[3]={.1,NAN,.4},old_xyz[3]={77,77,77};
    if(hb_dng_pcs_apply(out,nonfinite,1,old_xyz)!=HB_DNG_PCS_INVALID ||old_xyz[0]!=77)return error(6);
    printf("PASS Stage18 sanitizer smoke; no camera or photographic rendering\n");
    return 0;
}
