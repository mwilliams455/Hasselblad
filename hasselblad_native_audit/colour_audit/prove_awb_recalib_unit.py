#!/usr/bin/env python3
"""Execute one ABI-audited X2D II AWB leaf's original ARM64 instructions.

Requires a user-supplied, exact-hash libaaa.so. No firmware/code is bundled.
This establishes a tiny Q12 calibration operation, not an HNCS image renderer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ, UC_MEM_WRITE
from unicorn import arm64_const as reg

LIB_SHA256 = '7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba'
SYMBOL = 'scene_awb_result_recalib_unit'
VA, SIZE = 0x4a39a0, 56
DATA, STACK, STOP = 0x10000000, 0x20000000, 0x30000000
PAGE = 4096
CASES = [
    ('q12_unity', 4096, 4096, 4096, 4096),
    ('independent_channel_scales', 8192, 12288, 8192, 6144),
    ('fractional_truncation', 5001, 6001, 3000, 5000),
    ('one_q12_half_one_q12_double', 4096, 4096, 2048, 8192),
    ('zero_gain', 0, 0, 4096, 4096),
    ('bounded_maximum_gain', 65535, 65535, 4096, 8192),
    ('first_divisor_zero', 8192, 6144, 0, 4096),
    ('second_divisor_zero', 8192, 6144, 4096, 0),
    ('both_divisors_zero', 8192, 6144, 0, 0),
]


def audited_code(path):
    with path.open('rb') as f:
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
        if sha != LIB_SHA256:
            raise ValueError(f'Unsupported firmware library hash: {sha}')
        f.seek(0)
        elf = ELFFile(f)
        if elf.elfclass != 64 or elf['e_machine'] != 'EM_AARCH64' or not elf.little_endian:
            raise ValueError('Expected little-endian ELF64 AArch64')
        symbols = [s for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name == SYMBOL]
        if len(symbols) != 1 or symbols[0]['st_value'] != VA or symbols[0]['st_size'] != SIZE:
            raise ValueError('Audited symbol identity/extent mismatch')
        text = elf.get_section_by_name('.text')
        offset = VA - text['sh_addr']
        code = text.data()[offset:offset+SIZE]
        instructions = list(Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN).disasm(code, VA))
        if len(code) != SIZE or len(instructions) != SIZE//4:
            raise ValueError('Disassembly is incomplete')
        if any(i.mnemonic in ('bl', 'blr', 'br') for i in instructions):
            raise ValueError('Unexpected non-leaf control transfer')
        return code, [{"va": hex(i.address), "mnemonic": i.mnemonic, "operands": i.op_str} for i in instructions]


def execute_case(code, case):
    name, gain_a, gain_b, calib_a, calib_b = case
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    codepage = VA & ~(PAGE-1)
    uc.mem_map(codepage, PAGE, UC_PROT_READ|UC_PROT_EXEC)
    uc.mem_write(VA, code)
    uc.mem_map(DATA, PAGE, UC_PROT_READ|UC_PROT_WRITE)
    uc.mem_map(STACK, PAGE, UC_PROT_READ|UC_PROT_WRITE)
    uc.mem_map(STOP, PAGE, UC_PROT_READ|UC_PROT_EXEC)
    before = bytearray(b'\xa5' * PAGE)
    ptr_a, ptr_b = DATA+0x100, DATA+0x200
    struct.pack_into('<I', before, ptr_a-DATA, gain_a)
    struct.pack_into('<I', before, ptr_b-DATA, gain_b)
    uc.mem_write(DATA, bytes(before))
    for number, value in enumerate((ptr_a,ptr_b,calib_a,calib_b)):
        uc.reg_write(getattr(reg,f'UC_ARM64_REG_X{number}'),value)
    uc.reg_write(reg.UC_ARM64_REG_SP, STACK+PAGE-16)
    uc.reg_write(reg.UC_ARM64_REG_LR, STOP)
    saved={getattr(reg,f'UC_ARM64_REG_X{i}'):0x7000000000000000+i for i in range(19,30)}
    for r,v in saved.items():
        uc.reg_write(r,v)
    trace, accesses=[],[]
    def instruction_hook(machine,address,size,user):
        if not (VA <= address < VA+SIZE) or size != 4:
            raise RuntimeError(f'Execution outside audited function at {address:#x}')
        trace.append(address)
    def memory_hook(machine,access,address,size,value,user):
        if address not in (ptr_a,ptr_b) or size != 4:
            raise RuntimeError(f'Unexpected memory access at {address:#x}, {size} bytes')
        accesses.append({'kind':'read' if access == UC_MEM_READ else 'write','pointer':'a' if address==ptr_a else 'b','bytes':size})
    uc.hook_add(UC_HOOK_CODE,instruction_hook)
    uc.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory_hook)
    uc.emu_start(VA,STOP,timeout=100000,count=32)
    if uc.reg_read(reg.UC_ARM64_REG_PC)!=STOP:
        raise RuntimeError('Instruction/time bound exhausted without return')
    status=uc.reg_read(reg.UC_ARM64_REG_W0)
    actual=bytes(uc.mem_read(DATA,PAGE))
    out_a=struct.unpack_from('<I',actual,ptr_a-DATA)[0]
    out_b=struct.unpack_from('<I',actual,ptr_b-DATA)[0]
    expected=bytearray(before)
    if calib_a == 0 or calib_b == 0:
        expected_status,expected_a,expected_b=89,gain_a,gain_b
    else:
        expected_status=0
        expected_a=((gain_a<<12)&0xffffffff)//calib_a
        expected_b=((gain_b<<12)&0xffffffff)//calib_b
        struct.pack_into('<I',expected,ptr_a-DATA,expected_a)
        struct.pack_into('<I',expected,ptr_b-DATA,expected_b)
    assert (status,out_a,out_b)==(expected_status,expected_a,expected_b),(name,status,out_a,out_b)
    assert actual==bytes(expected),'Data changed outside the two audited uint32 cells'
    assert all(uc.reg_read(r)==v for r,v in saved.items()),'Callee-saved register changed'
    assert uc.reg_read(reg.UC_ARM64_REG_SP)==STACK+PAGE-16,'Stack pointer changed'
    return {'name':name,'input':{'gain_a':gain_a,'gain_b':gain_b,'calib_a':calib_a,'calib_b':calib_b},'status':status,'output':[out_a,out_b],'instructions_executed':len(trace),'instruction_vas':[hex(a) for a in trace],'memory_accesses':accesses,'result':'pass','guard_bytes_unchanged':True,'callee_saved_registers_unchanged':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('library',type=Path)
    p.add_argument('output',type=Path)
    args=p.parse_args()
    code,disassembly=audited_code(args.library)
    cases=[execute_case(code,case) for case in CASES]
    coverage=sorted({va for c in cases for va in c['instruction_vas']},key=lambda x:int(x,16))
    report={
        'firmware':'Hasselblad X2D II 100C 1.3.16.2',
        'library':'libaaa.so','library_sha256':LIB_SHA256,
        'symbol':SYMBOL,'symbol_va':hex(VA),'symbol_size':SIZE,
        'function_code_sha256':hashlib.sha256(code).hexdigest(),
        'method':'Unicorn AArch64 execution of exact original leaf instructions; no replacement function and no dependency stubs',
        'abi':'uint32_t scene_awb_result_recalib_unit(uint32_t *gain_a_inout, uint32_t *gain_b_inout, uint32_t calib_a, uint32_t calib_b)',
        'preconditions':'Two valid, distinct, aligned writable uint32 cells; for useful calibration calib_a/calib_b>0. Harness bounds gains to 0..65535. Original shifts wrap at uint32 width; larger inputs require separate adapter guards.',
        'memory_model':'Only function code, guarded input/output page and private stack page are mapped. No firmware globals, dependency symbols, callbacks or system calls are present.',
        'limits':'Proves only an AWB Q12 calibration leaf. Does not run scene_awb_lib_run, derive sensor-specific calibration, render RAW or establish HNCS.',
        'caller_evidence':[
            {'symbol':'scene_awb_get_result','calls':['0x465dc8','0x465df8'],'evidence':'x0/x1 point to separate 4-byte stack cells; w2/w3 loaded from calibration context; return checked with cbnz; outputs read as 32-bit cells.'},
            {'symbol':'scene_awb_get_recalib_res','calls':['0x474f94','0x474fc4','0x475000','0x475018'],'evidence':'Scalar divisors selected from per-unit/e-ND calibration context; outputs fed to further Q12 WB normalization with unity0x1000.'}
        ],
        'disassembly':disassembly,'cases':cases,'case_count':len(cases),'all_passed':True,
        'unique_instructions_executed':len(coverage),'total_function_instructions':SIZE//4,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'symbol':SYMBOL,'cases_passed':len(cases),'unique_instructions_executed':len(coverage),'total_function_instructions':SIZE//4,'output':str(args.output)}))


if __name__=='__main__':
    main()
