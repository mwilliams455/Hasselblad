"""Independent integer RGGB interpolation and RGB-to-Bayer selection.

No private code, calibration or photographed values are embedded here.
The native step-one, ordinary (non-green-blending) branch is the target.
Image-edge extension remains an explicit fixture, separate from these stencils.
"""
import numpy as np


def fast_bayer(mosaic, halo=4):
    m = np.asarray(mosaic)
    if m.ndim != 2 or m.dtype != np.uint16 or halo < 1 or halo % 2:
        raise ValueError('uint16 RGGB mosaic and positive even halo required')
    h, w = m.shape[0]-2*halo, m.shape[1]-2*halo
    if min(h, w) < 1:
        raise ValueError('Interior must be nonempty')
    # Work in integer code units; the original averages truncate down.
    m = m.astype(np.uint32)
    get = lambda dy, dx: m[halo+dy:halo+dy+h, halo+dx:halo+dx+w]
    center = get(0, 0)
    horizontal = (get(0, -1)+get(0, 1))//2
    vertical = (get(-1, 0)+get(1, 0))//2
    cross = (get(-1, 0)+get(1, 0)+get(0, -1)+get(0, 1))//4
    diagonal = (get(-1, -1)+get(-1, 1)+get(1, -1)+get(1, 1))//4
    out = np.empty((h, w, 3), dtype=np.uint16)
    for ys, xs, planes in (
        (0, 0, (center, cross, diagonal)),
        (0, 1, (horizontal, center, vertical)),
        (1, 0, (vertical, center, horizontal)),
        (1, 1, (diagonal, cross, center))):
        for ch, plane in enumerate(planes):
            out[ys::2, xs::2, ch] = plane[ys::2, xs::2]
    return out


def extract_bayer(rgb, phase=(0, 0)):
    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint16:
        raise ValueError('uint16 RGB image required')
    px, py = phase
    if px not in (0, 1) or py not in (0, 1):
        raise ValueError('CFA phase must contain zero or one')
    h, w = rgb.shape[:2]
    yy, xx = np.indices((h, w))
    # Channel sequence at RGGB sites is 0,1,1,2; shift by the red phase.
    channel = (((yy+py) & 1)*2 + ((xx+px) & 1) + 1)//2
    return np.take_along_axis(rgb, channel[..., None], axis=2)[..., 0]


def pad_bayer(mosaic, halo=4):
    """Reflect-101 fixture; does not claim the original outer-frame edge policy."""
    return np.pad(mosaic, halo, mode='reflect')
