#!/usr/bin/env python3
"""Bounded original-source search for MAIN pixel operations and simulation routes.

This is a static audit, not an ISP replay or pixel-parity test. The output
contains hashes, function relationships and structural test metadata only.
"""
import argparse,collections,hashlib,json,struct,sys
from importlib.metadata import version
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
from elftools.elf.elffile import ELFFile

HERE=Path(__file__).resolve().parent
for sibling in ['isp_knee_stage41m','isp_knee_stage41n','isp_liveview_stage41']:
    sys.path.insert(0,str(HERE.parent/sibling))
from replay_main_gamma41n import original_symbols
from inspect_original_liveview_xrefs41b import code_slice
from inspect_original_sbpc_processing41c import parse_plt

PINS={
 'librcam.so':'3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66',
 'libdcam_pp.so':'bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9',
 'libdcam_pp_base.so':'72934142975fa88ee65e331767e8b9badd9ca40bc987e3c9a2a5cf0ff60b3f76',
}


def branch_destination(word,address):
    """Decode only AArch64 immediate B/BL; other instructions return None."""
    if word>>26 not in (0b000101,0b100101):return None
    offset=word&0x3ffffff
    if offset&(1<<25):offset-=1<<26
    return address+4*offset


class Source:
    def __init__(self,path):
        self.path=path;self.sha=hashlib.sha256(path.read_bytes()).hexdigest()
        assert self.sha==PINS[path.name],'wrong original source'
        self.file=path.open('rb');self.elf=ELFFile(self.file)
        self.symbols=original_symbols(path)
        self.names={a:n for n,(a,z) in self.symbols.items()}
        self.plt,valid=parse_plt(self.elf);assert valid
        self.md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);self.md.detail=True

    def instructions(self,name):
        a,z=self.symbols[name]
        return list(self.md.disasm(code_slice(self.elf,a,z),a))

    def info(self,name):
        a,z=self.symbols[name];calls=collections.Counter();indirect=[]
        for i in self.instructions(name):
            if i.mnemonic in ['bl','b'] and i.operands[0].type==ARM64_OP_IMM:
                target=i.operands[0].imm
                if not a<=target<a+z:
                    calls[self.plt.get(target,self.names.get(target,hex(target)))]+=1
            if i.mnemonic in ['blr','br']:indirect.append(hex(i.address))
        return {'start':hex(a),'bytes':z,
                'code_sha256':hashlib.sha256(code_slice(self.elf,a,z)).hexdigest(),
                'external_direct_calls_or_tail_branches':dict(sorted(calls.items())),
                'indirect_call_or_branch_sites':indirect}

    def call(self,caller,callee):
        result=[]
        for i in self.instructions(caller):
            if i.mnemonic not in ['bl','b'] or i.operands[0].type!=ARM64_OP_IMM:continue
            a=i.operands[0].imm
            if self.plt.get(a,self.names.get(a))==callee:result.append(hex(i.address))
        assert result,(caller,callee)
        return {'caller':caller,'callee':callee,'sites':result}


def register_readers(source):
    """Exact immediate callers of one known getter, not a colour-name sweep."""
    section=source.elf.get_section_by_name('.text');data=section.data();base=int(section['sh_addr'])
    target=source.symbols['DjiIsp_Reg_Get'][0];sites=[];owners=collections.defaultdict(list)
    functions=[(a,a+z,n) for n,(a,z) in source.symbols.items() if z]
    for offset in range(0,len(data)-3,4):
        word=struct.unpack_from('<I',data,offset)[0];at=base+offset
        if branch_destination(word,at)!=target:continue
        decoded=list(source.md.disasm(data[offset:offset+4],at))
        assert len(decoded)==1 and decoded[0].mnemonic in ['b','bl']
        assert decoded[0].operands[0].imm==target
        containing=[n for lo,hi,n in functions if lo<=at<hi]
        assert len(containing)==1,(hex(at),containing)
        sites.append(at);owners[containing[0]].append(hex(at))
    assert len(sites)==90 and len(owners)==10
    return {'target':'DjiIsp_Reg_Get','call_sites':len(sites),'containing_functions':len(owners),
        'owners':[{'function':n,'sites':s} for n,s in sorted(owners.items())],
        'scope':'Immediate B/BL references in original librcam .text; indirect calls, direct buffer reads and other binaries are not excluded.',
        'pixel_evaluator_demonstrated':False}


