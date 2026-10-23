#!/usr/bin/env python3
"""Stage41E: track a proven original camera-service RELATIVE pointer to SBPC label.

Original ELF metadata, bounded pointer/ADR reference search only.
Does not hook or execute a camera, copy software or read camera pixel data.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json,re
from pathlib import Path
from inspect_original_liveview_xrefs41b import PIN,LABEL,ARCHIVE_SHA,require,sha,symbols,owner

SOURCE='system/bin/camera-service'
RELATIVE=1027  # R_AARCH64_RELATIVE
MAX_TEXT_BYTES=64*1024*1024
MAX_XREFS=48
SAFE_SYMBOL=re.compile(r'^[A-Za-z_.$@][A-Za-z0-9_.$@:+\-]{0,200}$')

def in_section(elf,va):
 for sec in elf.iter_sections():
  start=int(sec['sh_addr']);end=start+int(sec['sh_size'])
  if start<=va<end and (int(sec['sh_flags']) & 2):
   return sec.name
 return 'no_allocated_section'

def object_owners(elf,va):
 owners=[]
 for section_name in ('.symtab','.dynsym'):
  table=elf.get_section_by_name(section_name)
  if table is None:continue
  for sym in table.iter_symbols():
   if (not sym.name or not SAFE_SYMBOL.fullmatch(sym.name) or
       sym['st_info']['type']!='STT_OBJECT' or sym['st_shndx']=='SHN_UNDEF'):continue
   start=int(sym['st_value']);size=int(sym['st_size'])
   if size and start<=va<start+size:
    owners.append({'name':sym.name,'byte_offset_within_object':va-start,'size':size})
 return sorted(owners,key=lambda x:(x['size'],x['name']))[:16]

def relocations_for_label(elf,label_va):
 from elftools.elf.relocation import RelocationSection
 slots=[]
 for rs in elf.iter_sections():
  if not isinstance(rs,RelocationSection) or not rs.name.startswith('.rela'):continue
  for rec in rs.iter_relocations():
   if rec.is_RELA() and int(rec['r_addend'])==label_va:
    slots.append({'site_va':int(rec['r_offset']),
                  'reloc_section':rs.name,'reloc_type':int(rec['r_info_type'])})
 require(len(slots)<=24,'too_many_original_label_relocations')
 return slots

def nearby_relocation_classes(elf,site_va):
 from elftools.elf.relocation import RelocationSection
 out=[]
 for rs in elf.iter_sections():
  if not isinstance(rs,RelocationSection) or not rs.name.startswith('.rela'):continue
  for rec in rs.iter_relocations():
   at=int(rec['r_offset'])
   if abs(at-site_va)>64:continue
   target=int(rec['r_addend']) if rec.is_RELA() else 0
   out.append({'relative_pointer_offset':at-site_va,
               'source_relocation_section':rs.name,
               'relocation_type':int(rec['r_info_type']),
               'relocated_target_allocated_section':in_section(elf,target) if rec.is_RELA() else 'no_addend'})
 return sorted(out,key=lambda x:(abs(x['relative_pointer_offset']),x['relative_pointer_offset']))[:32]

def code_uses_pointer(elf,slots,syms):
 from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
 from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
 targets={s['site_va'] for s in slots}
 text=elf.get_section_by_name('.text')
 require(text is not None and 0<int(text['sh_size'])<=MAX_TEXT_BYTES,'original_code_text_missing_or_large')
 by_start={}
 for n,(v,l) in syms.items():by_start.setdefault(v,[]).append((n,l))
 cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
 pages={v&~0xfff for v in targets}
 adrp={};hits=[];nins=0
 for ins in cs.disasm(text.data(),int(text['sh_addr'])):
  nins+=1
  if nins>4_000_000:raise ValueError('original_instruction_budget_exceeded')
  ops=ins.operands
  if ins.mnemonic=='adrp' and len(ops)>=2 and ops[0].type==ARM64_OP_REG and ops[1].type==ARM64_OP_IMM:
   if int(ops[1].imm) in pages:
    adrp[ops[0].reg]=(int(ops[1].imm),ins.address)
  elif ins.mnemonic in ('add','ldr','ldrsw'):
   reg=None;off=None;kind=None
   if ins.mnemonic=='add' and len(ops)>=3 and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
    reg=ops[1].reg;off=int(ops[2].imm);kind='ADRP_ADD'
   elif len(ops)>=2 and ops[1].type==ARM64_OP_MEM:
    reg=ops[1].mem.base;off=int(ops[1].mem.disp);kind='ADRP_LDR_memory'
   old=adrp.get(reg)
   if old and 0<ins.address-old[1]<=96:
    calculated=old[0]+off
    for target in targets:
     if abs(calculated-target)<=64:
      hits.append({'method':kind,'function_owner':owner(ins.address,by_start),
                   'instruction_site_hex':hex(ins.address),'distance_from_relocation_slot':calculated-target,
                   'exact_pointer_slot_access':calculated==target})
  for reg,value in list(adrp.items()):
   if ins.address-value[1]>96:del adrp[reg]
  require(len(hits)<=MAX_XREFS,'excess_possible_pointer_xrefs')
 return {'instruction_count':nins,'bounded_pointer_site_candidates':hits,
         'candidate_count':len(hits),'active_live_camera_buffer_proven':False}

def inspect(root):
 from elftools.elf.elffile import ELFFile
 require((root/'system/etc/VERSION').read_text().strip()=='1.3.16.2','wrong_original_firmware')
 p=root/SOURCE
 require(p.is_file() and sha(p)==PIN[SOURCE],'original_camera_service_sha_mismatch')
 with p.open('rb') as f:
  elf=ELFFile(f)
  require(elf['e_machine']=='EM_AARCH64','wrong_original_arch')
  rd=elf.get_section_by_name('.rodata')
  require(rd is not None,'rodata_missing')
  locs=[];raw=rd.data();at=0
  while True:
   i=raw.find(LABEL,at)
   if i<0:break
   locs.append(int(rd['sh_addr'])+i)
   at=i+len(LABEL)
  require(len(locs)==1,'expected_one_original_exact_sbpc_label')
  label_va=locs[0]
  slots=relocations_for_label(elf,label_va)
  require(len(slots)==1 and slots[0]['reloc_type']==RELATIVE,
          'original_label_relocation_contract_unexpected')
  slot_va=slots[0]['site_va']
  require(in_section(elf,slot_va)=='.data.rel.ro',
          'original_label_pointer_not_in_expected_section')
  owners=object_owners(elf,slot_va)
  neighbors=nearby_relocation_classes(elf,slot_va)
  syms=symbols(elf)
  refs=code_uses_pointer(elf,slots,syms)
  return {'schema':'hasselblad-stage41e-original-postsbpc-label-pointer-v1',
   'status':'PASS_exact_original_camera_service_data_pointer_provenance',
   'source_sha256':PIN[SOURCE],
   'original_archive_sha256':ARCHIVE_SHA,
   'label_virtual_address_hex':hex(label_va),
   'label_section':'.rodata',
   'relative_pointer_slot_va_hex':hex(slot_va),
   'relative_pointer_section':in_section(elf,slot_va),
   'relative_pointer_relocation_kind':RELATIVE,
   'matched_named_containing_objects':owners,
   'bounded_nearby_relocation_classes':neighbors,
   'code_pointer_uses':refs,
   'original_label_table_statically_present':True,
   'original_frame_format_or_stage_location_verified':False,
   'active_hook_installed_or_executed_verified':False,
   'camera_hardware_or_original_DSP_called':False,
   'MAIN_CCM_before_after_pixel_oracle_proven':False,
   'main_or_Photon_saved_photo_renderer_modified':False,
   'vendor_function_bytes_or_raw_strings_exported':False,
   'private_camera_data_or_vendor_tuning_exported':False}

def synthetic():
 assert RELATIVE==1027
 assert in_section.__name__=='in_section'
 assert SOURCE=='system/bin/camera-service'
 assert PIN[SOURCE].startswith('51b9e02f')
 assert LABEL==b'liveview_after_sbpc'
 assert MAX_XREFS<=48
 assert MAX_TEXT_BYTES<=64*1024*1024
 assert SAFE_SYMBOL.fullmatch('_ZL_labelObject')
 assert not SAFE_SYMBOL.fullmatch('secret\nvalue')
 return {'status':'PASS_synthetic','checks':9,
         'firmware_loaded':False,'pixel_oracle_proven':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--self-test',action='store_true')
 parser.add_argument('--firmware-root',type=Path)
 parser.add_argument('--output',type=Path)
 args=parser.parse_args()
 report=synthetic() if args.self_test else inspect(args.firmware_root if args.firmware_root else
     (_ for _ in ()).throw(ValueError('original_firmware_path_required')))
 if args.output:
  args.output.parent.mkdir(parents=True,exist_ok=True)
  args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':report['status'],
                   'owner_objects':len(report.get('matched_named_containing_objects',[])),
                   'possible_code_uses':report.get('code_pointer_uses',{}).get('candidate_count',0),
                   'isolated_CCM_pixel_oracle':False},sort_keys=True))

if __name__=='__main__':main()