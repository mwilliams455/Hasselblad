#!/usr/bin/env python3
"""Stage41D: classify source-bound liveview_after_sbpc neighboring stage tokens.

Only exact 1.3.16.2 camera-service .rodata structural names/relocation metadata;
never code execution, original text dumps, camera buffers or colour matrices.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from inspect_original_liveview_xrefs41b import PIN,LABEL,ARCHIVE_SHA,require,sha
SOURCE='system/bin/camera-service'
MAX_SECTION=64*1024*1024
MAX_TOKENS=80
MAX_POINTER_REFS=40
# Restrict output to structured, non-sensitive stage identifiers. Never output
# arbitrary neighboring vendor strings, paths, files, customer data, or logs.
SAFE_STAGE=re.compile(rb'^(?:liveview_(?:before|after|from|to)_[a-z0-9_]{2,48}|[a-z0-9_]{3,45}_sbpc)$')

def structured_strings(data:bytes):
 tokens=[]
 for token in data.split(b'\0'):
  if 5<=len(token)<=80 and SAFE_STAGE.fullmatch(token):
   tokens.append(token.decode('ascii'))
 return tokens

def inspect(root:Path):
 from elftools.elf.elffile import ELFFile
 from elftools.elf.relocation import RelocationSection
 require((root/'system/etc/VERSION').read_text().strip()=='1.3.16.2','wrong_original_version')
 f=root/SOURCE
 require(f.is_file() and sha(f)==PIN[SOURCE],'original_camera_service_identity_mismatch')
 with f.open('rb') as source:
  elf=ELFFile(source)
  require(elf['e_machine']=='EM_AARCH64' and elf['e_type'] in ('ET_DYN','ET_EXEC'),'not_original_AARCH64')
  stage_tokens=[];anchor=[];neighbors=[]
  for sec in elf.iter_sections():
   if sec.name not in ('.rodata','.data.rel.ro','.dynstr','.strtab'):continue
   if int(sec['sh_size'])>MAX_SECTION:continue
   raw=sec.data()
   stage_tokens.extend({'section':sec.name,'name':v} for v in structured_strings(raw))
   pos=0
   while True:
    k=raw.find(LABEL,pos)
    if k<0:break
    va=int(sec['sh_addr'])+k
    anchor.append({'section':sec.name,'VA_hex':hex(va),'offset_hex':hex(k)})
    nearby=raw[max(0,k-512):min(len(raw),k+512)]
    neighbors.extend({'section':sec.name,'name':x} for x in structured_strings(nearby))
    pos=k+len(LABEL)
  ensure_list=lambda x: sorted({(item['section'],item['name']) for item in x})
  all_tokens=ensure_list(stage_tokens)
  around_tokens=ensure_list(neighbors)
  require(len(anchor)<=16,'excessive_exact_anchor_occurrences')
  target_vas={int(x['VA_hex'],16) for x in anchor}
  data_relocs=[]
  for section in elf.iter_sections():
   if not isinstance(section,RelocationSection):continue
   if not section.name.startswith('.rela'):continue
   for rec in section.iter_relocations():
    if rec.is_RELA() and int(rec['r_addend']) in target_vas:
     data_relocs.append({'reloc_section':section.name,'reloc_offset_hex':hex(int(rec['r_offset'])),
                         'reloc_type':int(rec['r_info_type'])})
     require(len(data_relocs)<=MAX_POINTER_REFS,'excessive_data_relocations')
  direct_pointer_refs=[]
  for sec in elf.iter_sections():
   if sec.name not in ('.data','.data.rel.ro','.rodata'):continue
   if int(sec['sh_size'])>MAX_SECTION:continue
   data=sec.data()
   for va in target_vas:
    needle=struct.pack('<Q',va)
    at=0
    while True:
     idx=data.find(needle,at)
     if idx<0:break
     direct_pointer_refs.append({'section':sec.name,'offset_hex':hex(idx)})
     require(len(direct_pointer_refs)<=MAX_POINTER_REFS,'excessive_literal_address_entries')
     at=idx+8
  require(len(all_tokens)<=256,'structured_name_inventory_exceeds_bound')
  return {'schema':'hasselblad-stage41d-original-sbpc-stage-labels-v1',
   'status':'PASS_pinned_original_camera_service_structured_stage_name_audit',
   'firmware_sha256':ARCHIVE_SHA,'source_sha256':PIN[SOURCE],
   'exact_label_locations':anchor,
   'stage_tokens_in_checked_string_sections':[
    {'section':s,'name':n} for s,n in all_tokens[:MAX_TOKENS]],
   'stage_tokens_truncated':len(all_tokens)>MAX_TOKENS,
   'structured_neighbors_of_exact_label':[
    {'section':s,'name':n} for s,n in around_tokens[:MAX_TOKENS]],
   'data_relocation_references_to_literal':data_relocs,
   'direct_aligned_pointer_value_matches':direct_pointer_refs,
   'actual_runtime_hook_registration_proven':False,
   'original_MAIN_CCM_input_output_placement_proven':False,
   'CCM_pixel_equation_proven':False,
   'vendor_proprietary_string_context_or_numeric_values_exported':False,
   'private_camera_frames_or_images_exported':False,
   'main_or_Photon_camera_saved_photo_renderer_modified':False,
   'caveat':'Structured names and relocation/pointer metadata alone do not establish camera control flow, original ISP stage order or real buffer format.'}

def synthetic():
 assert structured_strings(b'liveview_after_sbpc\0not_this\0liveview_before_ccm\0')==['liveview_after_sbpc','liveview_before_ccm']
 assert structured_strings(b'liveview_secret_password\0hello_liveview_user\0')==[]
 assert structured_strings(b'right_after_sbpc\0')==['right_after_sbpc']
 assert structured_strings(b'/etc/liveview_after_sbpc\0')==[]
 assert structured_strings(b'liveview_after_\npassword\0')==[]
 assert structured_strings(b'liveview_before_ccm\0')==['liveview_before_ccm']
 assert LABEL==b'liveview_after_sbpc'
 assert PIN[SOURCE].startswith('51b9e02f')
 assert MAX_SECTION<=64*1024*1024
 assert MAX_TOKENS<=80
 return {'status':'PASS_synthetic','checks':10,
         'vendor_firmware_loaded':False,'original_CCM_stage_proven':False}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--self-test',action='store_true')
 p.add_argument('--firmware-root',type=Path)
 p.add_argument('--output',type=Path)
 args=p.parse_args()
 d=synthetic() if args.self_test else inspect(args.firmware_root if args.firmware_root is not None else
     (_ for _ in ()).throw(ValueError('original_root_required')))
 if args.output:
  args.output.parent.mkdir(parents=True,exist_ok=True)
  args.output.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'status':d['status'],
  'original_stage_token_count':len(d.get('stage_tokens_in_checked_string_sections',[])),
  'neighbor_labels':d.get('structured_neighbors_of_exact_label',[]),
  'literal_data_relocation_count':len(d.get('data_relocation_references_to_literal',[])),
  'CCM_pixel_equation_proven':False},sort_keys=True))

if __name__=='__main__':main()