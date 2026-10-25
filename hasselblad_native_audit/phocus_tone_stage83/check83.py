#!/usr/bin/env python3
"""Focused tone-pack, profile compatibility, RGB stream and comparison-metric tests."""
import argparse,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--private-pack',type=Path);a=p.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    classes=work/'classes';classes.mkdir(exist_ok=True)
    java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
    compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
    sources=[java/(s+'.java') for s in ('HasselbladTone83','HasselbladProfile43','HasselbladRenderer42')]
    subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,sources),str(HERE/'Stage83Check.java')],check=True)
    args=['java','-cp',str(classes),'Stage83Check',str(work/'STAGE83_HOST_VALIDATION.json')]
    if a.private_pack:args.append(str(a.private_pack.resolve()))
    subprocess.run(args,check=True)
if __name__=='__main__':main()
