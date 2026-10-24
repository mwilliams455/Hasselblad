"""Independent numerical reconstruction of the bounded SDR highlight stage.

Inputs are gain ratios and per-channel 16-bit sensor clipping levels. This is
research code: no camera calibration or vendor shader is embedded here.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class Highlight:
    order: np.ndarray
    undo: np.ndarray
    limits: np.ndarray
    weights: np.ndarray
    middle: np.ndarray
    full: np.ndarray
    projection: np.ndarray
    red_projection: np.ndarray
    scale: np.ndarray | None = None

    @classmethod
    def from_float32_uniforms(cls, values):
        """Evaluate the independent equations at the shader's precision.

        Uniform construction is audited separately against prepare().
        Exact clipping boundaries require float32 multiplication here.
        """
        names = ('uBoLevel', 'uNeutral', 'uMidGrayScales', 'uFullScales',
                 'uRatioGreenBlue', 'uRatioRed', 'uBoScale')
        return cls(np.asarray(values['uOrder'], dtype=int),
                   np.asarray(values['uOrderBack'], dtype=int),
                   *[np.asarray(values[n], dtype=np.float32) for n in names])

    @classmethod
    def prepare(cls, gains, truncation=(65535, 65535, 65535)):
        gains = np.asarray(gains, dtype=float)
        levels = np.asarray(truncation, dtype=float) / 65535
        if (gains.shape != (3,) or levels.shape != (3,) or
                not np.isfinite(gains).all() or not np.isfinite(levels).all()):
            raise ValueError('Three finite gains and clipping levels are required')
        if np.any(gains <= 0) or np.any(levels <= 0) or np.any(levels > 1):
            raise ValueError('Gains and sensor clipping levels must be positive')
        if gains.max() <= 1e-9 or np.any(np.asarray(truncation) != np.floor(truncation)):
            raise ValueError('Tiny absolute gains and fractional clipping codes are outside the audited domain')
        gains = gains / gains.max()
        order = np.array(sorted(range(3), key=lambda i: (gains[i], i), reverse=True))
        undo = np.argsort(order)
        limits, weights = levels[order], gains[order]
        # The native construction is singular at equal lower gains. Reject
        # that input explicitly; the audit characterizes original behaviour.
        if weights[1] == weights[2]:
            raise ValueError('Equal lower gains require a separately validated limit')
        anchor = np.minimum(levels, levels * (weights[1]/gains))[order] / limits
        a, b, c = weights
        slope = (1-c/b)/(1-c)
        intercept = c/b-slope*c
        inv = 1/slope
        def project(x, yy): return (inv*x+yy-intercept)/(slope+inv)
        baseline = project(c, c/b)
        lower = max((1-inv+inv*c+c/b)*.5, .0001)
        middle = np.array([(1-inv+inv*anchor[0]+anchor[1])*.5/lower,
                           project(anchor[0], anchor[2])/baseline,
                           project(anchor[0], anchor[1])/baseline])
        full = np.array([1/lower, project(1, 1)/baseline, project(1, 1)/baseline])
        return cls(order, undo, limits, weights, middle, full,
                   np.array([slope, intercept, baseline]), np.array([1., 0., lower]))

    def parameters(self):
        """Parameter names are the native public-facing uniform interface."""
        return {'uOrder': self.order, 'uOrderBack': self.undo,
                'uBoScale': 1/self.limits, 'uBoLevel': self.limits,
                'uNeutral': self.weights, 'uMidGrayScales': self.middle,
                'uFullScales': self.full, 'uRatioGreenBlue': self.projection,
                'uRatioRed': self.red_projection}

    def boundary(self, values):
        values = np.asarray(values, dtype=self.weights.dtype)
        result = values*self.weights
        for channel, pair, projection in ((0, (1, 2), self.red_projection),
                                          (1, (0, 2), self.projection),
                                          (2, (0, 1), self.projection)):
            mask = values[:, channel] >= 1
            for later in range(channel+1, 3): mask &= values[:, later] < 1
            if not np.any(mask): continue
            v = values[mask]
            slope, offset, divisor = projection
            position = ((v[:, pair[0]]/slope+v[:, pair[1]]-offset)/(slope+1/slope))/divisor
            position = np.maximum(position, 1)
            mid, full = self.middle[channel], self.full[channel]
            center = self.weights[1]/self.weights[2]
            high = position > mid
            # Evaluate only the selected branch. Equal upper gains make the
            # unused high-segment denominator zero.
            first = np.divide(position-1, mid-1, out=np.zeros_like(position), where=~high)
            second = np.divide(position-mid, full-mid, out=np.zeros_like(position), where=high)
            gain_c = np.where(high, center+(1/self.weights[2]-center)*second,
                              1+(center-1)*first)
            gain_b = np.where(high, 1+(1/self.weights[1]-1)*second, 1)
            result[mask] = v*self.weights*np.column_stack([np.ones(len(v), dtype=v.dtype), gain_b, gain_c])
        return result

    def convert(self, pixels, gpu_dark_threshold=False):
        pixels = np.asarray(pixels, dtype=self.weights.dtype)
        shape = pixels.shape
        if shape[-1] != 3 or not np.isfinite(pixels).all() or np.any(pixels < 0):
            raise ValueError('Finite nonnegative sensor RGB is required')
        # Preserve reciprocal multiplication at the clipping boundary: a
        # mathematically equivalent division can select a different branch.
        scale = 1/self.limits if self.scale is None else self.scale
        v = np.minimum(pixels.reshape(-1, 3)[:, self.order]*scale, 1)
        result = self.boundary(v)
        mask = np.all(v < 1, axis=1)
        if np.any(mask):
            interior = v[mask]
            strength = interior**8
            total = strength.sum(axis=1, keepdims=True)
            weights = np.divide(strength, total, out=np.zeros_like(strength),
                                where=total > (1e-6 if gpu_dark_threshold else 0))
            correction = np.zeros_like(interior)
            for ch in range(3):
                edge = interior.copy(); edge[:, ch] = 1
                correction += (self.boundary(edge)-edge*self.weights)*weights[:, ch:ch+1]
            result[mask] = interior*self.weights+correction
        result = np.minimum(result/scale, self.limits)[:, self.undo]
        return result.reshape(shape)


def equal_lower_limit(pixels, gains, truncation=(65535, 65535, 65535)):
    """Analytic continuation where the two smaller gain ratios coincide.

    This is a separately labelled mathematical extension, not replication of
    native NaN handling. It includes the unity-gain identity case.
    """
    gains = np.asarray(gains, dtype=float)
    levels = np.asarray(truncation, dtype=float)/65535
    pixels = np.asarray(pixels, dtype=float)
    assert gains.shape == levels.shape == (3,) and pixels.shape[-1] == 3
    assert np.isfinite(gains).all() and np.all(gains > 0)
    assert np.isfinite(levels).all() and np.all((levels > 0) & (levels <= 1))
    assert np.isfinite(pixels).all() and np.all(pixels >= 0)
    order = np.array(sorted(range(3), key=lambda i: (gains[i], i), reverse=True))
    ratios = gains[order]/gains.max()
    assert ratios[1] == ratios[2]
    t = ratios[1]
    scale = 1/levels[order]
    v = np.minimum(pixels.reshape(-1, 3)[:, order]*scale, 1)
    result = v*np.column_stack([np.ones(len(v)), *([np.maximum(t, v[:, 0])]*2)])
    inside = np.all(v < 1, axis=1)
    u = v[inside]
    strength = u**8
    weight = np.divide(strength, strength.sum(axis=1, keepdims=True),
                       out=np.zeros_like(strength), where=strength.sum(axis=1, keepdims=True) > 0)
    extra = np.maximum(u[:, 0]-t, 0)
    result[inside, 0] = u[:, 0]
    result[inside, 1] = u[:, 1]*t + weight[:, 0]*u[:, 1]*(1-t) + weight[:, 1]*extra + weight[:, 2]*u[:, 1]*extra
    result[inside, 2] = u[:, 2]*t + weight[:, 0]*u[:, 2]*(1-t) + weight[:, 1]*u[:, 2]*extra + weight[:, 2]*extra
    return np.minimum(result/scale, levels[order])[:, np.argsort(order)].reshape(pixels.shape)


def factor_dng_white_balance(camera_to_d50, as_shot_neutral):
    """Factor existing WB for a sensor-domain reconstruction experiment.

    Applying returned matrix to raw * (gains / max(gains)) reproduces applying
    the original matrix to raw. This algebra alone does not establish physical
    cross-camera colour equivalence or a correct sensor clipping model.
    """
    matrix = np.asarray(camera_to_d50, dtype=float)
    neutral = np.asarray(as_shot_neutral, dtype=float)
    if (matrix.shape != (3, 3) or neutral.shape != (3,) or
            not np.isfinite(matrix).all() or not np.isfinite(neutral).all() or np.any(neutral <= 0)):
        raise ValueError('A finite 3x3 transform and positive neutral are required')
    gains = 1/neutral
    return gains, matrix @ np.diag(gains.max()/gains)
