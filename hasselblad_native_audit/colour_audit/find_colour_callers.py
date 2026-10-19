#!/usr/bin/env python3
"""Find direct AArch64 calls to exact ELF symbols/PLT entries, read-only."""
import argparse
import bisect
import struct
from pathlib import Path
from disassemble_colour import all_symbols, Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, ELFFile


def run(path, names, context):
    with path.open('rb') as source:
        elf = ELFFile(source)
        syms = all_symbols(elf)
        funcs = sorted((s['st_value'], s.name) for s in syms if s['st_info']['type']=='STT_FUNC' and s['st_value'])
        starts = [x[0] for x in funcs]
        targets = {s['st_value']:s.name for s in syms if s.name in names}
        dyn = elf.get_section_by_name('.dynsym')
        plt = elf.get_section_by_name('.plt')
        rel = elf.get_section_by_name('.rela.plt')
        labels = {s['st_value']:s.name for s in syms if s['st_value']}
        if rel and dyn and plt:
            for i, item in enumerate(rel.iter_relocations()):
                name = dyn.get_symbol(item['r_info_sym']).name
                address = plt['sh_addr'] + 32 + 16 * i
                labels[address] = name + '@plt'
                if name in names:
                    targets[address] = name + '@plt'
        text = elf.get_section_by_name('.text')
        data = text.data()
        base = text['sh_addr']
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        for i in range(0, len(data)-3, 4):
            word = struct.unpack_from('<I',data,i)[0]
            if word & 0x7c000000 != 0x14000000:
                continue
            imm = word & 0x3ffffff
            if imm & 0x2000000:
                imm -= 0x4000000
            target = base+i+imm*4
            if target not in targets:
                continue
            idx = bisect.bisect_right(starts,base+i)-1
            owner = funcs[idx] if idx>=0 else (0,'?')
            print(f'\n{base+i:#x} -> {targets[target]} in {owner[1]} + {base+i-owner[0]:#x}')
            lo=max(0,i-context*4)
            hi=min(len(data),i+(context+1)*4)
            for ins in md.disasm(data[lo:hi],base+lo):
                label=''
                if ins.mnemonic in ('bl','b') and ins.op_str.startswith('#'):
                    label=labels.get(int(ins.op_str[1:],0),'')
                print(f'{ins.address:08x} {ins.mnemonic:8s} {ins.op_str:40s} {label}')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('elf', type=Path)
    p.add_argument('symbols',nargs='+')
    p.add_argument('--context',type=int,default=12)
    a=p.parse_args()
    run(a.elf,a.symbols,a.context)
