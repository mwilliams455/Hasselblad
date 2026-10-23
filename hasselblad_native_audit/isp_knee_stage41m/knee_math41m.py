#!/usr/bin/env python3
"""Reconstructed table-preparation arithmetic, not an RGB pixel renderer.

Original librcam instructions are independently exercised by replay_knee41m.py.
No firmware bytes, tuning tables or camera-specific parameters are embedded.
"""
import numpy as np


def signed32(value):
    value=int(value)&0xffffffff
    return value-(1<<32) if value&(1<<31) else value


def sdiv32(numerator,denominator):
    """AArch64 signed 32-bit division, including zero and overflow behavior."""
    n,d=signed32(numerator),signed32(denominator)
    if d==0:return 0
    q=abs(n)//abs(d)
    return signed32(-q if (n<0)!=(d<0) else q)


def knee_slopes(values,keypoints):
    """Prepare Q12 slopes with the original 32-bit operation order.

    Contract: equally sized arrays with >=2 entries. Equal keypoints reproduce
    SDIV-by-zero behavior; they are not endorsed as valid camera tuning.
    The final slope entry is zero. No per-pixel interpolation is claimed.
    """
    if len(values)!=len(keypoints) or len(values)<2:
        raise ValueError('need equally sized arrays with at least two entries')
    result=[]
    for i in range(len(values)-1):
        numerator=signed32(signed32(int(values[i+1])-int(values[i]))<<12)
        denominator=signed32(int(keypoints[i+1])-int(keypoints[i]))
        result.append(sdiv32(numerator,denominator))
    return result+[0]


def fusion_table(source,knee_map,context_gain):
    """Reproduce the bounded, synthetic domain of the 257-entry fusion helper.

    The original helper's lookup of knee_map is external to this arithmetic.
    Context gain units/ownership and use in the four camera captures remain
    unproven. Keep each multiply/add separately rounded to IEEE float32.
    """
    if len(source)!=257 or len(knee_map)!=257:
        raise ValueError('fusion requires 257 entries')
    if not 0<=int(context_gain)<=4096 or any(not 0<=int(k)<=65535 for k in knee_map):
        raise ValueError('outside the independently replayed gain/map domain')
    if any(not -65535<=int(v)<=65535 for v in source):
        raise ValueError('outside the independently replayed source domain')
    f=np.float32;g=f(int(context_gain));out=[]
    for k in knee_map:
        position=f(f(f(g*f(int(k)))*f(.25))*f(1/256))
        index=int(position);lo=min(index,256);hi=min(index+1,256)
        difference=signed32(int(source[hi])-int(source[lo]))
        fraction=f(position-f(lo))
        value=f(f(fraction*f(difference))+f(int(source[lo])))
        # FCVTZU truncates toward zero and saturates at the unsigned bounds.
        out.append(min(0xffffffff,max(0,int(value))))
    return out
