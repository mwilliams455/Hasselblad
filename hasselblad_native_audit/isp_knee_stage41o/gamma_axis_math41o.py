#!/usr/bin/env python3
"""Reconstructed integer axis interpolation; this is not a pixel renderer.

No vendor tuning or capture values are embedded. Synthetic original-code
replay in replay_gamma_axis41o.py checks the arithmetic independently.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'isp_knee_stage41m'))
from knee_math41m import signed32,sdiv32


def axis_coefficient(axis,value):
    """Return (lower bank index, Q8 weight) for a nondecreasing signed axis.

    The original helper returns (0,0) for zero/one entries, but a zero-bank
    axis is not valid input to the complete table preparation pipeline.
    Signed 32-bit subtraction and shift overflow are deliberately preserved.
    """
    a=[signed32(v) for v in axis];x=signed32(value)
    if any(b<c for c,b in zip(a,a[1:])):
        raise ValueError('axis must be nondecreasing as signed 32-bit values')
    if len(a)<2 or x<a[0]:return 0,0
    if x>=a[-1]:return len(a)-2,256
    i=next(i for i in range(len(a)-1) if a[i]<=x<a[i+1])
    return i,sdiv32(signed32((x-a[i])<<8),signed32(a[i+1]-a[i]))


def lerp_word(lower,upper,weight):
    """32-bit multiply, arithmetic shift by eight, then wrapped addition.

    A negative fractional increment rounds down at the shift, not toward
    zero. Large synthetic differences can overflow even at weight 256.
    """
    a=signed32(lower)
    product=signed32(signed32(int(upper)-a)*signed32(weight))
    return signed32(a+(product>>8))


def interpolate_banks(banks,axis,value):
    """Single axis; each bank contains the same number of table entries."""
    if not banks or len(banks)!=len(axis) or not banks[0]:
        raise ValueError('one nonempty bank per axis entry is required')
    if any(len(b)!=len(banks[0]) for b in banks):
        raise ValueError('bank widths differ')
    i,q=axis_coefficient(axis,value)
    if q==0:return [signed32(v) for v in banks[i]]
    return [lerp_word(a,b,q) for a,b in zip(banks[i],banks[i+1])]
