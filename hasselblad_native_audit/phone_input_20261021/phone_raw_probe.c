/* SPDX-License-Identifier: MIT. Host/Android offline probe, no camera access. */
#include "hb_phone_raw.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
    if (argc!=4) return 2;
    FILE *f=fopen(argv[2],"r");if(!f)return 3;
    hb_awb_frame_input d={0};unsigned cfa,white;
    int n=fscanf(f,"%u %u %u %u %u %u %u %u %u %" SCNd64 " %" SCNd64 " %" SCNd64 " %" SCNd64 " %u",
        &d.width,&d.height,&d.row_stride_bytes,&d.pixel_stride_bytes,&d.left,&d.top,&d.right,&d.bottom,&cfa,
        &d.black_q16[0],&d.black_q16[1],&d.black_q16[2],&d.black_q16[3],&white);
    fclose(f);if(n!=14||white>65535)return 4;d.cfa=(enum hb_awb_cfa)cfa;d.white_code=(uint16_t)white;
    f=fopen(argv[1],"rb");if(!f)return 5;
    if(fseek(f,0,SEEK_END))return 6;
    long size=ftell(f);if(size<1||size>67108864)return 7;rewind(f);
    unsigned char *raw=malloc((size_t)size);hb_phone_raw_grid *out=malloc(sizeof *out);
    if(!raw||!out)return 8;
    if(fread(raw,1,(size_t)size,f)!=(size_t)size)return 9;
    fclose(f);
    int status=hb_phone_raw_build(raw,(size_t)size,&d,HB_PHONE_UNTOUCHED_RAW16_LE,out);
    if(status)return 10+status;
    f=fopen(argv[3],"wb");if(!f)return 14;
    if(fwrite(out,1,sizeof *out,f)!=sizeof *out||fclose(f))return 15;
    printf("{\"status\":0,\"bytes\":%zu,\"samples\":%" PRIu64 ",\"ratio_blocks\":%u}\n",sizeof *out,out->raw.input_sample_count,out->ratio_blocks);
    free(raw);free(out);return 0;
}
