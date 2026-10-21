/* SPDX-License-Identifier: MIT */
#include "hb_phone_domain.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
int main(void) {
    hb_phone_temperature_input input = {0};
    input.anchor[0].kelvin = 2856;
    hb_phone_domain_request r = {2000,10000,100,-100,100,25};
    hb_phone_domain_result *output=malloc(sizeof(*output));
    assert(output);
    memset(output,0xA5,sizeof(*output));
    assert(hb_phone_domain_evaluate(&input,&r,output)==HB_PHONE_DOMAIN_OK);
    assert(output->schema_version==HB_PHONE_DOMAIN_SCHEMA);
    assert(output->point_count==729);
    assert(output->representable==724);
    assert(output->temperature_clipped==3);
    assert(output->scene_signed_gain==1);
    assert(output->adjacent_duplicate==1);
    input.anchor[0].kelvin = 4321;
    assert(hb_phone_domain_evaluate(&input,&r,output)==HB_PHONE_DOMAIN_NATIVE);
    assert(output->representable==724); /* no mutation on failure */
    free(output);
    return 0;
}
