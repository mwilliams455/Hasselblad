#!/usr/bin/env python3
"""Self-contained positive/negative fixture tests, no vendor binaries or RAW pixels."""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util,json
spec=importlib.util.spec_from_file_location('seven_frame_compare',Path(__file__).resolve().parents[1]/'tools/seven_frame_compare.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
count=0
with TemporaryDirectory() as d:
    root=Path(d);data={'schema':m.SCHEMA,'mode':'synthetic','same_execution_asserted':False,'frames':[]}
    for i in range(7):
        c=bytearray(m.CBYTES);c[0x174:0x178]=b'\x00\x00\x00\x00';c[0xb0c48:0xb0c4c]=bytes([i,20,31,55])
        h=bytearray(m.HBYTES);h[0]=i
        for kind,blob in [('ctx',c),('handle',h)]:
            (root/f'{i}_{kind}_reference.bin').write_bytes(blob)
            (root/f'{i}_{kind}_owned.bin').write_bytes(blob)
        data['frames'].append({'serial':100+i,'stage':'after_outer_return',
            'reference':{'context':f'{i}_ctx_reference.bin','reawb':f'{i}_handle_reference.bin','status':0},
            'owned':{'context':f'{i}_ctx_owned.bin','reawb':f'{i}_handle_owned.bin','status':0}})
    path=root/'manifest.json';path.write_text(json.dumps(data))
    a=m.compare(path,root);assert a['all_snapshots_equal'] and a['frames_checked']==7;count+=1
    assert not a['vendor_library_sha256_verified'] and not a['verified_vendor_selected_neutral'];count+=1
    f=root/'3_ctx_owned.bin';b=bytearray(f.read_bytes());b[0xb0c48]^=1;f.write_bytes(b)
    a=m.compare(path,root);assert not a['all_snapshots_equal'];count+=1
    assert a['frame_results'][3]['context']['first_different_offset']==0xb0c48;count+=1
    f=root/'3_ctx_owned.bin';f.write_bytes((root/'3_ctx_reference.bin').read_bytes())
    f=root/'5_handle_owned.bin';b=bytearray(f.read_bytes());b[4]^=1;f.write_bytes(b)
    a=m.compare(path,root);assert not a['all_snapshots_equal'];count+=1
    assert a['frame_results'][5]['reawb']['first_different_offset']==4;count+=1
    f.write_bytes((root/'5_handle_reference.bin').read_bytes())
    data['frames'][4]['owned']['status']=151;path.write_text(json.dumps(data))
    a=m.compare(path,root);assert not a['all_snapshots_equal'];count+=1
    data['frames'][4]['owned']['status']=0;data['mode']='original_arm64';path.write_text(json.dumps(data))
    try:m.compare(path,root)
    except m.ContractError as e:assert 'requires verified' in str(e);count+=1
    else:raise AssertionError('original accepted without pinned ELF')
    data['mode']='synthetic';data['frames'][2]['owned']['context']='../../etc/passwd';path.write_text(json.dumps(data))
    try:m.compare(path,root)
    except m.ContractError as e:assert 'escape' in str(e);count+=1
    else:raise AssertionError('path traversal accepted')
    data['frames'][2]['owned']['context']='2_ctx_owned.bin'
    data['frames'][6]['serial']=100;path.write_text(json.dumps(data))
    try:m.compare(path,root)
    except m.ContractError as e:assert 'increase' in str(e);count+=1
    else:raise AssertionError('out-of-order frames accepted')
    data['frames'][6]['serial']=106;data['frames']=data['frames'][:6];path.write_text(json.dumps(data))
    try:m.compare(path,root)
    except m.ContractError as e:assert 'exactly 7' in str(e);count+=1
    else:raise AssertionError('incomplete series accepted')
    data['frames'].append({'serial':106,'stage':'after_outer_return',
       'reference':{'context':'6_ctx_reference.bin','reawb':'6_handle_reference.bin','status':0},
       'owned':{'context':'6_ctx_owned.bin','reawb':'6_handle_owned.bin','status':0}})
    data['mode']='original_arm64';path.write_text(json.dumps(data))
    try:m.compare(path,root,vendor_lib=root/'manifest.json')
    except m.ContractError as e:assert 'pinned original' in str(e);count+=1
    else:raise AssertionError('wrong vendor file accepted')
print('SEVEN-FRAME SNAPSHOT EVIDENCE GATE PASS',count,'positive/negative fixture cases; vendor not invoked')