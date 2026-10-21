#!/usr/bin/env python3
"""Reacquire/verify ONE pinned Hasselblad X2D II 1.3.16.2 source locally.
    PRIVATE data only. No vendor executable, decrypted payload or firmware in Git.
    This tool DOES NOT execute firmware or claim original AWB equivalence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

EXPECTED_PACKAGE_SHA='9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'
EXPECTED_PACKAGE_BYTES=364814336
EXPECTED_LIBAAA_SHA='7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba'
OFFICIAL_URL='https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim'
LIMIT_BYTES=EXPECTED_PACKAGE_BYTES+1

def inspect(path:Path,sha:str,exact_bytes:int|None=None)->dict:
    digest=hashlib.sha256()
    total=0
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):
            digest.update(chunk)
            total+=len(chunk)
    actual=digest.hexdigest()
    return {'bytes':total,'sha256':actual,'expected_sha256':sha,
            'sha256_matched':actual==sha,'size_matched':exact_bytes is None or total==exact_bytes,
            'validated':actual==sha and (exact_bytes is None or total==exact_bytes)}

def download_private(destination:Path)->dict:
    # Deliberately pins the exact official URL and expected bytes/hash.
    # The caller chooses a private path OUTSIDE the source repository.
    if destination.exists():raise FileExistsError('Refusing to overwrite existing firmware file')
    destination.parent.mkdir(parents=True,exist_ok=True)
    tmp=destination.with_name(destination.name+'.part')
    if tmp.exists():raise FileExistsError('Refusing to overwrite previous partial download')
    digest=hashlib.sha256();count=0
    try:
        with urlopen(Request(OFFICIAL_URL,headers={'User-Agent':'HasselbladPhoton-Restoration/1.0'}),timeout=60) as stream, tmp.open('xb') as out:
            while data:=stream.read(1024*1024):
                count+=len(data)
                if count>LIMIT_BYTES:raise ValueError('Official firmware download exceeded pinned file length')
                digest.update(data);out.write(data)
        if count!=EXPECTED_PACKAGE_BYTES or digest.hexdigest()!=EXPECTED_PACKAGE_SHA:
            raise ValueError('Firmware bytes or SHA-256 failed pinned verification')
        os.replace(tmp,destination)
        return {'sha256_matched':True,'size_matched':True,'validated':True,'bytes':count,
                'sha256':digest.hexdigest()}
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,help='Existing privately saved .cim')
    p.add_argument('--library',type=Path,help='Existing privately extracted system/lib64/libaaa.so')
    p.add_argument('--download-to',type=Path,help='Download exact official firmware to PRIVATE path, never into Git')
    p.add_argument('--report',type=Path,help='Save only booleans, byte counts and hashes')
    a=p.parse_args()
    if sum(v is not None for v in (a.package,a.download_to))>1:
        p.error('Use either --package or --download-to, not both')
    if not any((a.package,a.library,a.download_to)):
        p.error('Specify at least one private firmware or library input')
    results={'firmware':'X2D II 100C 1.3.16.2','original_awb_equivalence_proven':False,
             'package':None,'libaaa':None,'all_supplied_files_verified':False}
    if a.download_to:
        results['package']=download_private(a.download_to)
    elif a.package:
        results['package']=inspect(a.package,EXPECTED_PACKAGE_SHA,EXPECTED_PACKAGE_BYTES)
    if a.library:results['libaaa']=inspect(a.library,EXPECTED_LIBAAA_SHA)
    results['all_supplied_files_verified']=all(x['validated'] for x in (results['package'],results['libaaa']) if x is not None)
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results))
    return 0 if results['all_supplied_files_verified'] else 3

if __name__=='__main__':raise SystemExit(main())