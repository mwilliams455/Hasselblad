#!/usr/bin/env python3
"""Stage41B: exact-original X2D II liveview_after_sbpc reference provenance.

Investigates only pinned original camera-service and camera/plugin AIO ELF files.
Looks for the literal's ELF section, bounded code references and selected DSP/
SBPC original function calls. No executable calls, camera or pixels are touched.
"""
from __future__ import annotations
import argparse,bisect,hashlib,io,json,lzma,re
from collections import Counter
from pathlib import Path

PIN={
 'system/bin/camera-service':'51b9e02f8bfebf388be8dfa163c8e512bee19aeb8ae37a6712727ccc6f26a52d',
 'system/lib64/camera/plugins/libdcam_plugins_AIO.so':'1924f9aca6d5f4f92ff482f6a864579d303a890fcef3427053f35d9b00bd4135',
}
ARCHIVE_SHA='9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'
LABEL=b'liveview_after_sbpc'
MAX_XREFS=50
MAX_FUNCTION_SIZE=24*1024
MAX_TEXT_BYTES=64*1024*1024
MAX_DEBUG_BYTES=64*1024*1024
SAFE_NAME=re.compile(r'^[A-Za-z_.$@][A-Za-z0-9_.$@:+\-]{0,200}$')
CHOSEN={
 'requestDspHandler','releaseDspHandler','registerContainerCmd',
 'onSwitchSegmentSuccess','updateLiveviewSBPCMode','setParameters',
 'setSbpcCaliInfo','_liveview_mee_on_buffer','_liveview_mee_on_input_port_starting',
 '_liveview_mee_on_input_port_stopping','normalFillSubTable',
 'LiveviewSBPCMode','liveview_after_sbpc',
}

def require(b,msg):
 if not b:raise ValueError(msg)

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def selected_name(n):
 return bool(SAFE_NAME.fullmatch(n)) and any(token in n for token in CHOSEN)

def symbols(elf):
 from elftools.elf.elffile import ELFFile
 items={}
 for name in ('.dynsym','.symtab'):
  sec=elf.get_section_by_name(name)
  if sec:
   for s in sec.iter_symbols():
    if s.name and s['st_info']['type']=='STT_FUNC' and s['st_shndx']!='SHN_UNDEF' and 4<=int(s['st_size'])<=MAX_FUNCTION_SIZE and SAFE_NAME.fullmatch(s.name):
     items.setdefault(s.name,(int(s['st_value']),int(s['st_size'])))
 sec=elf.get_section_by_name('.gnu_debugdata')
 if sec and int(sec['sh_size'])<=MAX_DEBUG_BYTES:
  d=lzma.decompress(sec.data(),memlimit=MAX_DEBUG_BYTES*4)
  require(len(d)<=MAX_DEBUG_BYTES,'mini_debugdata_oversize')
  dbg=ELFFile(io.BytesIO(d))
  sm=dbg.get_section_by_name('.symtab')
  if sm:
   for s in sm.iter_symbols():
    if s.name and s['st_info']['type']=='STT_FUNC' and s['st_shndx']!='SHN_UNDEF' and 4<=int(s['st_size'])<=MAX_FUNCTION_SIZE and SAFE_NAME.fullmatch(s.name):
     items.setdefault(s.name,(int(s['st_value']),int(s['st_size'])))
 return items

def owner(addr,by_start):
 starts=sorted(by_start)
 i=bisect.bisect_right(starts,addr)-1
 if i<0:return 'unresolved_function'
 start=starts[i]
 names=sorted(n for n,size in by_start[start] if addr<start+size)
 return names[0] if names else 'unresolved_function'

def needle_sections(elf):
 out=[]
 for sec in elf.iter_sections():
  if not int(sec['sh_size']) or int(sec['sh_size'])>MAX_TEXT_BYTES:continue
  if sec.name in ('.text','.bss','.gnu_debugdata'):continue
  # The exact ASCII bytes are reported only as name and section locations.
  data=sec.data()
  pos=0
  while True:
   idx=data.find(LABEL,pos)
   if idx<0:break
   out.append({'section':sec.name,'file_section_offset_hex':hex(idx),
               'ELF_virtual_address_hex':hex(int(sec['sh_addr'])+idx),
               '_target_va':int(sec['sh_addr'])+idx})
   pos=idx+len(LABEL)
 require(len(out)<=64,'too_many_anchor_matches')
 return out

