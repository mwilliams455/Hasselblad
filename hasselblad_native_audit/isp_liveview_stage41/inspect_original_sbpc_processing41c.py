#!/usr/bin/env python3
"""Stage41C: exactly pinned original X2D II SBPC processing and DSP-handler calls.

Non-executing static call inspection of the original camera plugins AIO ELF.
Frame callback names are not evidence of pre-/post-CCM access. No firmware,
image data, vendor executable bytes, numeric IQ matrices or keys are exported.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from inspect_original_liveview_xrefs41b import PIN,ARCHIVE_SHA,symbols,owner,code_slice,require,sha

PLUGIN='system/lib64/camera/plugins/libdcam_plugins_AIO.so'
TARGET_NAMES=(
 '_liveview_mee_on_buffer',
 '_process_on_buffer',
 '_liveview_mee_on_input_port_starting',
 '_liveview_mee_on_input_port_stopping',
)
SBPC_FUNCTION_PARTS=(
 'requestDspHandler','releaseDspHandler','registerContainerCmd',
 'onSwitchSegmentSuccess','setSbpcCaliInfo','updateLiveviewSBPCMode',
)
ARITHMETIC=('mul','madd','msub','smull','umull','fmul','fmla','sdiv','udiv','smaddl','umaddl')
MAX_FN=24*1024
MAX_LINKS=30

def parse_plt(elf):
 from elftools.elf.relocation import RelocationSection
 section=elf.get_section_by_name('.plt')
 rel=elf.get_section_by_name('.rela.plt')
 if section is None or rel is None or not isinstance(rel,RelocationSection):return {},False
 rs=list(rel.iter_relocations())
 if int(section['sh_size'])!=32+16*len(rs):return {},False
 table=elf.get_section(int(rel['sh_link']))
 mapping={}
 for i,r in enumerate(rs):
  n=table.get_symbol(int(r['r_info_sym'])).name
  if n:mapping[int(section['sh_addr'])+32+i*16]=n
 return mapping,True

def classify(name):
 value=name.lower()
 if any(x in value for x in ('dsp','rpc','remote','function_client')):return 'DSP_related_named_call'
 if any(x in value for x in ('frame','buffer','buf','plane','stream')):return 'frame_or_buffer_named_call'
 if any(x in value for x in ('ccm','gamma','3dlut','colour','color')):return 'colour_named_call'
 if any(x in value for x in ('memcpy','memset','malloc','free')):return 'memory_named_call'
 return 'other_or_unknown'

def inspect_one(elf,by_name,by_start,plt,name):
 from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
 from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_MEM
 addr,size=by_name[name]
 require(4<=size<=MAX_FN,'unexpected_function_extent_'+name)
 code=code_slice(elf,addr,size)
 cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
 calls=Counter();memory_in=memory_out=arith=backward=indirect=inst_count=0
 for ins in cs.disasm(code,addr):
  inst_count+=1
  m=ins.mnemonic.lower()
  if m=='bl':
   immediates=[int(op.imm) for op in ins.operands if op.type==ARM64_OP_IMM]
   require(len(immediates)==1,'unexpected_original_call_shape')
   tgt=immediates[0]
   dst='plt:'+plt[tgt] if tgt in plt else 'local:'+owner(tgt,by_start)
   calls[dst]+=1
  elif m=='blr':indirect+=1
  if m.startswith(('ld','prfm')) and any(op.type==ARM64_OP_MEM for op in ins.operands):memory_in+=1
  if m.startswith('st') and any(op.type==ARM64_OP_MEM for op in ins.operands):memory_out+=1
  if m in ARITHMETIC:arith+=1
  if m in ('b','b.eq','b.ne','b.lo','b.hs','cbz','cbnz','tbz','tbnz'):
   immediates=[int(op.imm) for op in ins.operands if op.type==ARM64_OP_IMM]
   if len(immediates)==1 and immediates[0]<ins.address:backward+=1
 require(inst_count>0 and inst_count*4==size,'incomplete_selected_instruction_decode_'+name)
 best=sorted(calls.items(),key=lambda x:(-x[1],x[0]))
 return {
  'symbol':name,'original_code_length':size,
  'original_code_sha256':hashlib.sha256(code).hexdigest(),
  'AArch64_instruction_count':inst_count,
  'loaded_memory_instruction_count':memory_in,
  'stored_memory_instruction_count':memory_out,
  'multiply_and_divide_instruction_count':arith,
  'backward_branch_count':backward,
  'direct_call_count':sum(calls.values()),
  'indirect_call_count':indirect,
  'source_of_calls':'exact original static BL targets, PLT ordinal mapping when validated',
  'bounded_direct_callees':[{'name':n,'count':num,'name_based_category':classify(n)} for n,num in best[:MAX_LINKS]],
  'callees_truncated':len(best)>MAX_LINKS,
  'per_pixel_CCM_input_or_output_verified':False,
 }

def inspect(root):
 from elftools.elf.elffile import ELFFile
 require((root/'system/etc/VERSION').read_text().strip()=='1.3.16.2','wrong_original_version')
 p=root/PLUGIN
 require(p.is_file() and sha(p)==PIN[PLUGIN],'original_plugin_identity_mismatch')
 with p.open('rb') as f:
  elf=ELFFile(f)
  require(elf['e_machine']=='EM_AARCH64' and elf['e_type']=='ET_DYN','original_not_AARCH64_ET_DYN')
  byname=symbols(elf)
  bystart={}
  for n,(a,size) in byname.items():bystart.setdefault(a,[]).append((n,size))
  plt,plt_valid=parse_plt(elf)
  chosen={x for x in TARGET_NAMES if x in byname}
  chosen.update(n for n in byname if 'LiveViewSBPCManager' in n and any(term in n for term in SBPC_FUNCTION_PARTS))
  require('_liveview_mee_on_buffer' in chosen,'expected_original_buffer_callback_missing')
  require('_process_on_buffer' in chosen,'expected_original_callback_target_missing')
  require(len(chosen)<=24,'selected_function_count_excessive')
  rows={x:inspect_one(elf,byname,bystart,plt,x) for x in sorted(chosen)}
  callback=rows['_liveview_mee_on_buffer']['bounded_direct_callees']
  require(any(x['name']=='local:_process_on_buffer' for x in callback),
          'original_liveview_mee_callback_no_longer_points_to_process_on_buffer')
  return {'schema':'hasselblad-stage41c-original-sbpc-buffer-callback-v1',
   'status':'PASS_exact_original_AIO_SBPC_function_call_inspection',
   'original_firmware_version':'1.3.16.2','original_full_archive_sha256':ARCHIVE_SHA,
   'source_sha256':PIN[PLUGIN],
   'PLT_import_name_mapping_validated':plt_valid,
   'symbol_count_total':len(byname),
   'selected_functions_total':len(rows),
   'functions':rows,
   'buffer_entry_dispatch_to__process_on_buffer_verified':True,
   'original_camera_running_or_Camera2_used':False,
   'actual_frame_content_or_original_pixel_format_verified':False,
   'SBPC_before_or_after_MAIN_CCM_verified':False,
   'original_CCM_pixel_equation_proven':False,
   'vendor_binary_or_numeric_tuning_exported':False,
   'photon_main_or_saved_photo_render_modified':False,
   'boundary':'Named DSP/frame callbacks do not establish colour stage order, hardware pixel domain, original image dataflow or same-frame pre/post CCM buffers.'}

def synthetic():
 assert classify('plt:pp_dsp_rpc')=='DSP_related_named_call'
 assert classify('local:write_frame_buf')=='frame_or_buffer_named_call'
 assert classify('local:main_ccm_lut')=='colour_named_call'
 assert classify('plt:memcpy')=='memory_named_call'
 assert classify('plt:dcam_other')=='other_or_unknown'
 assert '_process_on_buffer' in TARGET_NAMES
 assert '_liveview_mee_on_buffer' in TARGET_NAMES
 assert len(PIN)==2
 assert PIN[PLUGIN].startswith('1924f9')
 assert MAX_FN<=24576
 assert MAX_LINKS<=30
 return {'status':'PASS_synthetic','checks':11,'original_firmware_loaded':False,
         'photographic_CCM_pixel_equation_proven':False}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--self-test',action='store_true')
 ap.add_argument('--firmware-root',type=Path)
 ap.add_argument('--output',type=Path)
 a=ap.parse_args()
 d=synthetic() if a.self_test else inspect(a.firmware_root if a.firmware_root is not None else
  (_ for _ in ()).throw(ValueError('original_firmware_root_required')))
 if a.output:
  a.output.parent.mkdir(parents=True,exist_ok=True)
  a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'status':d['status'],
   'PLT_resolved':d.get('PLT_import_name_mapping_validated'),
   'functions':d.get('selected_functions_total',0),
   'callback_to_process_on_buffer':d.get('buffer_entry_dispatch_to__process_on_buffer_verified',False),
   'CCM_pixel_equation_proven':False},sort_keys=True))

if __name__=='__main__':main()