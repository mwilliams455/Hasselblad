#include "interpolation62.h"
#include <stddef.h>

/* Convert modulo-2^32 arithmetic to a signed value without an out-of-range
 * signed conversion or signed overflow. C11 division then truncates to zero.
 */
static int32_t signed32(uint32_t value) {
    return value <= INT32_MAX ? (int32_t)value :
        -1 - (int32_t)(UINT32_MAX - value);
}

static int32_t upper_clamp(int32_t value) {
    return value < 65534 ? value : 65534;
}

static uint32_t weight(uint16_t center, uint16_t neighbour) {
    uint32_t difference = center >= neighbour ? center - neighbour : neighbour - center;
    return (difference >> 2) + 1;
}

/* Each pair uses the opposite neighbour's weight. The bounded uint16 input
 * domain keeps pair sums below 2^32 and products below 2^48. Explicit narrow
 * operations preserve the native duplicate-direction multiply semantics.
 */
static uint64_t pair_sum(const uint16_t samples[4], const uint32_t weights[4],
                         unsigned a, unsigned b) {
    return (uint64_t)weights[b]*samples[a] + (uint64_t)weights[a]*samples[b];
}

static int32_t interpolate(uint16_t center, const uint16_t green[4],
                           const uint16_t colour[4], const uint32_t weights[4],
                           const unsigned pairs[8][2], uint32_t narrow_mask,
                           uint32_t mask) {
    uint32_t total = 0, count = 0;
    for (unsigned i = 0; i < 8; ++i) {
        unsigned a = pairs[i][0], b = pairs[i][1];
        uint64_t denominator = pair_sum(green, weights, a, b);
        if ((mask & (UINT32_C(1) << i)) && (uint32_t)denominator != 0) {
            uint64_t numerator = pair_sum(colour, weights, a, b);
            if (narrow_mask & (UINT32_C(1) << i)) {
                numerator = (uint32_t)numerator;
                denominator = (uint32_t)denominator;
            }
            total += (uint32_t)((numerator*center)/denominator);
            ++count;
        }
    }
    if (count != 0)
        return upper_clamp(signed32(total)/(int32_t)count);
    uint32_t fallback = (uint32_t)colour[0]+colour[1]+colour[2]+colour[3];
    return upper_clamp((int32_t)(fallback >> 2));
}

int32_t hb_blue_at_red62(const uint16_t *colour, const uint16_t *green,
                         uint32_t mask, int stride) {
    const ptrdiff_t s = stride;
    const ptrdiff_t offsets[4] = {-s-1, -s+1, s-1, s+1}; /* NW, NE, SW, SE */
    const unsigned pairs[8][2] = {{0,1},{1,3},{2,3},{0,2},{1,2},{0,3},{1,2},{0,3}};
    uint16_t g[4], c[4];
    uint32_t weights[4];
    uint16_t center = *green;
    for (unsigned i = 0; i < 4; ++i) {
        g[i] = green[offsets[i]];
        c[i] = colour[offsets[i]];
        weights[i] = weight(center, g[i]);
    }
    return interpolate(center, g, c, weights, pairs, 0xc0, mask);
}

void hb_red_blue_at_green62(const uint16_t *first, const uint16_t *green,
                            const uint16_t *second, uint16_t *out_first,
                            uint16_t *out_second, uint32_t mask, int stride) {
    const ptrdiff_t s = stride;
    const ptrdiff_t offsets[4] = {-s, 1, s, -1}; /* N, E, S, W */
    const unsigned pairs[8][2] = {{0,2},{3,1},{0,2},{3,1},{0,1},{2,1},{2,3},{0,3}};
    uint16_t g[4], a[4], b[4];
    uint32_t weights[4];
    uint16_t center = *green;
    for (unsigned i = 0; i < 4; ++i) {
        g[i] = green[offsets[i]];
        a[i] = first[offsets[i]];
        b[i] = second[offsets[i]];
        weights[i] = weight(center, g[i]);
    }
    int32_t first_result = interpolate(center, g, a, weights, pairs, 0x0c, mask);
    int32_t second_result = interpolate(center, g, b, weights, pairs, 0x0c, mask);
    *out_second = (uint16_t)second_result;
    *out_first = (uint16_t)first_result;
}