def code_slice(elf,addr,size):
 for seg in elf.iter_segments():
  if seg['p_type']!='PT_LOAD' or not int(seg['p_flags'])&1:continue
  start=int(seg['p_vaddr']);length=int(seg['p_filesz'])
  if start<=addr and addr+size<=start+length:
   return seg.data()[addr-start:addr-start+size]
 raise ValueError('missing_original_function_executable_segment')

def call_targets(elf,syms,addr,size):
 from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
 from capstone.arm64 import ARM64_OP_IMM
 by_start={}
 for name,(va,length) in syms.items():by_start.setdefault(va,[]).append((name,length))
 cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
 calls=Counter();blr=0;inst_count=0
 for ins in cs.disasm(code_slice(elf,addr,size),addr):
  inst_count+=1
  if ins.mnemonic=='bl':
   t=[int(op.imm) for op in ins.operands if op.type==ARM64_OP_IMM]
   n=owner(t[0],by_start) if len(t)==1 else 'unresolved_branch_operand'
   calls[n]+=1
  elif ins.mnemonic=='blr':blr+=1
 require(inst_count>0 and inst_count*4==size,'incomplete_original_function_decode')
 return {'instructions':inst_count,'direct_callsite_count':sum(calls.values()),
         'indirect_callsite_count':blr,
         'callee_names_bounded':[{'name':n,'count':k} for n,k in calls.most_common(12)],
         'callee_names_truncated':len(calls)>12,
         'original_image_abi_proven':False}

def code_references(elf,syms,anchors):
 from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
 from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG
 sec=elf.get_section_by_name('.text')
 require(sec is not None and 0<int(sec['sh_size'])<=MAX_TEXT_BYTES,'text_missing_or_oversize')
 addrs={x['_target_va'] for x in anchors}
 if not addrs:return {'literal_address_references':[],'instructions_examined':0,'direct_anchor_reference_proven':False}
 by_start={}
 for name,(va,size) in syms.items():by_start.setdefault(va,[]).append((name,size))
 result=[];i_count=0
 # Bounded ADRP/ADD and direct ADR reference probes. This does not trace
 # pointers through memory or linked Qt registration tables.
 cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
 candidates={}
 for ins in cs.disasm(sec.data(),int(sec['sh_addr'])):
  i_count+=1
  if i_count>4_000_000:raise ValueError('original_inspection_instruction_budget')
  ops=ins.operands
  if ins.mnemonic=='adrp' and len(ops)>=2 and ops[0].type==ARM64_OP_REG and ops[1].type==ARM64_OP_IMM:
   reg=ops[0].reg
   if any((x&~0xfff)==int(ops[1].imm) for x in addrs):
    candidates[reg]=(int(ops[1].imm),ins.address)
  elif ins.mnemonic=='adr' and len(ops)>=2 and ops[1].type==ARM64_OP_IMM and int(ops[1].imm) in addrs:
   result.append({'method':'ADR_direct_absolute','owner':owner(ins.address,by_start),
                  'instruction_site_hex':hex(ins.address)})
  elif ins.mnemonic=='add' and len(ops)>=3 and ops[0].type==ARM64_OP_REG and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
   reg=ops[1].reg
   previous=candidates.get(reg)
   if previous and 0<ins.address-previous[1]<=80 and previous[0]+int(ops[2].imm) in addrs:
    result.append({'method':'ADRP_ADD_candidate','owner':owner(ins.address,by_start),
                   'instruction_site_hex':hex(ins.address)})
  # expire state when moved far beyond the source to avoid cross-function false positives.
  for reg,v in list(candidates.items()):
   if ins.address-v[1]>80:del candidates[reg]
  require(len(result)<=MAX_XREFS,'too_many_original_anchor_xrefs')
 return {'literal_address_references':result,
         'instructions_examined':i_count,
         'direct_anchor_reference_proven':bool(result),
         'indirect_or_relocated_pointer_references_not_excluded':True}

