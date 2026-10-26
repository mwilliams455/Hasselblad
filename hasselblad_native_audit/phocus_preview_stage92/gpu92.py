"""Mesa EGL shader execution; camera texture bytes use an explicit 2D test adapter.

The real external-OES shader is also compiled and linked. This does not simulate
Android SurfaceTexture, its lifecycle, or a phone's HAL colour processing.
"""
import ctypes as C,json,os,subprocess
from pathlib import Path
import numpy as np

def check_gpu(assets,work):
    os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE','1')
    egl=C.CDLL('libEGL.so.1');P=C.c_void_p;I=C.c_int;U=C.c_uint;F=C.c_float
    def efn(n,ret,args):
        f=getattr(egl,n);f.restype=ret;f.argtypes=args;return f
    proc=efn('eglGetProcAddress',P,[C.c_char_p])
    platform=C.CFUNCTYPE(P,U,P,C.POINTER(I))(proc(b'eglGetPlatformDisplayEXT'))
    display=platform(0x31DD,None,None);major=I();minor=I()
    assert efn('eglInitialize',U,[P,C.POINTER(I),C.POINTER(I)])(display,C.byref(major),C.byref(minor))
    assert efn('eglBindAPI',U,[U])(0x30A0)
    attrs=(I*15)(0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,0,0x3038)
    config=P();count=I()
    assert efn('eglChooseConfig',U,[P,C.POINTER(I),C.POINTER(P),I,C.POINTER(I)])(display,attrs,C.byref(config),1,C.byref(count)) and count.value
    context=efn('eglCreateContext',P,[P,P,P,C.POINTER(I)])(display,config,None,(I*3)(0x3098,3,0x3038));assert context
    width,height=128,64
    surface=efn('eglCreatePbufferSurface',P,[P,P,C.POINTER(I)])(display,config,(I*5)(0x3057,width,0x3056,height,0x3038));assert surface
    assert efn('eglMakeCurrent',U,[P,P,P,P])(display,surface,surface,context)
    def gl(n,ret,args):
        address=proc(n.encode());assert address,n
        return C.CFUNCTYPE(ret,*args)(address)
    getString=gl('glGetString',C.c_char_p,[U]);renderer=getString(0x1F01).decode();version=getString(0x1F02).decode()
    shader=gl('glCreateShader',U,[U]);source=gl('glShaderSource',None,[U,I,C.POINTER(C.c_char_p),P]);compile_=gl('glCompileShader',None,[U])
    shaderiv=gl('glGetShaderiv',None,[U,U,C.POINTER(I)]);slog=gl('glGetShaderInfoLog',None,[U,I,P,P])
    create=gl('glCreateProgram',U,[]);attach=gl('glAttachShader',None,[U,U]);link=gl('glLinkProgram',None,[U]);piv=gl('glGetProgramiv',None,[U,U,C.POINTER(I)]);plog=gl('glGetProgramInfoLog',None,[U,I,P,P])
    def program(vertex,fragment):
        p=create()
        for kind,text in ((0x8B31,vertex),(0x8B30,fragment)):
            s=shader(kind);encoded=C.c_char_p(('#version 300 es\n'+text).encode());source(s,1,C.byref(encoded),None);compile_(s)
            ok=I();shaderiv(s,0x8B81,C.byref(ok));message=C.create_string_buffer(8192);slog(s,8192,None,message)
            assert ok.value,message.value.decode();attach(p,s)
            gl('glDeleteShader',None,[U])(s)
        link(p);ok=I();piv(p,0x8B82,C.byref(ok));message=C.create_string_buffer(8192);plog(p,8192,None,message)
        assert ok.value,message.value.decode();return p
    tone=(assets/'colour92.glsl').read_text();stub='vec3 hb89Tone(vec3 c){return c;}'
    vertex=(assets/'main_vs.glsl').read_text();quad=(assets/'quad_vs.glsl').read_text()
    sharp=(assets/'main_fs.glsl').read_text();blur=(assets/'blur_oes_fs.glsl').read_text()
    programs=[]
    # Compile/link the production OES variants and their plain-feed fallback.
    for v,f in ((vertex,sharp),(quad,blur)):
        for common in (tone,stub):programs.append(program(v,f.replace('// HB89_TONE',common)))
    def adapter(f):return '\n'.join(l for l in f.splitlines() if not l.startswith('#extension')).replace('samplerExternalOES','sampler2D')
    p=program(vertex,adapter(sharp.replace('// HB89_TONE',tone)));programs.append(p)
    old=subprocess.check_output(['git','show','31189f98e9df99fac2988b42ecdcdb91811d2e92:HasselbladPhoton/app/src/main/assets/shaders/preview/main_fs.glsl'],text=True)
    original=program(vertex,adapter(old));programs.append(original)
    pb=program(quad,adapter(blur.replace('// HB89_TONE',tone)));programs.append(pb)
    oldblur=subprocess.check_output(['git','show','31189f98e9df99fac2988b42ecdcdb91811d2e92:HasselbladPhoton/app/src/main/assets/shaders/preview/blur_oes_fs.glsl'],text=True)
    originalblur=program(quad,adapter(oldblur));programs.append(originalblur)
    use=gl('glUseProgram',None,[U]);loc=gl('glGetUniformLocation',I,[U,C.c_char_p])
    u1i=gl('glUniform1i',None,[I,I]);u1f=gl('glUniform1f',None,[I,F]);u2f=gl('glUniform2f',None,[I,F,F]);mat=gl('glUniformMatrix4fv',None,[I,I,U,P])
    gen=gl('glGenTextures',None,[I,C.POINTER(U)]);bind=gl('glBindTexture',None,[U,U]);active=gl('glActiveTexture',None,[U]);param=gl('glTexParameteri',None,[U,U,I]);tex=gl('glTexImage2D',None,[U,I,I,I,I,I,U,U,P])
    names=(U*2)();gen(2,names)
    rng=np.random.default_rng(89);pixels=rng.integers(0,256,(height,width,4),dtype=np.uint8);pixels[:,:,3]=255
    pixels[0,:,:3]=np.arange(width,dtype=np.uint8)[:,None]*2
    pixels[1,:8,:3]=np.array([[0,0,0],[255,255,255],[255,0,0],[0,255,0],[0,0,255],[255,255,0],[0,255,255],[255,0,255]])
    def upload(unit,name,data,w,h):
        active(0x84C0+unit);bind(0x0DE1,name)
        for key,value in ((0x2801,0x2600),(0x2800,0x2600),(0x2802,0x812F),(0x2803,0x812F)):param(0x0DE1,key,value)
        tex(0x0DE1,0,0x1908,w,h,0,0x1908,0x1401,data.ctypes.data)
    upload(0,names[0],pixels,width,height)
    bnames=(U*2)();gl('glGenBuffers',None,[I,C.POINTER(U)])(2,bnames)
    bindbuf=gl('glBindBuffer',None,[U,U]);bufferdata=gl('glBufferData',None,[U,C.c_size_t,P,U]);attrib=gl('glGetAttribLocation',I,[U,C.c_char_p]);enable=gl('glEnableVertexAttribArray',None,[U]);pointer=gl('glVertexAttribPointer',None,[U,I,U,U,I,P])
    for name,arr in zip(bnames,([1,-1,-1,-1,1,1,-1,1],[1,1,0,1,1,0,0,0])):
        values=np.array(arr,np.float32);bindbuf(0x8892,name);bufferdata(0x8892,values.nbytes,values.ctypes.data,0x88E4)
    gl('glViewport',None,[I,I,I,I])(0,0,width,height);gl('glDisable',None,[U])(0x0BD0) # dither off for numerical checks
    read=gl('glReadPixels',None,[I,I,I,I,U,U,P]);draw=gl('glDrawArrays',None,[U,I,I]);error=gl('glGetError',U,[])
    def render(prog,on,mirror=0,peak=0,angle=0,blur_pass=False):
        use(prog)
        for n,val in [('sTexture',0),('uColour92',1),('uColour92Enabled',on),('mirror',mirror),('enablePeak',peak)]:u1i(loc(prog,n.encode()),val)
        for n,val in [('uCornerRadius',0),('uCos',1),('uSin',0)]:u1f(loc(prog,n.encode()),val)
        for n,vals in [('resolution',(width,height)),('uSharpOrigin',(0,0)),('uSharpSize',(width,height)),('uViewSize',(width,height)),('uFboSize',(width,height)),('uOffsetPx',(2,0))]:u2f(loc(prog,n.encode()),*vals)
        c,s=np.cos(angle),np.sin(angle);m=np.array([[c,s,0,0],[-s,c,0,0],[0,0,1,0],[0,0,0,1]],np.float32);mat(loc(prog,b'uTexRotateMatrix'),1,0,m.ctypes.data)
        for n,name in zip((b'vPosition',b'vTexCoord'),bnames):
            a=attrib(prog,n)
            if a>=0:bindbuf(0x8892,name);enable(a);pointer(a,2,0x1406,0,0,None)
        active(0x84C0);bind(0x0DE1,names[0]);draw(5,0,4)
        out=np.empty_like(pixels);read(0,0,width,height,0x1908,0x1401,out.ctypes.data);assert error()==0
        return out
    def cpu(rgb,table):
        p=rgb/255.*32;lo=np.floor(p).astype(int);hi=np.minimum(lo+1,32);weight=p-lo
        out=np.zeros_like(p)
        for dr in (0,1):
            for dg in (0,1):
                for db in (0,1):
                    r=hi[...,0] if dr else lo[...,0];g=hi[...,1] if dg else lo[...,1];b=hi[...,2] if db else lo[...,2]
                    w=(weight[...,0] if dr else 1-weight[...,0])*(weight[...,1] if dg else 1-weight[...,1])*(weight[...,2] if db else 1-weight[...,2])
                    out+=table[g,b*33+r,:3]*w[...,None]
        return np.clip(np.floor(out+.5),0,255).astype(np.uint8)
    off_pixels=0;on_pixels=0;worst=0
    tables=sorted(work.glob('cube-*.rgba'))
    identity=np.empty((33,1089,4),np.uint8)
    for g in range(33):
        for b in range(33):
            for r in range(33):identity[g,b*33+r]=[round(r*255/32),round(g*255/32),round(b*255/32),255]
    for index,table in enumerate([identity]+[np.frombuffer(t.read_bytes(),np.uint8).reshape(33,1089,4) for t in tables]):
        upload(1,names[1],table,1089,33)
        for mirror in (0,1):
            for peak in (0,1):
                for angle in (0,np.pi/2):
                    off=render(p,0,mirror,peak,angle);expected=render(original,0,mirror,peak,angle)
                    assert np.array_equal(off,expected),'disabled sharp differs';off_pixels+=width*height
            offblur=render(pb,0,mirror);expected=render(originalblur,0,mirror)
            assert np.array_equal(offblur,expected),'disabled blur differs';off_pixels+=width*height
            onblur=render(pb,1,mirror);assert onblur[:,:,3].min()==255
            mapped=pixels.copy();mapped[:,:,:3]=cpu(pixels[:,:,:3],table);upload(0,names[0],mapped,width,height)
            expectedblur=render(originalblur,0,mirror);upload(0,names[0],pixels,width,height)
            assert np.max(np.abs(onblur.astype(int)-expectedblur.astype(int)))<=2,'blur uses same cube before filtering'
            off=render(p,0,mirror);on=render(p,1,mirror);expected=cpu(off[:,:,:3],table)
            diff=np.abs(on[:,:,:3].astype(int)-expected.astype(int));d=int(diff.max());worst=max(worst,d)
            assert d<=1,('CPU/GPU difference',d,index);assert on[:,:,3].min()==255;on_pixels+=width*height
            if index==0:assert np.max(np.abs(on.astype(int)-off.astype(int)))<=1,'identity table'

    # Isolate production cube interpolation from the existing mediump preview caller.
    # A deliberately discontinuous public table stresses fractional arithmetic.
    probe=program(vertex,'precision highp float; uniform highp sampler2D sTexture; in vec2 texCoord; out vec4 Output;\n'+tone+'\nvoid main(){Output=vec4(hb89Tone(texture(sTexture,texCoord).rgb),1.0);}')
    programs.append(probe)
    steep=np.random.default_rng(9201).integers(0,256,(33,1089,4),dtype=np.uint8);steep[:,:,3]=255
    upload(1,names[1],steep,1089,33)
    off=render(probe,0);on=render(probe,1);probe_error=int(np.max(np.abs(on[:,:,:3].astype(int)-cpu(off[:,:,:3],steep).astype(int))))
    assert probe_error<=1,('steep cube highp interpolation',probe_error)
    for p in programs:gl('glDeleteProgram',None,[U])(p)
    efn('eglMakeCurrent',U,[P,P,P,P])(display,None,None,None)
    efn('eglDestroySurface',U,[P,P])(display,surface);efn('eglDestroyContext',U,[P,P])(display,context);efn('eglTerminate',U,[P])(display)
    return {'renderer':renderer,'gl_version':version,'production_oes_and_fallback_programs_linked':4,'off_pixels_exact':off_pixels,'on_pixels_compared':on_pixels,'max_rgb8_difference_from_cpu':worst,'steep_table_interpolation_probe_pixels':width*height,'steep_table_interpolation_probe_max_error':probe_error,'blur_vs_cpu_before_filter_max_tolerance':2,'texture_adapter':'2D fixture; external-OES production shader separately compiled','android_surface_lifecycle_tested':False}
