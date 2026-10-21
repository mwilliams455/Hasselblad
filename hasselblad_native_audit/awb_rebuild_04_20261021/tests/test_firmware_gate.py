#!/usr/bin/env python3
"""Offline negative controls; no online firmware download is made."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('firmware_gate',root/'tools/firmware_gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
cases=0
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'fake.cim';path.write_bytes(b'nothing like original vendor firmware')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert gate.inspect(path,digest,len(path.read_bytes()))['validated'];cases+=1
    assert not gate.inspect(path,digest,len(path.read_bytes())+1)['validated'];cases+=1
    assert not gate.inspect(path,'0'*64,len(path.read_bytes()))['validated'];cases+=1
    args=[sys.executable,str(root/'tools/firmware_gate.py'),'--package',str(path),'--report',str(Path(d)/'report.json')]
    p=subprocess.run(args,capture_output=True,text=True)
    assert p.returncode==3;cases+=1
    r=json.loads((Path(d)/'report.json').read_text())
    assert r['original_awb_equivalence_proven'] is False and r['all_supplied_files_verified'] is False;cases+=1
    assert r['package']['sha256']==digest and r['package']['sha256_matched'] is False;cases+=1
    assert 'nothing like original vendor firmware' not in (Path(d)/'report.json').read_text();cases+=1
    assert (not gate.OFFICIAL_URL.endswith('localhost') and gate.EXPECTED_PACKAGE_BYTES==364814336);cases+=1
print(json.dumps({'status':'PASS','offline_pinned_firmware_gate_cases':cases,
   'official_firmware_download_attempted':False,'original_vendor_compared':False}))