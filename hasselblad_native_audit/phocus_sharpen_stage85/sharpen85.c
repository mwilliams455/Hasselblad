#include "sharpen85.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

int hb85_tables(int amount, double radius, int noise, int dark,
                int32_t at[16384], uint8_t nt[16384], uint32_t weights[9], int *taps) {
    if (!at || !nt || !weights || !taps || amount < 0 || amount > 1000 ||
        !isfinite(radius) || radius < 0.5 || radius > 4.0 ||
        noise < 0 || noise > 255 || dark < 0 || dark > 255) return -1;
    const float pivot = fminf((float)(dark * 64), 16383.0f);
    const float remainder = 16384.0f - pivot;
    const float pivot2 = pivot * pivot, remainder2 = remainder * remainder;
    const float peak = fminf(fmaxf(1638400.0f / ((float)amount + 100.0f),
                                  1000.0f), 10000.0f);
    const float scale = (float)(((double)amount + 100.0) / 16384.0);
    const int limit = noise * 64, transition = limit / 4 > 128 ? limit / 4 : 128;
    for (int i = 0; i < 16384; ++i) {
        float x = (float)i, value = (float)amount;
        if (amount > 0 && x < pivot) {
            float a = fmaf(6.0f, pivot, -2.0f * peak) / pivot;
            float b = fmaf(3.0f, pivot, -peak) / pivot2;
            a = x * (3.0f - a); b = x * b;
            float mapped = fmaf(x, b, a);
            value = mapped > 0.0f && mapped < 16384.0f
                ? fmaf(scale, mapped, -100.0f) : -100.0f;
        } else if (amount > 0 && x < 16384.0f) {
            float d = x - pivot;
            float b = fmaf(-3.0f, remainder, 16384.0f - peak) / remainder2;
            float mapped = peak + fmaf(d, d * b, 3.0f * d);
            if (mapped > 0.0f && mapped < 16384.0f)
                value = fmaf(scale, mapped, -100.0f);
        }
        at[i] = (int32_t)value;
        float gate = ((float)i - (float)(limit - transition)) / (float)transition;
        nt[i] = (uint8_t)(fminf(fmaxf(gate, 0.0f), 1.0f) * 255.0f);
    }
    int n = 0;
    for (int x = -4; x <= 4; ++x) {
        double d = (double)x / radius;
        uint32_t w = (uint32_t)(exp(-d * d) * 10000.0);
        if (w > 1000) weights[n++] = w;
    }
    if (n < 3) {
        uint32_t side = (uint32_t)(exp(-1.0 / radius / radius) * 10000.0);
        weights[0] = weights[2] = side; weights[1] = 10000; n = 3;
    }
    for (int i = n; i < 9; ++i) weights[i] = 0;
    *taps = n;
    return 0;
}

static size_t edge(size_t pos, int offset, size_t length) {
    if (offset < 0) return pos < (size_t)(-offset) ? 0 : pos - (size_t)(-offset);
    size_t p = pos + (size_t)offset;
    return p < length ? p : length - 1;
}

int hb85_sharpen14(const uint16_t *in, uint16_t *out, size_t w, size_t h,
                  int amount, double radius, int noise, int dark) {
    if (!in || !out || w == 0 || h == 0 || w > 8192 || h > 8192 ||
        w > 16777216 / h) return -1;
    int32_t at[16384]; uint8_t nt[16384]; uint32_t weights[9]; int taps;
    if (hb85_tables(amount, radius, noise, dark, at, nt, weights, &taps)) return -1;
    size_t count = w * h;
    for (size_t i = 0; i < count * 3; ++i) if (in[i] > 16383) return -1;
    if (amount == 0) { memmove(out, in, count * 3 * sizeof(*in)); return 0; }
    /* Host reference uses two luma planes. Android integration must stream rows. */
    uint16_t *luma = malloc(count * sizeof(*luma));
    uint16_t *horizontal = malloc(count * sizeof(*horizontal));
    if (!luma || !horizontal) { free(luma); free(horizontal); return -2; }
    for (size_t i = 0; i < count; ++i)
        luma[i] = (uint16_t)(((uint32_t)in[3*i]*299 +
                    (uint32_t)in[3*i+1]*587 + (uint32_t)in[3*i+2]*114) / 1000);
    uint32_t sum = 0; for (int k = 0; k < taps; ++k) sum += weights[k];
    int r = taps / 2;
    for (size_t y = 0; y < h; ++y) for (size_t x = 0; x < w; ++x) {
        uint32_t v = 0;
        for (int k = 0; k < taps; ++k) v += weights[k] * luma[y*w + edge(x, k-r, w)];
        horizontal[y*w+x] = (uint16_t)(v / sum);
    }
    for (size_t y = 0; y < h; ++y) for (size_t x = 0; x < w; ++x) {
        uint32_t v = 0;
        for (int k = 0; k < taps; ++k) v += weights[k] * horizontal[edge(y, k-r, h)*w+x];
        int original = luma[y*w+x], difference = original - (int)(v / sum);
        int magnitude = difference < 0 ? -difference : difference;
        /* Preserve the original 32-bit product wrap at extreme strengths. */
        int64_t product = (int64_t)difference * at[original] * nt[magnitude];
        uint32_t bits = (uint32_t)product;
        int32_t signed_product = bits <= INT32_MAX ? (int32_t)bits
            : (int32_t)((int64_t)bits - INT64_C(4294967296));
        int delta = signed_product / 25500;
        for (size_t c = 0; c < 3; ++c) {
            int value = (int)in[3*(y*w+x)+c] + delta;
            out[3*(y*w+x)+c] = (uint16_t)(value < 0 ? 0 : value > 16383 ? 16383 : value);
        }
    }
    free(luma); free(horizontal); return 0;
}
