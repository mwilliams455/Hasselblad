/* Scene-independent equations; no vendor code or calibration payloads. */
#include "gradient_maps61.h"
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static int valid_bounds(int width, int height, int stride,
                        int x0, int y0, int x1, int y1, int margin) {
    if (width <= 0 || height <= 0 || stride < width ||
        (uint64_t)height * (uint64_t)stride > SIZE_MAX / sizeof(float) ||
        x0 < margin || y0 < margin || x1 <= x0 || y1 <= y0 ||
        x1 > width || y1 > height || ((x0 | y0) & 1)) return 0;
    /* The last cell includes its offset-one CFA site, then a margin. */
    const int64_t last_x = x0 + ((int64_t)x1 - x0 - 1) / 2 * 2;
    const int64_t last_y = y0 + ((int64_t)y1 - y0 - 1) / 2 * 2;
    return last_x + 1 + margin < width && last_y + 1 + margin < height;
}

static float absdiff(unsigned a, unsigned b) {
    return (float)(a > b ? a - b : b - a);
}

/* Alternating five-sample line: green, other, green, other, green. */
static float line_scale(const uint16_t *p, ptrdiff_t step,
                         double threshold, float *contrast) {
    const unsigned a = p[-2 * step], c = p[0], b = p[2 * step];
    const unsigned low = a < c ? a : c;
    if ((double)(low < b ? low : b) < threshold) return 1.0f;
    const unsigned u = p[-step], v = p[step];
    const float left_den = (float)(a + c + 1);
    const float right_den = (float)(b + c + 1);
    const float dl = absdiff(a, c) / left_den;
    const float dc = absdiff(u, v) / (float)(u + v + 1);
    const float dr = absdiff(c, b) / right_den;
    const float total = dr + (dl + dc);
    float left = ((float)u * 2.0f) / left_den;
    float center = (float)(u + v) / ((float)c * 2.0f + 1.0f);
    float right = ((float)v * 2.0f) / right_den;
    *contrast = total;
    /* The comparison is against a double constant, not 0.05f. */
    if ((double)total > 0.05) {
        const float denominator = total + total;
        center = ((center * 3.0f) * (total - dc)) / denominator;
        left = ((left * 3.0f) * (total - dl)) / denominator;
        right = ((right * 3.0f) * (total - dr)) / denominator;
    }
    const float sum = right + (center + left);
    return sum != 0.0f ? 3.0f / sum : sum;
}

int hb_gradient_scale61(const uint16_t *raw, int width, int height, int stride,
                        int x0, int y0, int x1, int y1, double threshold,
                        float *horizontal, float *vertical) {
    if (!raw || !horizontal || !vertical || !isfinite(threshold) ||
        threshold < 1.0 || threshold > 100.0 ||
        !valid_bounds(width, height, stride, x0, y0, x1, y1, 2)) return -1;
    for (int y = y0; y < y1; y += 2) {
        for (int x = x0; x < x1; x += 2) {
            const size_t red = (size_t)y * stride + x;
            const size_t g0 = red + 1, g1 = red + stride;
            horizontal[g0] = line_scale(raw + g0, 1, threshold, horizontal + g0 + 1);
            horizontal[g1] = line_scale(raw + g1, 1, threshold, horizontal + g1 + 1);
            vertical[g0] = line_scale(raw + g0, stride, threshold, vertical + g0 + 1);
            vertical[g1] = line_scale(raw + g1, stride, threshold, vertical + g1 + 1);
        }
    }
    return 0;
}

static float middle_two(float a, float b, float c, float d) {
    const float hi_ab = a > b ? a : b, lo_ab = a < b ? a : b;
    const float hi_cd = c > d ? c : d, lo_cd = c < d ? c : d;
    const float high = hi_ab > hi_cd ? hi_ab : hi_cd;
    const float low = lo_ab < lo_cd ? lo_ab : lo_cd;
    /* Preserve the original evaluation order, including its cancellation. */
    return (((((a + b) + c) + d) - high) - low) * 0.5f;
}