def installed_callbacks(source):
    """Resolve address constructions stored in the DSP device callback object.

    This narrow block precedes any call and has only straight-line address
    construction/stores. No instruction bytes are exported.
    """
    regs={};slots={};start=0x57d4c;end=0x57dd0
    for i in source.instructions('pp_create_dsp_frwk_dev_ctx'):
        if not start<=i.address<end:continue
        o=i.operands
        if i.mnemonic=='adrp':
            regs[i.reg_name(o[0].reg)]=o[1].imm
        elif i.mnemonic=='add' and len(o)==3 and o[1].type==ARM64_OP_REG and o[2].type==ARM64_OP_IMM:
            dst=i.reg_name(o[0].reg);src=i.reg_name(o[1].reg)
            if src in regs:regs[dst]=regs[src]+(o[2].imm<<o[2].shift.value)
            else:regs.pop(dst,None)
        elif i.mnemonic=='stp' and o[2].type==ARM64_OP_MEM and i.reg_name(o[2].mem.base)=='x20':
            for j in range(2):
                target=regs.get(i.reg_name(o[j].reg))
                assert target in source.names
                slots[o[2].mem.disp+8*j]={'target':source.names[target],'store_site':hex(i.address)}
        elif i.mnemonic in ['bl','blr','b','br']:
            raise AssertionError('unexpected control flow in pointer construction')
        else:
            for reg in i.regs_access()[1]:regs.pop(i.reg_name(reg),None)
    expected={0x10:'_pp_dsp_frwk_buf_trans',0x28:'_pp_dsp_frwk_process',
              0x30:'_pp_dsp_frwk_wait',0x40:'_pp_dsp_frwk_pull_buf'}
    assert all(slots[k]['target']==v for k,v in expected.items())
    return {hex(k):slots[k] for k in expected}


def simulation_indirect_calls(source,slots):
    ins=source.instructions('proc_e2_subp_sim');out=[]
    for idx,i in enumerate(ins):
        if i.mnemonic!='blr':continue
        assert i.op_str=='x8'
        candidates=[]
        for p in reversed(ins[max(0,idx-8):idx]):
            if p.mnemonic=='ldr' and p.operands[0].type==ARM64_OP_REG and p.reg_name(p.operands[0].reg)=='x8':
                mem=p.operands[1];assert mem.type==ARM64_OP_MEM and p.reg_name(mem.mem.base)=='x21'
                candidates=[mem.mem.disp];break
        assert len(candidates)==1
        offset=hex(candidates[0]);assert offset in slots
        out.append({'site':hex(i.address),'device_callback_offset':offset,'target':slots[offset]['target']})
    assert len(out)==4
    return out


def test_definitions(root):
    directory=root/'system/etc/ppt';basenames={p.name for p in root.rglob('*') if p.is_file()}
    out={}
    for module in ['e2_subp_sim','gamma','gamma_reverse']:
        recipe_path=directory/(module+'-data_set_0-stress_test.json')
        param_path=directory/(module+'-data_set_0-stress_param_0.json')
        recipe=json.loads(recipe_path.read_text());params=json.loads(param_path.read_text())
        body=params['e2_subp_sim' if module=='e2_subp_sim' else 'gamma']
        names=recipe['input']['file_name']
        out[module]={'recipe_sha256':hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
            'parameter_file_sha256':hashlib.sha256(param_path.read_bytes()).hexdigest(),
            'declared_platform':recipe['platform'],'input_count':len(names),
            'input_formats':recipe['input']['format'],
            'referenced_inputs_present_by_basename':[Path(n).name in basenames for n in names],
            'has_cmodel_tag':'cmodel_tag' in params,'has_crc_field':'crc' in params,
            'parameter_fields':sorted(body)}
        if module=='e2_subp_sim':
            out[module]['ccm_coefficient_count']=len(body['ccm']['lmtx'])
            out[module]['gamma_entry_count']=len(body['gam']['lut'])
            out[module]['negative_gamma_entry_count']=len(body['gam']['minus_lut'])
        else:
            out[module]['gamma_entry_count']=len(body['gamma_lut'])
            out[module]['negative_gamma_entry_count']=len(body['gamma_minus_lut'])
        assert recipe['platform']=='PP_PLATFORM_DSP_FRWK'
    assert out['e2_subp_sim']['ccm_coefficient_count']==9
    return out


