#!/usr/bin/env python3
"""Exact cached/uncached finishing comparison and an explicitly host-only benchmark."""
import argparse,ctypes,json,os,subprocess,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'phocus_post_stage55'

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--sanitizers',action='store_true');a=p.parse_args()
    work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    sources=[str(HERE/'finish88.c'),str(OLD/'post55.c')]
    common=['gcc','-std=c11','-Wall','-Wextra','-Werror','-ffp-contract=off','-pthread','-DHB88_TESTING','-I'+str(HERE),'-I'+str(OLD)]
    lib=work/'finish88.so'
    subprocess.run(common+['-O2','-fPIC','-shared',*sources,'-lm','-o',str(lib)],check=True)
    exe=work/'test88';subprocess.run(common+['-O2',str(HERE/'test88.c'),*sources,'-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
    if a.sanitizers:
        sanitized=work/'test88-sanitized'
        subprocess.run(common+['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(HERE/'test88.c'),*sources,'-lm','-o',str(sanitized)],check=True)
        subprocess.run([str(sanitized)],env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'},check=True)
    c=ctypes.CDLL(str(lib));ptr=ctypes.c_void_p;size=ctypes.c_size_t
    c.hb55_default_curve.argtypes=[ptr]
    c.hb55_gradate.argtypes=[ptr,ptr,size,ptr];c.hb88_gradate.argtypes=[ptr,size,ptr]
    for name in ('hb55_output_rgb16','hb88_output_rgb16'):getattr(c,name).argtypes=[ptr,size,ptr,ctypes.c_double,ptr]
    for name in ('hb88_decode_builds','hb88_curve_builds'):getattr(c,name).restype=ctypes.c_ulong
    curve=np.empty(65536,np.uint16);assert c.hb55_default_curve(curve.ctypes.data)==0
    ramp=np.arange(65536,dtype=np.uint16);rng=np.random.default_rng(88)
    patterns=[np.repeat(ramp[:,None],3,axis=1),np.stack([ramp,np.roll(ramp,21845),np.roll(ramp,43690)],axis=1),rng.integers(0,65536,(65536,3),dtype=np.uint16)]
    matrices=[np.eye(3),np.array([[1.12,-.1,-.02],[-.04,1.03,.01],[.02,-.2,1.18]]),np.array([[3,-2,0],[0,.5,0],[-1,0,2]])]
    cases=channels=0
    for x in patterns:
        x=np.ascontiguousarray(x);old=np.empty_like(x);new=np.empty_like(x)
        assert c.hb55_gradate(curve.ctypes.data,x.ctypes.data,len(x),old.ctypes.data)==0
        assert c.hb88_gradate(x.ctypes.data,len(x),new.ctypes.data)==0
        assert np.array_equal(old,new);cases+=1;channels+=x.size
        alias=x.copy();assert c.hb88_gradate(alias.ctypes.data,len(alias),alias.ctypes.data)==0;assert np.array_equal(alias,old)
        for exponent in (.25,1.,1.8,2.2,3.,8.):
            for matrix in matrices:
                matrix=np.ascontiguousarray(matrix,dtype=np.float64)
                assert c.hb55_output_rgb16(x.ctypes.data,len(x),matrix.ctypes.data,exponent,old.ctypes.data)==0
                assert c.hb88_output_rgb16(x.ctypes.data,len(x),matrix.ctypes.data,exponent,new.ctypes.data)==0
                assert np.array_equal(old,new),(exponent,matrix);cases+=1;channels+=x.size
                alias=x.copy();assert c.hb88_output_rgb16(alias.ctypes.data,len(alias),matrix.ctypes.data,exponent,alias.ctypes.data)==0;assert np.array_equal(alias,old)
    assert c.hb88_curve_builds()==1
    small=np.array([[0,32768,65535]],np.uint16);out=np.full_like(small,4242);matrix=np.eye(3,dtype=np.float64)
    for e in (0.,-1.,8.01,float('nan'),float('inf')):
        assert c.hb88_output_rgb16(small.ctypes.data,1,matrix.ctypes.data,e,out.ctypes.data)==-1;assert np.all(out==4242)
    for bad in (float('nan'),float('inf'),1e6+1):
        m=matrix.copy();m[0,0]=bad
        assert c.hb88_output_rgb16(small.ctypes.data,1,m.ctypes.data,2.2,out.ctypes.data)==-1;assert np.all(out==4242)
    count=c.hb88_decode_builds()
    for _ in range(47):assert c.hb88_output_rgb16(small.ctypes.data,1,matrix.ctypes.data,2.25,out.ctypes.data)==0
    assert c.hb88_decode_builds()==count+1
    # Frame-sized finishing workload, 4032 x 3008 in the existing 47 x 64-row bands.
    x=rng.integers(0,65536,(4032*64,3),dtype=np.uint16);g=np.empty_like(x);out=np.empty_like(x)
    def timed(cached):
        start=time.perf_counter_ns()
        for _ in range(47):
            if cached:assert c.hb88_gradate(x.ctypes.data,len(x),g.ctypes.data)==0
            else:
                assert c.hb55_default_curve(curve.ctypes.data)==0
                assert c.hb55_gradate(curve.ctypes.data,x.ctypes.data,len(x),g.ctypes.data)==0
            f=c.hb88_output_rgb16 if cached else c.hb55_output_rgb16
            assert f(g.ctypes.data,len(g),matrix.ctypes.data,2.2,out.ctypes.data)==0
        return (time.perf_counter_ns()-start)/1e6
    old_times=[];new_times=[]
    for i in range(5):
        for cached in ((False,True) if i%2==0 else (True,False)):
            (new_times if cached else old_times).append(timed(cached))
    old_ms=float(np.median(old_times));new_ms=float(np.median(new_times))
    result={'schema':'hasselblad-stage88-cache-v1','status':'PASS_EXACT_FINISHING_CACHE','numeric_cases':cases,'rgb16_channels_compared':channels,'max_abs_difference':0,'in_place_matches':True,'concurrent_output_cases':160,'cold_concurrent_initialization_passed':True,'gradation_table_builds':1,'decode_builds_for_47_same_exponent_bands':1,'cache_bytes':393216,'output_matrix_not_cached':True,'sanitizers_passed':a.sanitizers,'benchmark':{'scope':'host only, finishing only, synthetic 4032x3008 workload; not Android or shutter timing','uncached_ms':old_times,'cached_ms':new_times,'uncached_median_ms':old_ms,'cached_median_ms':new_ms,'median_reduction_ms':old_ms-new_ms,'median_reduction_percent':100*(old_ms-new_ms)/old_ms},'original_native_oracle_retested':False,'demosaic_retested':False,'device_tested':False}
    (work/'STAGE88_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