int hb_gradient_green61(const uint16_t *raw, int width, int height, int stride,
                        int x0, int y0, int x1, int y1,
                        const float *horizontal, const float *vertical,
                        float *scale, uint16_t *green) {
    if (!raw || !horizontal || !vertical || !scale || !green ||
        !valid_bounds(width, height, stride, x0, y0, x1, y1, 1)) return -1;
    for (int y = y0; y < y1; y += 2) {
        for (int x = x0; x < x1; x += 2) {
            for (int phase = 0; phase < 2; ++phase) {
                const size_t p = (size_t)(y + phase) * stride + x + phase;
                const float s = middle_two(horizontal[p - 1], horizontal[p + 1],
                                           vertical[p - stride], vertical[p + stride]);
                scale[p] = s;
                const float value = fminf(s * (float)raw[p], 65535.0f);
                green[p] = (uint16_t)(int32_t)value;
            }
        }
    }
    return 0;
}

int hb_gradient_smooth_row61(const uint16_t *row, uint16_t *out, int stride, int width) {
    if (!row || !out || width < 2 || stride < width) return -1;
    out[0] = out[width - 1] = 0;
    const ptrdiff_t s = stride;
    for (int x = 1; x < width - 1; ++x) {
        const uint16_t *p = row + x;
        const uint32_t corners = p[-s - 1] + p[-s + 1] + p[s - 1] + p[s + 1];
        const uint32_t cross = p[-s] + p[s] + p[-1] + p[1];
        out[x] = (uint16_t)((corners + 2 * cross + 4 * p[0]) / 16);
    }
    return 0;
}

int hb_gradient_edge_row61(const uint16_t *row, int16_t *out, int stride, int width) {
    if (!row || !out || width < 2 || stride < width) return -1;
    out[0] = out[width - 1] = 0;
    const ptrdiff_t s = stride;
    for (int x = 1; x < width - 1; ++x) {
        const uint16_t *p = row + x;
        const int32_t value = 4 * (int32_t)p[0] - p[-s - 1] - p[-s + 1] - p[s - 1] - p[s + 1];
        /* Signed arithmetic floor, without relying on a negative right shift. */
        out[x] = (int16_t)(value >= 0 ? value / 8 : -((-value + 7) / 8));
    }
    return 0;
}

static int16_t median3(int16_t a, int16_t b, int16_t c) {
    const int16_t lo = a < b ? a : b, hi = a > b ? a : b;
    return c < lo ? lo : c > hi ? hi : c;
}

int hb_gradient_median_row61(const int16_t *row, int16_t *out, int stride, int width) {
    if (!row || !out || width < 2 || stride < width) return -1;
    out[0] = row[0]; out[width - 1] = row[width - 1];
    const ptrdiff_t s = stride;
    for (int x = 1; x < width - 1; ++x) {
        const int16_t *p = row + x;
        out[x] = median3(median3(p[-s - 1], p[-s], p[-s + 1]),
                         median3(p[-1], p[0], p[1]),
                         median3(p[s - 1], p[s], p[s + 1]));
    }
    return 0;
}

static uint32_t signed_difference(int a, int b) {
    return (uint32_t)(a > b ? a - b : b - a);
}

static int16_t narrow_signed(uint32_t value) {
    const uint16_t bits = (uint16_t)value;
    int16_t result;
    memcpy(&result, &bits, sizeof result);
    return result;
}

