"""Recovered MAIN gamma knot construction; this does not sample image pixels.

The original MAIN-linked consumer is librcam tmc_v1_0_calc_tmc, firmware
1.3.16.2, instruction interval [0x3866b0, 0x386d28). Its seven division
registers specify log2 interval counts, across the fixed regions below.
Only the 257-knot contract is exposed. Hardware interpolation, output
quantization and dithering are intentionally outside this primitive.
"""

REGION_BOUNDARIES = (0, 1024, 2048, 4096, 8192, 16384, 32768, 65536)


def main_gamma_knots(divisions):
    """Return 257 integer input coordinates after validating bounded counts."""
    if not isinstance(divisions, (tuple, list)) or len(divisions) != 7:
        raise ValueError("Expected exactly seven division integers")
    if any(type(value) is not int or not 0 <= value <= 7 for value in divisions):
        raise ValueError("Division integers must lie in the proved range 0..7")
    counts = tuple(1 << value for value in divisions)
    if sum(counts) != 256:
        raise ValueError("The MAIN table requires exactly 256 intervals")
    knots = [0]
    for index, (division, count) in enumerate(zip(divisions, counts)):
        lower, upper = REGION_BOUNDARIES[index:index + 2]
        step = ((upper - lower) + count // 2) >> division
        knots.extend(lower + step * number for number in range(1, count))
        knots.append(upper)
    return tuple(knots)
