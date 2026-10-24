/* Scene-independent RAW-site directional gradients, independent C11.
 * No vendor executable bytes, disassembly, original photographs or profiles.
 * Derived from a bounded CPU instruction study, not fitted to photographs.
 */
#include "raw_gradient67.h"
#include <stddef.h>
#include <stdint.h>

typedef struct { int8_t y0, x0, y1, x1; } Edge67;
#define P(Y,X,U,V) {Y,X,U,V}

/* Two main and four peripheral two-step differences per cardinal direction.
 * The peripheral terms are accumulated in TWO separate half-sums before the
 * final /8. Combining them first subtly changes one-code rounding cases. */
static const Edge67 primary[4][2]={
    { P(-2,0,0,0), P(-1,0,1,0) },
    { P(0,-1,0,1), P(0,0,0,2) },
    { P(-1,0,1,0), P(0,0,2,0) },
    { P(0,-2,0,0), P(0,-1,0,1) }
};
static const Edge67 peripheral[4][4]={
    { P(-2,-1,0,-1), P(-2,1,0,1), P(-1,-1,1,-1), P(-1,1,1,1) },
    { P(-1,-1,-1,1), P(-1,0,-1,2), P(1,-1,1,1), P(1,0,1,2) },
    { P(-1,-1,1,-1), P(-1,1,1,1), P(0,-1,2,-1), P(0,1,2,1) },
    { P(-1,-2,-1,0), P(-1,-1,-1,1), P(1,-2,1,0), P(1,-1,1,1) }
};
/* For N/S, group by stencil row; for E/W, group by column. */
static const uint8_t pairing[4][4]={{0,1,2,3},{0,2,1,3},{0,1,2,3},{0,2,1,3}};

/* Diagonals directly accumulate four two-step unsigned differences. */
static const Edge67 diagonal[4][4]={
    { P(-2,1,0,-1), P(-2,2,0,0), P(-1,1,1,-1), P(-1,2,1,0) },
    { P(-1,-1,1,1), P(-1,0,1,2), P(0,-1,2,1), P(0,0,2,2) },
    { P(-1,0,1,-2), P(-1,1,1,-1), P(0,0,2,-2), P(0,1,2,-1) },
    { P(-2,-2,0,0), P(-2,-1,0,1), P(-1,-2,1,0), P(-1,-1,1,1) }
};
#undef P

static uint32_t difference(const uint16_t *p, ptrdiff_t s, Edge67 e) {
    const uint32_t a=p[(ptrdiff_t)e.y0*s+e.x0];
    const uint32_t b=p[(ptrdiff_t)e.y1*s+e.x1];
    return a>b ? a-b : b-a;
}
int hb_inline_raw_gradient67(const uint16_t *p, int stride, int16_t out[8]) {
    if (!p || !out || stride<5) return -1;
    const ptrdiff_t s=stride;
    for (unsigned i=0; i<4; ++i) {
        const Edge67 *a=primary[i], *b=peripheral[i];
        uint32_t m=difference(p,s,a[0])+difference(p,s,a[1]);
        /* IMPORTANT: Preserve each integer truncation independently. */
        m += (difference(p,s,b[pairing[i][0]])+
              difference(p,s,b[pairing[i][1]])) >> 1;
        m += (difference(p,s,b[pairing[i][2]])+
              difference(p,s,b[pairing[i][3]])) >> 1;
        out[i]=(int16_t)(m>>3);
    }
    for (unsigned i=0;i<4;++i) {
        uint32_t m=0;
        for (unsigned j=0;j<4;++j)m+=difference(p,s,diagonal[i][j]);
        out[i+4]=(int16_t)(m>>3);
    }
    return 0;
}