int hb_gradient_directions61(const int16_t *p, int stride, int16_t out[8]) {
    if (!p || !out || stride < 5) return -1;
    const ptrdiff_t s = stride;
#define DIFF(y0,x0,y1,x1) signed_difference(p[(y0)*s+(x0)], p[(y1)*s+(x1)])
    const uint32_t h = DIFF(0,-1,0,0) + DIFF(0,0,0,1)
        + (DIFF(-1,-1,-1,0) + DIFF(-1,0,-1,1) + DIFF(1,-1,1,0) + DIFF(1,0,1,1)) / 2;
    out[1] = narrow_signed((h + DIFF(0,2,0,1) + (DIFF(-1,2,-1,1) + DIFF(1,2,1,1)) / 2) / 4);
    out[3] = narrow_signed((h + DIFF(0,-2,0,-1) + (DIFF(-1,-2,-1,-1) + DIFF(1,-2,1,-1)) / 2) / 4);
    const uint32_t v = DIFF(-1,0,0,0) + DIFF(0,0,1,0)
        + (DIFF(-1,-1,0,-1) + DIFF(0,-1,1,-1) + DIFF(-1,1,0,1) + DIFF(0,1,1,1)) / 2;
    out[0] = narrow_signed((v + DIFF(-2,0,-1,0) + (DIFF(-2,-1,-1,-1) + DIFF(-2,1,-1,1)) / 2) / 4);
    out[2] = narrow_signed((v + DIFF(2,0,1,0) + (DIFF(2,-1,1,-1) + DIFF(2,1,1,1)) / 2) / 4);
    const uint32_t backslash = DIFF(-1,-1,0,0) + DIFF(0,0,1,1) + DIFF(-1,0,0,1) + DIFF(0,-1,1,0);
    out[5] = narrow_signed((backslash + DIFF(1,1,2,2) + (DIFF(0,1,1,2) + DIFF(1,0,2,1)) / 2) / 4);
    out[7] = narrow_signed((backslash + DIFF(-1,-1,-2,-2) + (DIFF(-1,0,-2,-1) + DIFF(0,-1,-1,-2)) / 2) / 4);
    const uint32_t slash = DIFF(-1,1,0,0) + DIFF(0,0,1,-1) + DIFF(0,-1,-1,0) + DIFF(0,1,1,0);
    out[4] = narrow_signed((slash + DIFF(-1,1,-2,2) + (DIFF(-1,0,-2,1) + DIFF(0,1,-1,2)) / 2) / 4);
    out[6] = narrow_signed((slash + DIFF(1,-1,2,-2) + (DIFF(0,-1,1,-2) + DIFF(1,0,2,-1)) / 2) / 4);
#undef DIFF
    return 0;
}

uint16_t hb_gradient_mask61(const int16_t first[8], const int16_t second[8],
                            int16_t first_floor, int16_t second_floor) {
    int lo_a = first[0], hi_a = first[0], lo_b = second[0], hi_b = second[0];
    for (int i = 1; i < 8; ++i) {
        if (first[i] < lo_a) lo_a = first[i];
        if (first[i] > hi_a) hi_a = first[i];
        if (second[i] < lo_b) lo_b = second[i];
        if (second[i] > hi_b) hi_b = second[i];
    }
    const int half_min = lo_a >= 0 ? lo_a / 2 : -((-lo_a + 1) / 2);
    const uint32_t range = (uint32_t)((hi_a > 0 ? hi_a : 0) / 2 - half_min);
    const int a_value = ((uint16_t)lo_a & 0xfffe) + half_min - (int)(range / 16) + (int)(range / 4) + 8;
    const int b_value = ((uint16_t)lo_b & 0xfffe) + (hi_b > 0 ? hi_b : 0) / 2 + 8;
    int ta = narrow_signed((uint32_t)a_value), tb = narrow_signed((uint32_t)b_value);
    if (ta < first_floor) ta = first_floor;
    if (tb < second_floor) tb = second_floor;
    unsigned mask = 0, count = 0;
    for (int i = 0; i < 8; ++i) {
        if (first[i] < ta && second[i] < tb) { mask |= 1u << i; ++count; }
    }
    if (!mask) {
        for (int i = 0; i < 8; ++i) {
            if (first[i] < ta) { mask |= 1u << i; ++count; }
        }
    }
    return count ? (uint16_t)(mask | (count << 8)) : 0x8ff;
}
