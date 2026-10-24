/* Standalone mock used ONLY to check Stage68 argument ordering. This is NOT
 * a green interpolator and must never be linked into a camera renderer. */
#include <stdint.h>
#include <string.h>
static unsigned calls;
static int16_t saved_edge[8],saved_raw[8],saved_floors[2];
void hb_green_at_colour63(const uint16_t *raw,const float *horizontal,
 const float *vertical,const float *scale,int stride,const int16_t first[8],
 const int16_t second[8],int16_t floor1,int16_t floor2,
 int32_t *green,int32_t *mask,int16_t *max) {
 (void)raw;(void)horizontal;(void)vertical;(void)scale;(void)stride;
 memcpy(saved_edge,first,sizeof saved_edge);
 memcpy(saved_raw,second,sizeof saved_raw);
 saved_floors[0]=floor1;saved_floors[1]=floor2;
 ++calls;*green=32100;*mask=0x511;*max=234;
}
unsigned hb68_mock_calls(void){return calls;}
void hb68_mock_read(int16_t a[8],int16_t b[8],int16_t f[2]){
 memcpy(a,saved_edge,sizeof saved_edge);
 memcpy(b,saved_raw,sizeof saved_raw);
 memcpy(f,saved_floors,sizeof saved_floors);
}
