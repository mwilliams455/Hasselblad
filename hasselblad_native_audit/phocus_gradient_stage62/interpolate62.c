/* Scene-agnostic independent reconstruction of two CPU interpolation helpers.
 * No original executable, disassembly, private DNG data, or calibration.
 * Arithmetic follows the bounded observed AArch64 helper instructions:
 * unsigned widened products and division; 32-bit sum and signed average;
 * final signed minimum with 65534 and narrowing at caller/output sites.
 */
#include "interpolate62.h"
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct {
    uint16_t g, color[4];
    uint16_t green[4];
    uint32_t weight[4];
} FourNeighbours;

/* Blue-at-red sample index: NW=0, NE=1, SW=2, SE=3.
 * Red/blue-at-green sample index: up=0, right=1, down=2, left=3.
 */
static uint32_t weight(uint16_t center, uint16_t other) {
    const uint32_t a=center,b=other;
    return 1u + ((a>b ? a-b : b-a) >> 2);
}
static uint32_t min_65534_signed(uint32_t code) {
    int32_t s;
    memcpy(&s, &code, sizeof s);
    return s < 65534 ? code : UINT32_C(65534);
}
static uint32_t weighted_estimate(uint16_t center,
                                  uint16_t a, uint16_t b,
                                  uint32_t wa, uint32_t wb,
                                  uint64_t den) {
    /* wa,wb <= 16384, samples <= 65535. 64-bit products do not overflow in
     * the supported code domain. Intermediate candidate is narrowed to W32.
     */
    const uint64_t num=(uint64_t)wa*a + (uint64_t)wb*b;
    return den ? (uint32_t)((num*(uint64_t)center)/den) : 0u;
}
static uint64_t pair_den(const FourNeighbours *s, unsigned a, unsigned b) {
    /* Opposite-site gradient weight, matching the two native directed
     * sums. weight[b] weights sample[a] and vice versa. */
    return (uint64_t)s->weight[b]*s->green[a]
         + (uint64_t)s->weight[a]*s->green[b];
}
static uint32_t one_pair(const FourNeighbours *s, const uint16_t values[4],
                         unsigned a, unsigned b) {
    return weighted_estimate(s->g, values[a], values[b],
                             s->weight[b], s->weight[a], pair_den(s,a,b));
}
static uint32_t average_or_fallback(const uint32_t estimates[8],
                                   uint32_t count, const uint16_t values[4]) {
    uint32_t result;
    if (!count) {
        const uint32_t sum=(uint32_t)values[0]+values[1]+values[2]+values[3];
        result=sum>>2;
    } else {
        uint32_t sum=0;
        for (unsigned i=0;i<8;++i)sum+=estimates[i]; /* intentional W32 wrap */
        int32_t signed_sum;
        memcpy(&signed_sum,&sum,sizeof signed_sum);
        const int32_t average=signed_sum/(int32_t)count;
        memcpy(&result,&average,sizeof result);
    }
    return min_65534_signed(result);
}
static uint32_t interpolate(const FourNeighbours *s,
                            const uint16_t values[4],
                            const uint8_t pair_a[8],
                            const uint8_t pair_b[8],uint32_t mask) {
    uint32_t count=0,estimate[8]={0};
    for (unsigned i=0;i<8;++i) {
        if ((mask & (1u<<i)) && pair_den(s,pair_a[i],pair_b[i])) {
            estimate[i]=one_pair(s,values,pair_a[i],pair_b[i]);
            ++count;
        }
    }
    return average_or_fallback(estimate,count,values);
}

uint32_t hb_blue_at_red_code62(const uint16_t *blue, const uint16_t *green,
                               uint32_t mask, int stride) {
    if (!blue || !green || stride<3)return 0;
    const ptrdiff_t d=stride;
    const ptrdiff_t locations[4]={-d-1,-d+1,d-1,d+1};
    FourNeighbours s={0};
    s.g=green[0];
    for (unsigned i=0;i<4;++i) {
        s.green[i]=green[locations[i]];
        s.color[i]=blue[locations[i]];
        s.weight[i]=weight(s.g,s.green[i]);
    }
    /* N,E,S,W,NE,SE,SW,NW. Paired diagonal paths 4/6 and 5/7
     * share their numerator/denominator but count as separate selections. */
    static const uint8_t a[8]={0,1,2,0,2,0,2,0};
    static const uint8_t b[8]={1,3,3,2,1,3,1,3};
    return interpolate(&s,s.color,a,b,mask);
}

int hb_red_blue_at_green62(const uint16_t *red, const uint16_t *green,
                           const uint16_t *blue, uint16_t *out_red,
                           uint16_t *out_blue, uint32_t mask, int stride) {
    if (!red||!green||!blue||!out_red||!out_blue||stride<3)return -1;
    const ptrdiff_t d=stride;
    const ptrdiff_t locations[4]={-d,1,d,-1};
    FourNeighbours s={0};uint16_t reds[4],blues[4];
    s.g=green[0];
    for (unsigned i=0;i<4;++i) {
        s.green[i]=green[locations[i]];
        reds[i]=red[locations[i]];
        blues[i]=blue[locations[i]];
        s.weight[i]=weight(s.g,s.green[i]);
    }
    /* The first four bits contain repeated cardinal pair estimates;
     * the final four bits cover the four adjacent directional pairs. */
    static const uint8_t a[8]={0,1,0,1,0,1,2,3};
    static const uint8_t b[8]={2,3,2,3,1,2,3,0};
    const uint32_t red_code=interpolate(&s,reds,a,b,mask);
    const uint32_t blue_code=interpolate(&s,blues,a,b,mask);
    /* The caller's output references may point into source colour planes;
     * complete both computations before either 16-bit store. */
    *out_blue=(uint16_t)blue_code;
    *out_red=(uint16_t)red_code;
    return 0;
}
