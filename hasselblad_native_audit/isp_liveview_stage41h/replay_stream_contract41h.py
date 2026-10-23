#!/usr/bin/env python3
"""Execute original forwarding/export functions with entirely synthetic resources."""
import argparse, hashlib, io, json, struct, sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from unicorn import UC_PROT_ALL
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_LR, UC_ARM64_REG_X0
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'isp_liveview_stage41g'))
from pixel_export41g import OfflineExporter, DATA, FRAME, HANDLE, PIXELS, STACK, STOP, symbols, parse_plt, require
from pixel_export41g import PIN as EXPORT_PIN
from inspect_stream_contract41h import configurations, PIN

FRWK=0x30000000
OUT=DATA+0x6000
OUT_SLOT=DATA+0x7000
OLD_HANDLE=DATA+0x8000


class ForwardReplay(OfflineExporter):
    def __init__(self,root):
        super().__init__(root)
        raw=(root/'libdcam_frwk.so').read_bytes()
        require(hashlib.sha256(raw).hexdigest()==PIN['system/lib64/libdcam_frwk.so'],'framework_hash_mismatch')
        e=ELFFile(io.BytesIO(raw));segs=[s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
        end=max(int(s['p_vaddr'])+int(s['p_memsz']) for s in segs)
        self.uc.mem_map(FRWK,(end+4095)&~4095,UC_PROT_ALL)
        for s in segs:self.uc.mem_write(FRWK+int(s['p_vaddr']),s.data())
        sy=symbols(e);pl,valid=parse_plt(e);require(valid,'framework_PLT_decode_failed')
        self.modules['libdcam_frwk.so']=(FRWK,sy)
        self.plt.update({FRWK+a:('libdcam_frwk.so',n) for a,n in pl.items()})
        for sec in e.iter_sections():
            if not isinstance(sec,RelocationSection):continue
            tab=e.get_section(sec['sh_link'])
            for rel in sec.iter_relocations():
                a=FRWK+int(rel['r_offset']);t=int(rel['r_info_type']);add=int(rel['r_addend']) if rel.is_RELA() else 0
                if t==1027:self.put64(a,FRWK+add)
                elif t in (257,1025):
                    s=tab.get_symbol(rel['r_info_sym'])
                    if s['st_shndx']!='SHN_UNDEF':self.put64(a,FRWK+int(s['st_value'])+add)

    def hook(self,uc,pc,size,unused):
        name=self.plt.get(pc,('', ''))[1]
        if name in ('duss_osal_mutex_lock','duss_osal_mutex_unlock'):
            self.count+=1;self.calls[name]+=1;self.ret();return
        super().hook(uc,pc,size,unused)

    def forward(self):
        self.count=0;self.returned=False
        self.uc.reg_write(UC_ARM64_REG_SP,STACK+0xff000)
        self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        self.uc.reg_write(UC_ARM64_REG_X0,FRAME)
        self.uc.reg_write(UC_ARM64_REG_X0+1,OUT_SLOT)
        self.uc.emu_start(FRWK+self.modules['libdcam_frwk.so'][1]['cam_stream_filter_eng_process_bypass_v2'][0],STOP+8,count=1000000)
        require(self.returned,'original_forwarder_did_not_return')

    def u32(self,p):return struct.unpack('<I',self.uc.mem_read(p,4))[0]
    def u64(self,p):return struct.unpack('<Q',self.uc.mem_read(p,8))[0]
    def format(self,name):
        self.uc.mem_write(DATA,name.encode()+b'\0')
        require(self.run('duss_pixel_format_from_str',[DATA,DATA+0x800])==0,'format_resolution_failed')
        return self.u32(DATA+0x800)


def descriptor_case(root,label,fmt_name,width,height,alignment,export_pixels):
    r=ForwardReplay(root/'system/lib64');fmt=r.format(fmt_name)
    # Type 0 common frame, one reference, no external parent or tracing flags.
    r.put64(FRAME,1);r.put64(FRAME+8,DATA+0x9000)
    r.put64(FRAME+0x20,HANDLE);r.put32(FRAME+0x28,fmt)
    r.put32(FRAME+0x38,width);r.put32(FRAME+0x3c,height);r.put32(FRAME+0xb4,123)
    r.put64(OUT,1);r.put64(OUT+0x20,OLD_HANDLE);r.put32(OUT+0x28,2)
    r.put32(OUT+0x38,4);r.put32(OUT+0x3c,2);r.put64(OUT_SLOT,OUT)
    payload=None;planes=[];length=0
    if export_pixels:
        length=r.run('frame_buffer_plane_info_generate',[FRAME,alignment,1])
        require(length+PIXELS<DATA+0x400000,'synthetic_payload_exceeds_mapping')
        require(r.u32(FRAME+0xb0)==2,'NV12_plane_count_changed')
        # Output plane layout is prepared separately; the forwarder does not copy it.
        r.put32(OUT+0x38,width);r.put32(OUT+0x3c,height)
        require(r.run('frame_buffer_plane_info_generate',[OUT,alignment,1])==length,'output_plane_layout_mismatch')
        payload=bytearray([205])*length
        for i in range(2):
            v=struct.unpack('<7I',r.uc.mem_read(FRAME+0x40+i*28,28))
            plane=dict(stride=v[0],offset=v[1],height=v[3]);planes.append(plane)
            for y in range(plane['height']):
                at=plane['offset']+y*plane['stride']
                payload[at:at+width]=bytes((i*101+y*7+x*3)%251 for x in range(width))
        r.uc.mem_write(PIXELS,bytes(payload));r.mapped_capacity=length
        # Deliberately wrong descriptor dimensions to verify overwrite by original helper.
        r.put32(OUT+0x38,4);r.put32(OUT+0x3c,2)
    plane_before=bytes(r.uc.mem_read(OUT+0x40,0x74))
    r.forward();forward_instructions=r.count
    require(r.u64(OUT+0x390)==FRAME,'output_parent_reference_missing')
    require(r.u64(OUT+0x20)==HANDLE and r.u64(OUT+0x3a0)==OLD_HANDLE,'shared_or_saved_memory_handle_changed')
    require(r.u32(OUT+0x28)==fmt and r.u32(OUT+0x38)==width and r.u32(OUT+0x3c)==height,'descriptor_overwrite_failed')
    require(r.u32(OUT+0xb4)==123 and (r.u64(FRAME)&0x7fffff)==2,'frame_id_or_refcount_failed')
    require(bytes(r.uc.mem_read(OUT+0x40,0x74))==plane_before,'forwarder_plane_layout_unexpectedly_changed')
    if export_pixels:
        r.uc.mem_write(DATA,b'synthetic.raw\0')
        require(r.run('dump_frame_to_file',[DATA,OUT,0])==0,'forwarded_frame_export_failed')
        require(r.output==payload,'export_not_byte_exact')
        require(bytes(r.uc.mem_read(PIXELS,length))==bytes(payload),'input_pixels_modified')
    return dict(case=label,original_format_name=fmt_name,original_format_enum=fmt,
        width=width,height=height,alignment=alignment,planes=planes,
        forward_instructions=forward_instructions,output_has_input_memory_handle=True,
        output_parent_reference=True,input_reference_count_after=2,
        output_format_and_dimensions_replaced=True,output_plane_layout_unchanged=True,
        input_pixel_bytes_unchanged=True if export_pixels else None,
        allocation_bytes=length,exported_bytes=len(r.output),
        byte_exact_export_including_padding=bool(export_pixels and r.output==payload),
        tight_NV12_bytes=width*height*3//2 if export_pixels else None,
        padding_bytes=length-width*height*3//2 if export_pixels else None,
        output_sha256=hashlib.sha256(r.output).hexdigest() if export_pixels else None,
        platform_calls=dict(r.calls),actual_camera_pixels=False)


def run(root):
    for rel in ('system/etc/imx861bqr_hb722.conf','system/etc/imx861bqr_hb722.sp','system/etc/iq/hb722_config.json'):
        require(hashlib.sha256((root/rel).read_bytes()).hexdigest()==PIN[rel],'configuration_hash_mismatch')
    cfg=configurations(root);desc=cfg['modes'][0]['streams']['liveview_sout1']
    w,h=desc['default_dimensions'];align=desc['alignment'][0]
    cases=[descriptor_case(root,'configured_SOUT1_NV12',desc['declared_format'],w,h,align,True),
      descriptor_case(root,'RAW_input_overwrites_output_declared_NV12','DUSS_PIXFMT_RAW16_OPAQUE',7408,1482,256,False)]
    require(cases[0]['allocation_bytes']==3225600 and cases[0]['padding_bytes']==345600,'configured_stride_expectation_changed')
    require(cases[1]['original_format_enum']!=2,'RAW_format_not_distinct')
    return dict(schema='hasselblad-stage41h-forwarded-export-v1',status='PASS_original_forwarder_and_configured_size_export',
        cases=cases,source_sha256={**PIN,**{'system/lib64/'+k:v for k,v in EXPORT_PIN.items()}},
        original_forwarding_and_export_code_emulated=True,
        entire_SBPC_callback_or_DSP_not_executed=True,platform_memory_mutex_cache_stdio_simulated=True,
        RAW_case_does_not_execute_shadow_filter=True,
        output_plane_layout_prepared_separately=True,physical_camera_accessed=False,
        actual_camera_pixels_obtained=False,MAIN_CCM_pixel_oracle_proven=False,
        vendor_bytes_or_tuning_values_exported=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.root);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=r['status'],cases=len(r['cases']),actual_camera_pixels_obtained=False)))
