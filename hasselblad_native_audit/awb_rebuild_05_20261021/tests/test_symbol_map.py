#!/usr/bin/env python3
"""Synthetic index mutation controls; actual pinned inventory replay is documented separately."""
from pathlib import Path
import json,importlib.util,tempfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('export_scene_symbol_map',ROOT/'tools/export_scene_symbol_map.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
saved=json.loads((ROOT/'evidence/SCENE_SYMBOL_MAP.json').read_text())
assert saved['count']==39
assert saved['symbols']['scene_awb_scene_opt']['address']=='0x4a8c48'
assert saved['original_elf_bytes_available_now'] is False
assert saved['source_inventory_sha256']=='d99c5d19a4ef434d7e55056f8bb397a45737c3923edb8ec5f2f03be27da2393b'
cases=4
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'inventory.json'
    objs=[{'name':name,'va':int(data['address'],16),'bytes':data['byte_count'],'type':'STT_FUNC'}
          for name,data in saved['symbols'].items()]
    doc={'libraries':[{'path':'system/lib64/libaaa.so','sha256':m.PINNED_ELF_SHA,
                       'machine':'EM_AARCH64','colour_symbols':objs}]}
    path.write_text(json.dumps(doc))
    rebuilt=m.extract(path)
    assert rebuilt['symbols']==saved['symbols'];cases+=1
    doc['libraries'][0]['sha256']='0'*64;path.write_text(json.dumps(doc))
    try:m.extract(path)
    except ValueError as e:assert 'provenance' in str(e);cases+=1
    else:raise AssertionError('incorrect vendor hash accepted')
    doc['libraries'][0]['sha256']=m.PINNED_ELF_SHA
    target=next(x for x in objs if x['name']=='scene_awb_scene_opt')
    true_va=target['va'];target['va']=0
    path.write_text(json.dumps(doc))
    try:m.extract(path)
    except ValueError as e:assert 'drift' in str(e) or 'missing function' in str(e);cases+=1
    else:raise AssertionError('invented symbol address accepted')
    target['va']=true_va
    doc['libraries'][0]['colour_symbols']=objs[:-1];path.write_text(json.dumps(doc))
    try:m.extract(path)
    except ValueError as e:assert 'missing symbol' in str(e);cases+=1
    else:raise AssertionError('missing symbol accepted')
print('PRESERVED SYMBOL MAP CHECK',cases,'synthetic and source-index controls')