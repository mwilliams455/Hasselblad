"""Extra sampled textures for the independent Stage50 GLES harness."""
import ctypes as C
import numpy as np
from gles50 import GLES, U


class CurveGLES(GLES):
    def render_curves(self, fragment, pixels, uniforms, curves, linear):
        textures = (U * len(curves))()
        self.glGenTextures(len(curves), textures)
        samplers = {}
        try:
            for unit, (name, values) in enumerate(curves.items(), 1):
                rgba = np.ascontiguousarray(values, dtype=np.float32)
                assert rgba.shape == (256, 256, 4)
                self.glActiveTexture(0x84c0 + unit)
                self.glBindTexture(0x0de1, textures[unit - 1])
                for key in (0x2801, 0x2800):
                    self.glTexParameteri(0x0de1, key, 0x2601 if linear else 0x2600)
                for key in (0x2802, 0x2803): self.glTexParameteri(0x0de1, key, 0x812f)
                self.glTexImage2D(0x0de1, 0, 0x8814, 256, 256, 0, 0x1908, 0x1406, rgba.ctypes.data)
                samplers[name] = unit
            self.glActiveTexture(0x84c0)
            return self.render(fragment, pixels, {**uniforms, **samplers})
        finally:
            self.glDeleteTextures(len(curves), textures)
            self.glActiveTexture(0x84c0)
