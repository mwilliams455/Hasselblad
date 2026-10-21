"""Original Camera2 calibration -> temperature-only native descriptor.

No render-mutated/effective matrices, embedded phone values, or HAL neutral
substitution. Input provenance is checked by the existing full-frame binder.
"""
import math
import struct
from capture_binding import bind_capture, require


def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def rational32(v):
    n, d = v['numerator'], v['denominator']
    require(type(n) is int and type(d) is int and d != 0 and
            -(1 << 31) <= n < (1 << 31) and -(1 << 31) <= d < (1 << 31), 'Camera2 rational')
    value = f32(f32(n) / f32(d))  # Android Rational.floatValue conversion order
    require(math.isfinite(value), 'finite Camera2 value')
    return value


def bind_temperature(j, black_source):
    binding = bind_capture(j, black_source)
    # Current RAW grid divides each site by white-black. Identical spans make
    # that a common scalar, preserving the original Camera2 neutral basis.
    # A per-channel span correction needs its own validated mapping.
    require(len(set(binding['black_q16'])) == 1, 'unequal site normalization unvalidated')
    c = binding['original_characteristics']
    # Deliberately bounded to the two standard illuminants verified here.
    # The native model is generic; extend this metadata mapping with evidence.
    kelvin = {17: 2856, 21: 6504}
    anchors = []
    for i in (1, 2):
        code = c['android.sensor.referenceIlluminant'+str(i)]
        require(type(code) is int and code in kelvin, 'unsupported reference illuminant')
        anchors.append({'kelvin': kelvin[code],
                        'color': [rational32(v) for v in c['android.sensor.colorTransform'+str(i)]],
                        'calibration': [rational32(v) for v in c['android.sensor.calibrationTransform'+str(i)]]})
    require(anchors[0]['kelvin'] != anchors[1]['kelvin'], 'distinct illuminants required')
    return {'anchors': anchors, 'binding': binding,
            'temperature_model_available': True,
            'full_automatic_profile_available': False,
            'model_basis': 'original Camera2 calibrationTransform * colorTransform',
            'public_table_variant': 'Adobe DNG SDK 1.4, u325=0.24702',
            'white_classification_radius': None,
            'exposure_and_spatial_profile': None}
