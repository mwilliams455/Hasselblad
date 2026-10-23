#!/usr/bin/env python3
"""Offline original ARM64 exporter test. Every platform resource is synthetic."""
import argparse, hashlib, io, json, struct, sys
import capstone, elftools, unicorn
from collections import Counter
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_PROT_ALL
from unicorn.arm64_const import *
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'isp_liveview_stage41'))
from inspect_original_liveview_xrefs41b import symbols, require
from inspect_original_sbpc_processing41c import parse_plt

PIN = {'libdcam_base.so':'8486fa7ce0b400992358ad92c445ad026a3784703accf2bae8a490ed10b2ff52',
       'libduml_hal.so':'adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20'}
BASE = 0x10000000
HAL = 0x20000000
DATA = 0x40000000
STACK = 0x50000000
STOP = 0x60000000
MAP_CALLBACK = STOP+4
PIXELS = DATA+0x10000
FRAME = DATA+0x1000
HANDLE = DATA+0x2000
DEVICE = DATA+0x2100
OPS = DATA+0x2200
TLS = DATA+0x3000


class OfflineExporter:
    def __init__(self, root):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.modules = {}
        self.plt = {}
        self.calls = Counter()
        self.strings_compared = set()
        self.writes = []
        self.syncs = []
        self.count = 0
        self.returned = False
        self.map_failure = False
        self.output = bytearray()
        self.mapped_capacity = 0
        self.max_write = None
        self.file_open_failure = False
        for name, base in [('libdcam_base.so', BASE), ('libduml_hal.so', HAL)]:
            raw = (root/name).read_bytes()
            require(hashlib.sha256(raw).hexdigest() == PIN[name], 'original_library_hash_mismatch')
            e = ELFFile(io.BytesIO(raw))
            require(e['e_machine']=='EM_AARCH64', 'wrong_arch')
            segments = [s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
            end = max(int(s['p_vaddr'])+int(s['p_memsz']) for s in segments)
            self.uc.mem_map(base,(end+4095)&~4095,UC_PROT_ALL)
            for s in segments:self.uc.mem_write(base+int(s['p_vaddr']),s.data())
            sy = symbols(e)
            pl, valid = parse_plt(e)
            require(valid, 'PLT_layout_not_recognized')
            self.modules[name] = (base, sy)
            for at,n in pl.items():self.plt[base+at]=(name,n)
            for sec in e.iter_sections():
                if not isinstance(sec,RelocationSection):continue
                tab = e.get_section(sec['sh_link'])
                for rel in sec.iter_relocations():
                    target = base+int(rel['r_offset'])
                    typ = int(rel['r_info_type'])
                    add = int(rel['r_addend']) if rel.is_RELA() else 0
                    if typ == 1027:self.put64(target,base+add)
                    elif typ in (257,1025):
                        sym = tab.get_symbol(rel['r_info_sym'])
                        if sym['st_shndx'] != 'SHN_UNDEF':self.put64(target,base+int(sym['st_value'])+add)
        self.uc.mem_map(DATA,0x400000,UC_PROT_ALL)
        self.uc.mem_map(STACK,0x100000,UC_PROT_ALL)
        self.uc.mem_map(STOP,0x1000,UC_PROT_ALL)
        self.uc.mem_write(STOP,bytes.fromhex('c0035fd6c0035fd6'))
        self.uc.reg_write(UC_ARM64_REG_TPIDR_EL0,TLS)
        self.uc.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
        self.put64(TLS+0x28,0x123456789abcdef0)
        self.put64(HANDLE,DEVICE)
        self.uc.mem_write(DEVICE+8,b'\x01')
        self.put64(DEVICE+0x68,OPS)
        self.put64(OPS+0x40,MAP_CALLBACK)
        self.uc.hook_add(UC_HOOK_CODE,self.hook)

    def put64(self,p,n):self.uc.mem_write(p,struct.pack('<Q',n & ((1<<64)-1)))
    def put32(self,p,n):self.uc.mem_write(p,struct.pack('<I',n & 0xffffffff))
    def reg(self,n):return self.uc.reg_read(UC_ARM64_REG_X0+n)
    def cstring(self,p):
        b=bytearray()
        for i in range(512):
            v=self.uc.mem_read(p+i,1)[0]
            if not v:return b.decode('ascii',errors='replace')
            b.append(v)
        raise ValueError('unterminated_string')
    def ret(self,value=0):
        self.uc.reg_write(UC_ARM64_REG_X0,value & ((1<<64)-1))
        self.uc.reg_write(UC_ARM64_REG_PC,self.uc.reg_read(UC_ARM64_REG_LR))

    def hook(self,uc,pc,size,_):
        self.count+=1
        require(self.count < 1000000,'instruction_budget_exceeded')
        if pc==STOP:
            self.returned=True
            uc.emu_stop()
            return
        if pc==MAP_CALLBACK:
            require(self.reg(0)==DEVICE and self.reg(1)==HANDLE,'unexpected_mapping_abi')
            self.calls['synthetic_memory_backend_map']+=1
            if self.map_failure:self.ret(-1)
            else:
                self.put64(self.reg(2),PIXELS)
                self.ret()
            return
        if pc not in self.plt:return
        module,name=self.plt[pc]
        self.calls[name]+=1
        # Calls exported by this ELF still execute their original implementations.
        base,sy=self.modules[module]
        if name in sy:
            uc.reg_write(UC_ARM64_REG_PC,base+sy[name][0])
            return
        if name=='duss_hal_mem_map':
            uc.reg_write(UC_ARM64_REG_PC,HAL+self.modules['libduml_hal.so'][1][name][0])
            return
        if name in ('strcmp','strncmp'):
            a,b=self.cstring(self.reg(0)),self.cstring(self.reg(1))
            self.strings_compared.update([a,b])
            if name=='strncmp':a,b=a[:self.reg(2)],b[:self.reg(2)]
            self.ret((a>b)-(a<b))
        elif name in ('memset','__memset_chk'):
            require(self.reg(2)<=0x400000,'memset_bound')
            uc.mem_write(self.reg(0),bytes([self.reg(1)&255])*self.reg(2));self.ret(self.reg(0))
        elif name in ('memcpy','__memcpy_chk','memmove'):
            require(self.reg(2)<=0x400000,'memcpy_bound')
            uc.mem_write(self.reg(0),bytes(uc.mem_read(self.reg(1),self.reg(2))));self.ret(self.reg(0))
        elif name in ('log_mgr_check','duss_log_gen_head','duss_log_print','co_thread_get',
                      'pthread_getspecific','log_to_kmsg','duss_log_dump_backtrace'):
            self.ret(0)
        elif name=='__errno':self.ret(TLS+0x80)
        elif name in ('abort','exit','__stack_chk_fail'):
            raise ValueError('original_fatal_path:'+name)
        elif name=='duss_hal_mem_get_flags':
            require(self.reg(0)==HANDLE,'unexpected_memory_handle')
            self.put32(self.reg(1),0);self.ret()
        elif name=='duss_hal_mem_sync_ext':
            require(self.reg(0)==HANDLE,'unexpected_sync_handle')
            self.syncs.append(dict(direction=self.reg(1),offset=self.reg(2),size=self.reg(3)))
            self.ret()
        elif name=='duss_hal_mem_unmap':
            require(self.reg(0)==HANDLE,'unexpected_unmap_handle');self.ret()
        elif name=='fopen':
            require(self.cstring(self.reg(0))=='synthetic.raw','unexpected_filename')
            self.ret(0 if self.file_open_failure else DATA+0x5000)
        elif name=='fwrite':
            ptr,unit,count,file=self.reg(0),self.reg(1),self.reg(2),self.reg(3)
            require(file==DATA+0x5000 and unit==1,'unexpected_fwrite_abi')
            require(PIXELS<=ptr and ptr+count<=PIXELS+self.mapped_capacity,'pixel_read_out_of_bounds')
            n=count if self.max_write is None else min(count,self.max_write)
            self.output.extend(uc.mem_read(ptr,n))
            self.writes.append(dict(offset=ptr-PIXELS,count=n))
            self.ret(n)
        elif name in ('fflush','fsync','fclose','fallocate64'):self.ret()
        elif name=='fileno':self.ret(7)
        elif name=='is_running_in_cam_sil':self.ret(1)
        else:raise ValueError('unhandled_original_import:'+name)

    def run(self,name,args):
        self.count=0;self.returned=False
        self.uc.reg_write(UC_ARM64_REG_SP,STACK+0xff000)
        self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        for i,x in enumerate(args):self.uc.reg_write(UC_ARM64_REG_X0+i,x)
        a=self.modules['libdcam_base.so'][1][name][0]
        self.uc.emu_start(BASE+a,STOP+8,count=1000000)
        require(self.returned,'original_function_did_not_return')
        return self.reg(0)


def run_cases(root):
    cases=[]
    tests=[('tight_small',16,8,1,None),('tight_640x480',640,480,1,None),
           ('padded_rows',18,10,64,None),('partial_fwrite',16,8,1,'short'),
           ('map_failure',16,8,1,'map'),('open_failure',16,8,1,'open')]
    for label,width,height,alignment,failure in tests:
        r=OfflineExporter(root)
        r.uc.mem_write(DATA,b'DUSS_PIXFMT_YUV8_SP420_YUV\0')
        status=r.run('duss_pixel_format_from_str',[DATA,DATA+0x800])
        fmt=struct.unpack('<I',r.uc.mem_read(DATA+0x800,4))[0]
        require(status==0 and fmt==2,'original_NV12_format_mapping_changed')
        r.put64(FRAME+0x20,HANDLE)
        r.put32(FRAME+0x28,fmt)
        r.put32(FRAME+0x38,width)
        r.put32(FRAME+0x3c,height)
        length=r.run('frame_buffer_plane_info_generate',[FRAME,alignment,1])
        count=struct.unpack('<I',r.uc.mem_read(FRAME+0xb0,4))[0]
        require(count==2 and length<=0x300000,'unexpected_NV12_plane_layout')
        rows=[]
        for i in range(count):
            values=struct.unpack('<7I',r.uc.mem_read(FRAME+0x40+i*28,28))
            rows.append(dict(stride=values[0],offset=values[1],height=values[3]))
        require(rows[0]['height']==height and rows[1]['height']==height//2,
                'unexpected_original_NV12_height')
        require(rows[0]['stride']>=width and rows[1]['stride']>=width,'invalid_stride')
        payload=bytearray([205])*length
        for i,plane in enumerate(rows):
            for y in range(plane['height']):
                row=bytes((i*101+y*7+x*3)%251 for x in range(width))
                at=plane['offset']+y*plane['stride']
                payload[at:at+width]=row
        r.uc.mem_write(PIXELS,bytes(payload))
        r.mapped_capacity=length
        r.uc.mem_write(DATA,b'synthetic.raw\0')
        r.map_failure=failure=='map'
        r.file_open_failure=failure=='open'
        r.max_write=7 if failure=='short' else None
        result=r.run('dump_frame_to_file',[DATA,FRAME,0]) & 0xffffffff
        signed=result-(1<<32) if result&(1<<31) else result
        success=failure not in ('map','open')
        require((signed==0 and r.output==payload) if success else (signed<0 and not r.output),
                'original_export_case_failed_'+label)
        require(bytes(r.uc.mem_read(PIXELS,length))==bytes(payload),'synthetic_input_modified')
        if success:
            require(r.calls['duss_hal_mem_map']==1 and r.calls['synthetic_memory_backend_map']==1,
                    'original_HAL_mapping_dispatch_not_reached')
            require(r.calls['duss_hal_mem_unmap']==1,'unmap_not_reached')
            require(len(r.syncs)==2,'unexpected_cache_sync_sequence')
        cases.append(dict(case=label,width=width,height=height,alignment=alignment,
                          original_format_enum=fmt,planes=rows,allocation_bytes=length,
                          original_export_return=signed,exported_bytes=len(r.output),
                          fwrite_calls=len(r.writes),original_export_instructions=r.count,
                          byte_exact_including_padding=bool(success and r.output==payload),
                          output_sha256=hashlib.sha256(r.output).hexdigest(),
                          input_unchanged=True,expected_failure=not success,
                          platform_calls=dict(r.calls),cache_sync_requests=r.syncs))
    return dict(schema='hasselblad-stage41g-original-pixel-export-v1',
                status='PASS_original_ARM64_exporter_synthetic_NV12',cases=cases,
                source_sha256=PIN,original_code_emulated=True,
                runtime_versions=dict(unicorn=unicorn.__version__,capstone=capstone.__version__,
                                      pyelftools=elftools.__version__),
                original_functions=['duss_pixel_format_from_str','frame_buffer_plane_info_generate',
                                    'dump_frame_to_file','_fwrite_data','duss_hal_mem_map'],
                platform_memory_backend_and_stdio_simulated=True,
                cache_operations_simulated=True,physical_camera_accessed=False,
                actual_camera_pixels_obtained=False,MAIN_CCM_pixel_oracle_proven=False,
                vendor_bytes_exported=False,private_photographs_accessed=False,
                source_plane_padding_is_preserved=True,
                boundary='This verifies an original pixel reader with synthetic backing memory, not camera capture or firmware colour rendering.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--lib-root',type=Path,required=True)
    p.add_argument('--probe-format',default=None)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.probe_format:
        r=OfflineExporter(a.lib_root)
        r.uc.mem_write(DATA,a.probe_format.encode()+b'\0')
        status=r.run('duss_pixel_format_from_str',[DATA,DATA+0x800])
        value=struct.unpack('<I',r.uc.mem_read(DATA+0x800,4))[0]
        print(json.dumps({'input':a.probe_format,'enum':value,'status':status,
                          'matching_names':[x for x in r.strings_compared if any(k in x.lower() for k in ['nv12','nv21','420','422'])],
                          'instructions':r.count}))
    else:
        require(a.output is not None,'output_required')
        report=run_cases(a.lib_root)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'status':report['status'],'cases':len(report['cases']),
                          'actual_camera_pixels_obtained':False}))

if __name__=='__main__':main()