def self_test():
    cases=[(0x94000001,0x1000,0x1004),(0x97ffffff,0x1000,0xffc),
           (0x14000002,0x1000,0x1008),(0x17fffffe,0x1000,0xff8),
           (0xd503201f,0x1000,None),(0xd63f0100,0x1000,None)]
    for word,at,want in cases:assert branch_destination(word,at)==want
    return len(cases)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--firmware-root',type=Path)
    ap.add_argument('--output',type=Path);ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
    if a.self_test:print(json.dumps({'branch_decoder_cases':self_test(),'passed':True}));return
    assert a.firmware_root and a.output
    sources={n:Source(a.firmware_root/'system/lib64'/n) for n in PINS}
    rcam=sources['librcam.so'];pp=sources['libdcam_pp.so'];base=sources['libdcam_pp_base.so']
    selected={
       'librcam.so':['_ColorMatrix_Func','DjiMetadata_ProresRaw_GetCcmByCct','tmc_v1_0_calc_tmc'],
       'libdcam_pp.so':['e2_subp_sim_init','e2_subp_sim','proc_e2_subp_sim','e2_subp_sim_ceva_buf_trans'],
       'libdcam_pp_base.so':['pp_create_platform_ctx','_create_platform_ctx_base','pp_create_dsp_frwk_dev_ctx',
           '_pp_dsp_frwk_buf_trans','_pp_dsp_frwk_process','_pp_dsp_frwk_sl_process',
           '_pp_dsp_frwk_wait','_pp_dsp_frwk_pull_buf','pp_call_ss_function_client']}
    slots=installed_callbacks(base)
    edges=[pp.call('e2_subp_sim','proc_e2_subp_sim'),pp.call('e2_subp_sim_init','pp_create_platform_ctx'),
        base.call('pp_create_platform_ctx','_create_platform_ctx_base'),
        base.call('_create_platform_ctx_base','pp_create_dsp_frwk_dev_ctx'),
        base.call('_pp_dsp_frwk_process','_pp_dsp_frwk_sl_process'),
        base.call('_pp_dsp_frwk_sl_process','pp_call_ss_function_client'),
        base.call('pp_call_ss_function_client','ss_dsp_function_client_call')]
    out={'schema':'hasselblad-stage41p-pixel-consumer-audit-v1','static_audit_only':True,
        'pixel_equation_recovered':False,'original_pixel_execution_performed':False,
        'physical_hardware_accessed':False,'production_photo_output_changed':False,
        'vendor_bytes_tuning_disassembly_exported':False,'source_sha256':PINS,
        'runtime':{'python':sys.version.split()[0],**{n:version(n) for n in ['capstone','pyelftools']}},
        'branch_decoder_synthetic_cases':self_test(),'register_reader_trace':register_readers(rcam),
        'simulation_test_definitions':test_definitions(a.firmware_root),
        'simulation_callback_slots':slots,'simulation_indirect_calls':simulation_indirect_calls(pp,slots),
        'simulation_verified_direct_edges':edges,
        'functions':{file:{n:sources[file].info(n) for n in names} for file,names in selected.items()},
        'limits':['The direct getter trace does not exclude indirect or direct-buffer consumers.',
            'The SUB simulation uses a nine-coefficient CCM; equivalence to the six-coefficient MAIN block is not established.',
            'The traced simulation process dispatches through an SS DSP function client; its remote pixel body is not recovered.',
            'TMC gamma resampling and ProRes metadata matrix preparation are not established MAIN hardware pixel evaluators.',
            'Four end-to-end RAW/JPEG pairs do not isolate the MAIN stages or their active register state.']}
    for source in sources.values():assert hashlib.sha256(source.path.read_bytes()).hexdigest()==source.sha
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'original_function_bodies_inspected':sum(map(len,selected.values())),
        'direct_register_get_call_sites':out['register_reader_trace']['call_sites'],
        'resolved_simulation_callbacks':len(out['simulation_indirect_calls']),
        'verified_direct_edges':len(edges),'pixel_equation_recovered':False}))


if __name__=='__main__':main()
