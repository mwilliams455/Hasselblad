"""Build independent green estimation; no original executable dependency."""
import ctypes as C
from pathlib import Path
import subprocess


class PortableGreen:
    def __init__(self, work, compiler='gcc', sanitize=False, unfused_negative_control=False):
        work=Path(work); work.mkdir(parents=True,exist_ok=True)
        self.path=work/'libgreen63.so'
        flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-fno-fast-math',
               '-ffp-contract=off','-fPIC','-shared']
        if sanitize: flags+=['-fsanitize=undefined','-fno-sanitize-recover=all']
        source=Path(__file__).with_name('green63.c')
        if unfused_negative_control:
            # Deliberately wrong arithmetic, generated only for a synthetic
            # discrimination test. The default library always uses fmaf.
            text=source.read_text().replace('fmaf(', 'unfused63(')
            text='static float unfused63(float a,float b,float c) { volatile float p=a*b; return p+c; }\n'+text
            source=work/'unfused_negative_control.c'; source.write_text(text)
            flags+=['-I',str(Path(__file__).parent)]
        self.command=[compiler,*flags,str(source),'-lm','-o',str(self.path)]
        subprocess.run(self.command,check=True,capture_output=True)
        self.lib=C.CDLL(str(self.path))
        self.lib.hb_green_at_colour63.argtypes=[C.c_void_p]*4+[C.c_int]+[C.c_void_p]*2+[C.c_int16]*2+[C.c_void_p]*3
        self.lib.hb_green_at_colour63.restype=None
