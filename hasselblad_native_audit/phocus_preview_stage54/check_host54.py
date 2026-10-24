#!/usr/bin/env python3
"""Build the actual JNI library and run synthetic bridge/regression checks."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--jni-include',type=Path);a=p.parse_args()
    work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    classes=work/'classes';classes.mkdir(exist_ok=True)
    def run(*args):
        result=subprocess.run([str(x) for x in args],cwd=ROOT,check=True,text=True,capture_output=True)
        if result.stderr:print(result.stderr,file=sys.stderr,end='')
        return result.stdout
    src=ROOT/'HasselbladPhoton/app/src/main';audit=ROOT/'hasselblad_native_audit'
    java=src/'java/com/particlesdevs/photoncamera/hasselblad'
    javac=shutil.which('javac');java_binary=shutil.which('java')
    if not java_binary:raise RuntimeError('Java 17 is required')
    jdk=Path(javac or java_binary).resolve().parents[1]
    jni=a.jni_include.resolve() if a.jni_include else jdk/'include'
    if not (jni/'jni.h').is_file():raise RuntimeError('JNI headers required; pass --jni-include')
    units=['HasselbladRenderer42','HasselbladRenderBundle42','HasselbladDngTileReader','HasselbladProfile43','HasselbladPreparedHighlight54']
    tests=[audit/'phocus_port_stage42/Stage42BridgeSmoke.java',audit/'phocus_dng_stage43/Stage43Smoke.java',
           audit/'phocus_boundaries_stage48/Metadata48Check.java',Path(__file__).with_name('Stage54Smoke.java'),
           Path(__file__).with_name('Stage54PrivateCheck.java')]
    compiler=[javac] if javac else [java_binary,'com.sun.tools.javac.Main']
    run(*compiler,'--release','17','-d',classes,*[java/(name+'.java') for name in units],*tests)
    includes=[jni,jni/'linux',audit/'phocus_port_stage42/src',audit/'isp_dng_stage18/src',
              audit/'isp_colour_stage19/src',audit/'phocus_highlight_stage53']
    sources=[src/'cpp/hasselblad/hb_renderer42_jni.c',audit/'phocus_port_stage42/src/hb42_colour.c',
             audit/'isp_dng_stage18/src/hb_dng_pcs_bridge.c',audit/'isp_colour_stage19/src/hb_colour_stage19.c',
             audit/'phocus_highlight_stage53/highlight53.c']
    run('gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off','-fPIC','-shared',
        *['-I'+str(x) for x in includes],*sources,'-Wl,--no-undefined','-lm','-o',work/'libhasselblad_renderer42_jni.so')
    for script,dest in ((audit/'phocus_dng_stage43/make_fixtures43.py',work/'fixtures43'),
                        (audit/'phocus_boundaries_stage48/make_metadata_fixtures48.py',work/'fixtures48'),
                        (Path(__file__).with_name('make_bridge_fixtures54.py'),work/'fixtures54')):
        run(sys.executable,script,'--out',dest)
    results={}
    for test,args in (('Stage42BridgeSmoke',[]),('Stage43Smoke',[work/'fixtures43']),
                      ('Metadata48Check',[work/'fixtures48']),('Stage54Smoke',[work/'fixtures54'])):
        output=run('java','-Djava.library.path='+str(work),'-cp',classes,test,*args)
        results[test]=json.loads(output.strip().splitlines()[-1]);print(test,results[test]['status'],flush=True)
    receipt={'schema':'hasselblad-stage54-host-suite-v1','status':'PASS','results':results,
             'synthetic_only':True,'capture_renderer_changed':False,'device_tested':False}
    (work/'STAGE54_HOST_SUITE.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
