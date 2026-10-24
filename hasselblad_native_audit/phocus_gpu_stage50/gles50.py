"""Small offscreen GLES runner for private, unchanged fragment shaders.

The software implementation tests shader arithmetic, not a phone GPU or the
Android compositor. No vendor shader source is included in this module.
"""
import ctypes as C
import os
import numpy as np

P, I, U, F = C.c_void_p, C.c_int, C.c_uint, C.c_float


class GLES:
    def __init__(self):
        os.environ['EGL_PLATFORM'] = 'surfaceless'
        os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
        e = self.e = C.CDLL('libEGL.so.1')
        for name, result, args in (
            ('eglGetDisplay', P, [P]), ('eglInitialize', U, [P, C.POINTER(I), C.POINTER(I)]),
            ('eglChooseConfig', U, [P, C.POINTER(I), C.POINTER(P), I, C.POINTER(I)]),
            ('eglBindAPI', U, [U]), ('eglCreateContext', P, [P, P, P, C.POINTER(I)]),
            ('eglMakeCurrent', U, [P, P, P, P]), ('eglGetProcAddress', P, [C.c_char_p]),
            ('eglGetError', U, []), ('eglDestroyContext', U, [P, P]), ('eglTerminate', U, [P])):
            fn = getattr(e, name); fn.restype = result; fn.argtypes = args
        self.d = e.eglGetDisplay(None); major, minor = I(), I()
        assert e.eglInitialize(self.d, C.byref(major), C.byref(minor)), hex(e.eglGetError())
        attrs = (I * 9)(0x3033, 1, 0x3040, 0x40, 0x3024, 8, 0x3023, 8, 0x3038)
        cfg, count = P(), I()
        assert e.eglChooseConfig(self.d, attrs, C.byref(cfg), 1, C.byref(count)) and count.value
        assert e.eglBindAPI(0x30a0)
        self.ctx = e.eglCreateContext(self.d, cfg, None, (I * 3)(0x3098, 3, 0x3038))
        assert self.ctx and e.eglMakeCurrent(self.d, None, None, self.ctx)
        signatures = {
            'glGetString': (C.c_char_p, [U]), 'glGetError': (U, []),
            'glCreateShader': (U, [U]), 'glShaderSource': (None, [U, I, C.POINTER(C.c_char_p), P]),
            'glCompileShader': (None, [U]), 'glGetShaderiv': (None, [U, U, C.POINTER(I)]),
            'glGetShaderInfoLog': (None, [U, I, P, P]), 'glDeleteShader': (None, [U]),
            'glCreateProgram': (U, []), 'glAttachShader': (None, [U, U]),
            'glLinkProgram': (None, [U]), 'glGetProgramiv': (None, [U, U, C.POINTER(I)]),
            'glGetProgramInfoLog': (None, [U, I, P, P]), 'glUseProgram': (None, [U]),
            'glDeleteProgram': (None, [U]), 'glGetUniformLocation': (I, [U, C.c_char_p]),
            'glUniform1i': (None, [I, I]), 'glUniform1f': (None, [I, F]),
            'glUniform2i': (None, [I, I, I]), 'glUniformMatrix3fv': (None, [I, I, U, P]),
            'glGenTextures': (None, [I, C.POINTER(U)]), 'glBindTexture': (None, [U, U]),
            'glActiveTexture': (None, [U]), 'glTexParameteri': (None, [U, U, I]),
            'glTexImage2D': (None, [U, I, I, I, I, I, U, U, P]),
            'glDeleteTextures': (None, [I, C.POINTER(U)]),
            'glGenFramebuffers': (None, [I, C.POINTER(U)]), 'glBindFramebuffer': (None, [U, U]),
            'glFramebufferTexture2D': (None, [U, U, U, U, I]), 'glCheckFramebufferStatus': (U, [U]),
            'glDeleteFramebuffers': (None, [I, C.POINTER(U)]),
            'glGenVertexArrays': (None, [I, C.POINTER(U)]), 'glBindVertexArray': (None, [U]),
            'glDeleteVertexArrays': (None, [I, C.POINTER(U)]),
            'glViewport': (None, [I, I, I, I]), 'glDrawArrays': (None, [U, I, I]),
            'glReadPixels': (None, [I, I, I, I, U, U, P]), 'glFinish': (None, [])}
        for name, (result, args) in signatures.items():
            address = e.eglGetProcAddress(name.encode()); assert address, name
            setattr(self, name, C.CFUNCTYPE(result, *args)(address))
        self.info = {'EGL': f'{major.value}.{minor.value}',
                     'GL': self.glGetString(0x1f02).decode(),
                     'renderer': self.glGetString(0x1f01).decode()}

    def shader(self, kind, source):
        shader = self.glCreateShader(kind)
        text = C.c_char_p(source.encode())
        self.glShaderSource(shader, 1, C.byref(text), None); self.glCompileShader(shader)
        status = I(); self.glGetShaderiv(shader, 0x8b81, C.byref(status))
        if not status.value:
            log = C.create_string_buffer(4096); self.glGetShaderInfoLog(shader, 4096, None, log)
            raise RuntimeError(log.value.decode())
        return shader

    def render(self, fragment, pixels, uniforms):
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
            elif len(value) == 2: self.glUniform2i(location, *map(int, value))
            else: raise ValueError(name)
        textures = (U * 2)(); self.glGenTextures(2, textures)
        for index, texture in enumerate(textures):
            self.glBindTexture(0x0de1, texture)
            for key in (0x2801, 0x2800): self.glTexParameteri(0x0de1, key, 0x2600)
            for key in (0x2802, 0x2803): self.glTexParameteri(0x0de1, key, 0x812f)
            self.glTexImage2D(0x0de1, 0, 0x881a, width, height, 0, 0x1908, 0x1406,
                              rgba.ctypes.data if index == 0 else None)
        fbo = U(); self.glGenFramebuffers(1, C.byref(fbo)); self.glBindFramebuffer(0x8d40, fbo)
        self.glFramebufferTexture2D(0x8d40, 0x8ce0, 0x0de1, textures[1], 0)
        assert self.glCheckFramebufferStatus(0x8d40) == 0x8cd5
        vao = U(); self.glGenVertexArrays(1, C.byref(vao)); self.glBindVertexArray(vao)
        self.glActiveTexture(0x84c0); self.glBindTexture(0x0de1, textures[0])
        self.glViewport(0, 0, width, height); self.glDrawArrays(4, 0, 3); self.glFinish()
        output = np.empty_like(rgba)
        self.glReadPixels(0, 0, width, height, 0x1908, 0x1406, output.ctypes.data)
        assert self.glGetError() == 0
        assert np.isfinite(output).all() and np.array_equal(output[..., 3], np.ones((height, width)))
        self.glDeleteVertexArrays(1, C.byref(vao)); self.glDeleteFramebuffers(1, C.byref(fbo))
        self.glDeleteTextures(2, textures); self.glDeleteProgram(program)
        for shader in shaders: self.glDeleteShader(shader)
        return output[..., :3].reshape(pixels.shape)

    def close(self):
        self.e.eglMakeCurrent(self.d, None, None, None)
        self.e.eglDestroyContext(self.d, self.ctx); self.e.eglTerminate(self.d)
