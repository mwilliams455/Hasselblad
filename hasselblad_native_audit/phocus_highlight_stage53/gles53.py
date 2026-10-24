"""Typed vector uniforms for original private highlight shader execution.

RGBA16F matches the selected native texture format. RGBA32F is diagnostic only.
"""
import ctypes as C
import numpy as np
from gles50 import GLES, I, U, P


class HighlightGLES(GLES):
    def __init__(self):
        super().__init__()
        for n in ('glUniform2fv', 'glUniform3fv', 'glUniform2iv', 'glUniform3iv'):
            address = self.e.eglGetProcAddress(n.encode()); assert address
            setattr(self, n, C.CFUNCTYPE(None, I, I, P)(address))

    def render(self, fragment, pixels, uniforms, storage=0x881a):
        rgb = np.ascontiguousarray(pixels, dtype=np.float32)
        if rgb.ndim == 2: rgb = rgb[None, ...]
        height, width, channels = rgb.shape
        assert channels == 3
        rgba = np.concatenate([rgb, np.ones((height, width, 1), np.float32)], axis=-1)
        vertex = '''#version 300 es
        precision highp float;
        out vec2 TexCoord;
        void main() {
          vec2 p = vec2(gl_VertexID == 1 ? 3.0 : -1.0, gl_VertexID == 2 ? 3.0 : -1.0);
          TexCoord = p * 0.5 + 0.5;
          gl_Position = vec4(p, 0.0, 1.0);
        }'''
        shaders = [self.shader(0x8b31, vertex), self.shader(0x8b30, fragment)]
        program = self.glCreateProgram()
        for shader in shaders: self.glAttachShader(program, shader)
        self.glLinkProgram(program); status = I(); self.glGetProgramiv(program, 0x8b82, C.byref(status))
        if not status.value:
            log = C.create_string_buffer(4096); self.glGetProgramInfoLog(program, 4096, None, log)
            raise RuntimeError(log.value.decode())
        self.glUseProgram(program)
        for name, value in {'uInputTexture0': 0, **uniforms}.items():
            location = self.glGetUniformLocation(program, name.encode())
            if location < 0: continue  # Unused declarations may be optimized out.
            if isinstance(value, (int, np.integer)): self.glUniform1i(location, int(value))
            elif np.ndim(value) == 0: self.glUniform1f(location, float(value))
            elif np.shape(value) == (3, 3):
                matrix = np.ascontiguousarray(np.asarray(value, np.float32).T)
                self.glUniformMatrix3fv(location, 1, 0, matrix.ctypes.data)
            elif len(value) in (2, 3):
                integer = np.issubdtype(np.asarray(value).dtype, np.integer)
                array = np.ascontiguousarray(value, dtype=np.int32 if integer else np.float32)
                fn = getattr(self, 'glUniform'+str(len(value))+('iv' if integer else 'fv'))
                fn(location, 1, array.ctypes.data)
            else: raise ValueError(name)
        textures = (U * 2)(); self.glGenTextures(2, textures)
        for index, texture in enumerate(textures):
            self.glBindTexture(0x0de1, texture)
            for key in (0x2801, 0x2800): self.glTexParameteri(0x0de1, key, 0x2600)
            for key in (0x2802, 0x2803): self.glTexParameteri(0x0de1, key, 0x812f)
            self.glTexImage2D(0x0de1, 0, storage, width, height, 0, 0x1908, 0x1406,
                              rgba.ctypes.data if index == 0 else None)
        fbo = U(); self.glGenFramebuffers(1, C.byref(fbo)); self.glBindFramebuffer(0x8d40, fbo)
        self.glFramebufferTexture2D(0x8d40, 0x8ce0, 0x0de1, textures[1], 0)
        assert self.glCheckFramebufferStatus(0x8d40) == 0x8cd5
        # Read the actual stored input; driver float-to-half conversion need
        # not use NumPy's rounding mode. Compare arithmetic on identical data.
        self.glFramebufferTexture2D(0x8d40, 0x8ce0, 0x0de1, textures[0], 0)
        stored = np.empty_like(rgba)
        self.glReadPixels(0, 0, width, height, 0x1908, 0x1406, stored.ctypes.data)
        self.last_stored_input = stored[..., :3].reshape(pixels.shape).copy()
        self.glFramebufferTexture2D(0x8d40, 0x8ce0, 0x0de1, textures[1], 0)
        vao = U(); self.glGenVertexArrays(1, C.byref(vao)); self.glBindVertexArray(vao)
        self.glActiveTexture(0x84c0); self.glBindTexture(0x0de1, textures[0])
        self.glViewport(0, 0, width, height); self.glDrawArrays(4, 0, 3); self.glFinish()
        output = np.empty_like(rgba)
        self.glReadPixels(0, 0, width, height, 0x1908, 0x1406, output.ctypes.data)
        assert self.glGetError() == 0
        assert np.array_equal(output[..., 3], np.ones((height, width)))
        self.glDeleteVertexArrays(1, C.byref(vao)); self.glDeleteFramebuffers(1, C.byref(fbo))
        self.glDeleteTextures(2, textures); self.glDeleteProgram(program)
        for shader in shaders: self.glDeleteShader(shader)
        return output[..., :3].reshape(pixels.shape)
