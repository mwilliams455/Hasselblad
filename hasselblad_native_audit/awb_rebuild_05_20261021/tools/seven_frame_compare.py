#!/usr/bin/env python3
"""Check entire paired AWB context + REAWB states at exactly seven boundaries.

No extraction, invocation or reimplementation of proprietary vendor code occurs.
Original-firmware MODE refuses operation without a SHA256-verified libaaa.so.
Synthetic mode exercises the comparator but NEVER proves original equivalence.
Do not commit private snapshot binaries or original vendor files to Git.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

CBYTES=920560
HBYTES=1000
PINNED_ELF='7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba'
SCHEMA='hb-awb-seven-frame-v1'

class ContractError(ValueError):pass

def digest_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as reader:
        for chunk in iter(lambda:reader.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()

def safe_path(root:Path, name:str)->Path:
    if not isinstance(name,str) or not name or Path(name).is_absolute():
        raise ContractError('snapshot path must be nonempty and relative')
    resolved=(root/name).resolve()
    if not resolved.is_relative_to(root):
        raise ContractError('snapshot cannot escape the private input directory')
    if not resolved.is_file():raise ContractError('missing snapshot input')
    return resolved

def read_exact(path:Path, n:int)->bytes:
    if path.stat().st_size!=n:raise ContractError('snapshot length mismatch: expected '+str(n))
    return path.read_bytes()

def discrepancy(reference:bytes, owned:bytes)->dict:
    mismatches=0; first=None
    for k,(a,b) in enumerate(zip(reference,owned)):
        if a!=b:
            mismatches+=1
            if first is None:first=k
    return {'different_bytes':mismatches,'first_different_offset':first}

def compare(manifest_file:Path, private_root:Path, *, vendor_lib:Path|None=None)->dict:
    private_root=private_root.resolve()
    manifest=json.loads(manifest_file.read_text())
    if manifest.get('schema')!=SCHEMA:raise ContractError('schema mismatch')
    mode=manifest.get('mode')
    if mode not in {'synthetic','original_arm64'}:raise ContractError('mode must be synthetic or original_arm64')
    if mode=='original_arm64':
        if vendor_lib is None:raise ContractError('original ARM64 mode requires verified --vendor-lib')
        if not vendor_lib.is_file() or digest_file(vendor_lib)!=PINNED_ELF:
            raise ContractError('vendor lib does not match pinned original libaaa SHA256')
        if manifest.get('same_execution_asserted') is not True:
            raise ContractError('original mode requires explicit same-execution attestation')
    elif vendor_lib is not None:
        raise ContractError('synthetic mode must not provide vendor-lib')
    frames=manifest.get('frames')
    if not isinstance(frames,list) or len(frames)!=7:
        raise ContractError('exactly 7 frame pairs required')
    report=[];last_serial=-1;all_equal=True
    for i,frame in enumerate(frames):
        if not isinstance(frame,dict) or not isinstance(frame.get('serial'),int) or isinstance(frame.get('serial'),bool):
            raise ContractError('serial must be integer')
        serial=frame['serial']
        if serial<=last_serial:raise ContractError('serials must increase')
        last_serial=serial
        if frame.get('stage')!='after_outer_return':
            raise ContractError('unsupported stage: expected after_outer_return')
        x=frame.get('reference');y=frame.get('owned')
        if not isinstance(x,dict) or not isinstance(y,dict):raise ContractError('missing reference/owned blocks')
        ctx_ref=read_exact(safe_path(private_root,x.get('context')),CBYTES)
        ctx_own=read_exact(safe_path(private_root,y.get('context')),CBYTES)
        h_ref=read_exact(safe_path(private_root,x.get('reawb')),HBYTES)
        h_own=read_exact(safe_path(private_root,y.get('reawb')),HBYTES)
        for p in (x,y):
            if not isinstance(p.get('status'),int) or isinstance(p.get('status'),bool):
                raise ContractError('status must be integer')
        ctx=discrepancy(ctx_ref,ctx_own);handle=discrepancy(h_ref,h_own)
        equality=ctx['different_bytes']==0 and handle['different_bytes']==0 and x['status']==y['status']
        all_equal=all_equal and equality
        report.append({'index':i,'serial':serial,'context':ctx,'reawb':handle,
                       'reference_status':x['status'],'owned_status':y['status'],
                       'exact_bytes_and_status_equal':equality})
    return {'schema':SCHEMA,'mode':mode,'frames_checked':len(frames),'all_snapshots_equal':all_equal,
            'vendor_library_sha256_verified':mode=='original_arm64',
            'same_execution_claim_from_manifest_only':bool(manifest.get('same_execution_asserted')),
            'original_abi_invoked_by_this_tool':False,
            'original_awb_algorithm_reconstructed_by_this_tool':False,
            'verified_vendor_selected_neutral':False,
            'matched_snapshot_bytes_do_not_prove_authentic_scene_estimation':True,
            'frame_results':report}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--private-root',type=Path,required=True)
    ap.add_argument('--vendor-lib',type=Path)
    ap.add_argument('--report',type=Path)
    a=ap.parse_args(argv)
    try:
        result=compare(a.manifest,a.private_root,vendor_lib=a.vendor_lib)
    except (OSError,ValueError,KeyError,TypeError) as e:
        print('REJECTED:',str(e),file=sys.stderr)
        return 2
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'MATCH' if result['all_snapshots_equal'] else 'MISMATCH',
                      'frames_checked':result['frames_checked'],'mode':result['mode'],
                      'vendor_equivalence_proven':False}))
    return 0 if result['all_snapshots_equal'] else 1

if __name__=='__main__':raise SystemExit(main())