def inspect(root):
 require((root/'system/etc/VERSION').read_text().strip()=='1.3.16.2','wrong_firmware')
 from elftools.elf.elffile import ELFFile
 report={}
 for rel,exp in PIN.items():
  path=root/rel
  require(path.is_file() and sha(path)==exp,'original_source_mismatch_'+rel)
  with path.open('rb') as f:
   elf=ELFFile(f)
   require(elf['e_type'] in ('ET_DYN','ET_EXEC') and elf['e_machine']=='EM_AARCH64','unexpected_elf_type')
   funcs=symbols(elf)
   matches=sorted((n,va,size) for n,(va,size) in funcs.items() if selected_name(n))
   rows=[]
   for name,va,size in matches[:24]:
    rows.append({'original_symbol':name,'size_bytes':size,
                 'role_hint_only':True,
                 'static_calls':call_targets(elf,funcs,va,size)})
   anchors=needle_sections(elf)
   refs=code_references(elf,funcs,anchors)
   report[rel]={
    'sha256':exp,
    'total_named_function_symbols_examined':len(funcs),
    'bounded_selected_candidate_functions':rows,
    'selected_functions_total':len(matches),
    'selected_functions_truncated':len(matches)>24,
    'literal_anchor_locations':[ {k:v for k,v in x.items() if k!='_target_va'} for x in anchors],
    'exact_literal_in_non_executable_sections':bool(anchors),
    'anchor_code_reference_scan':refs,
    'processor_stage_and_colour_domain_proven':False}
 return {'schema':'hasselblad-stage41b-original-sbpc-anchor-callgraph-v1',
         'status':'PASS_pinned_original_camera_service_and_AIO_static_xref_audit',
         'original_firmware_sha256':ARCHIVE_SHA,
         'source_reports':report,
         'upstream_named_post_sbpc_tap_is_runtime_verified':False,
         'same_frame_before_after_MAIN_CCM_proven':False,
         'CCM_pixel_equation_proven':False,
         'original_vendor_instruction_bytes_exported':False,
         'private_camera_images_or_calibration_exported':False,
         'phone_app_main_or_saved_photos_modified':False,
         'caveat':'ELF symbol names and bounded static code references only; matching rodata/branch does not identify a framebuffer format or executed capture path.'}

def synthetic():
 fake={100:[('a',30)],140:[('b',24)]}
 assert owner(100,fake)=='a'
 assert owner(129,fake)=='a'
 assert owner(130,fake)=='unresolved_function'
 assert owner(145,fake)=='b'
 assert owner(165,fake)=='unresolved_function'
 assert selected_name('_ZN19LiveViewSBPCManager17requestDspHandlerEv')
 assert selected_name('_liveview_mee_on_buffer')
 assert not selected_name('ccm_set_fmt')
 assert SAFE_NAME.fullmatch('_ZN19LiveViewSBPCManager')
 assert not SAFE_NAME.fullmatch('_secret\nX')
 assert LABEL==b'liveview_after_sbpc'
 assert len(PIN)==2
 return {'status':'PASS_synthetic','checks':12,
         'vendor_firmware_loaded':False,'CCM_pixel_equation_proven':False}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--self-test',action='store_true')
 p.add_argument('--firmware-root',type=Path)
 p.add_argument('--output',type=Path)
 a=p.parse_args()
 d=synthetic() if a.self_test else inspect(a.firmware_root if a.firmware_root is not None else
    (_ for _ in ()).throw(ValueError('original_root_required')))
 if a.output:
  a.output.parent.mkdir(parents=True,exist_ok=True)
  a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'status':d['status'],
                   'anchor':{k:{'literal':v['exact_literal_in_non_executable_sections'],
                       'xref_count':len(v['anchor_code_reference_scan']['literal_address_references']),
                       'selected_functions':v['selected_functions_total']}
                             for k,v in d.get('source_reports',{}).items()},
                   'ccm_pixel_equation_proven':False},sort_keys=True))

if __name__=='__main__':main()