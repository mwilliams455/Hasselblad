/* Sensor-independent algorithmic reconstruction, no original executable,
 * photograph, profile, or calibration data. Uses the Stage67 scalar cardinal
 * gradient implementation; colour CFA sites use different diagonals.
 */
#include "colour_gradient68.h"
#include "../phocus_inline_stage67/raw_gradient67.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct { int8_t y0,x0,y1,x1; } Pair68;
#define D(A,B,C,E) { A,B,C,E }
/* Six abs-differences / diagonal, order NE,SE,SW,NW. Each is included
 * once; there is no intermediate rounding in this diagonal accumulator. */
static const Pair68 diagonal[4][6] = {
    {D(-2,1,-1,0), D(-2,2,0,0), D(-1,0,0,-1),
     D(-1,1,1,-1), D(-1,2,0,1), D(0,1,1,0)},
    {D(-1,-1,1,1), D(-1,0,0,1), D(0,-1,1,0),
     D(0,0,2,2), D(0,1,1,2), D(1,0,2,1)},
    {D(-1,0,0,-1), D(-1,1,1,-1), D(0,-1,1,-2),
     D(0,0,2,-2), D(0,1,1,0), D(1,0,2,-1)},
    {D(-2,-2,0,0), D(-2,-1,-1,0), D(-1,-2,0,-1),
     D(-1,-1,1,1), D(-1,0,0,1), D(0,-1,1,0)}
};
#undef D

static uint32_t diff(const uint16_t *p,ptrdiff_t s,Pair68 e) {
    uint32_t a = p[(ptrdiff_t)e.y0*s+e.x0];
    uint32_t b = p[(ptrdiff_t)e.y1*s+e.x1];
    return a>b ? a-b : b-a;
}

int hb_colour_raw_gradient68(const uint16_t *raw, int stride, int16_t out[8]) {
    if (!raw || !out || stride<5) return -1;
    if (hb_inline_raw_gradient67(raw,stride,out)!=0) return -1;
    const ptrdiff_t s=stride;
    for (unsigned i=0; i<4; ++i) {
        uint32_t accumulator=0;
        for (unsigned j=0;j<6;++j) accumulator += diff(raw,s,diagonal[i][j]);
        const uint16_t low=(uint16_t)(accumulator>>3);
        int16_t signed_bits;
        memcpy(&signed_bits,&low,sizeof signed_bits);
        out[i+4]=signed_bits;
    }
    return 0;
}
