#!/usr/bin/env python3
"""Strict same-execution original-vs-owned AWB boundary comparator.

Run only against snapshots captured in ONE execution of the original Android
firmware harness, so opaque process pointers in its 920560-byte context have
meaningful identical values. This file is a comparator, NOT that lost harness.
Original vendor binaries, snapshots, raw private sidecars are NOT included.
"""
import argparse
import hashlib
import json
from pathlib import Path

SIZES={'context':920560,'handle':1000}

def check_pair(key, original, owned):
    original_bytes=Path(original).read_bytes()
    owned_bytes=Path(owned).read_bytes()
    expected=SIZES[key]
    if len(original_bytes)!=expected or len(owned_bytes)!=expected:
        raise ValueError(f'{key} expected {expected} bytes, got {len(original_bytes)} / {len(owned_bytes)}')
    changes=[i for i,(a,b) in enumerate(zip(original_bytes,owned_bytes)) if a!=b]
    return {'identical':not changes, 'expected_bytes':expected,
            'original_sha256':hashlib.sha256(original_bytes).hexdigest(),
            'owned_sha256':hashlib.sha256(owned_bytes).hexdigest(),
            'mismatching_byte_count':len(changes),
            'first_mismatching_offsets':changes[:16]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--same-execution',action='store_true',required=True,
                   help='Affirm contexts were produced in same ARM64 execution')
    p.add_argument('--original-context',type=Path,required=True)
    p.add_argument('--owned-context',type=Path,required=True)
    p.add_argument('--original-handle',type=Path,required=True)
    p.add_argument('--owned-handle',type=Path,required=True)
    p.add_argument('--original-status',type=int,required=True)
    p.add_argument('--owned-status',type=int,required=True)
    a=p.parse_args()
    report={'scope':'same-execution original-vs-owned state comparison',
            'original_firmware_comparison_performed':True,
            'context':check_pair('context',a.original_context,a.owned_context),
            'handle':check_pair('handle',a.original_handle,a.owned_handle),
            'return_status_match':a.original_status==a.owned_status}
    report['result']='PASS' if report['context']['identical'] and report['handle']['identical'] and report['return_status_match'] else 'FAIL'
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())