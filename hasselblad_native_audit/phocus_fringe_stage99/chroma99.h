#ifndef HB_CHROMA99_H
#define HB_CHROMA99_H
#include <stdint.h>
#include <stddef.h>
/* Input includes a real 15-pixel halo. flags: bit0 raw zero, bit1 raw white. */
int hb99_chroma_roi(const uint16_t *rgb,size_t count,const uint8_t *flags,size_t flag_count,
    int width,int height,double nr,double nb,uint16_t *out,size_t capacity);
#endif
