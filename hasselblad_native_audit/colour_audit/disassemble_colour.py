#!/usr/bin/env python3
"""Print selected ELF functions and resolved direct calls; read-only input."""
import argparse
import io
import lzma
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN


def all_symbols(elf):
    out = []
    for name in (".dynsym", ".symtab"):
        sec = elf.get_section_by_name(name)
        if sec and hasattr(sec, "iter_symbols"):
            out.extend(s for s in sec.iter_symbols() if s["st_shndx"] != "SHN_UNDEF" and s.name)
    debug = elf.get_section_by_name(".gnu_debugdata")
    if debug:
        data = lzma.decompress(debug.data())
        if len(data) > 64 * 1024 * 1024:
            raise ValueError("debugdata exceeds analysis bound")
        de = ELFFile(io.BytesIO(data))
        sec = de.get_section_by_name(".symtab")
        if sec and hasattr(sec, "iter_symbols"):
            out.extend(s for s in sec.iter_symbols() if s["st_shndx"] != "SHN_UNDEF" and s.name)
    return out


def run(path, names):
    with path.open("rb") as source:
        elf = ELFFile(source)
        if elf["e_machine"] != "EM_AARCH64":
            raise ValueError("requires AArch64 ELF")
        symbols = all_symbols(elf)
        byname = {s.name: s for s in symbols}
        addresses = {s["st_value"]: s.name for s in symbols if s["st_value"]}
        dynsym = elf.get_section_by_name(".dynsym")
        plt = elf.get_section_by_name(".plt")
        rel = elf.get_section_by_name(".rela.plt")
        if rel and dynsym and plt:
            for i, item in enumerate(rel.iter_relocations()):
                addresses[plt["sh_addr"] + 32 + 16 * i] = dynsym.get_symbol(item["r_info_sym"]).name + "@plt"
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        text = elf.get_section_by_name(".text")
        for name in names:
            symbol = byname[name]
            va, size = symbol["st_value"], symbol["st_size"]
            if not size:
                later = [x for x in addresses if x > va]
                size = min(later) - va if later else 256
            if size > 256 * 1024:
                raise ValueError("function exceeds analysis bound")
            start = va - text["sh_addr"]
            if start < 0 or start + size > text["sh_size"]:
                raise ValueError("function outside .text")
            print(f"\n{name} @ {va:#x}, {size} bytes")
            for ins in md.disasm(text.data()[start:start+size], va):
                annotation = ""
                if ins.mnemonic in ("bl", "b") and ins.op_str.startswith("#"):
                    try:
                        dest = int(ins.op_str[1:], 0)
                        annotation = addresses.get(dest, "")
                    except ValueError:
                        pass
                print(f"{ins.address:08x}  {ins.mnemonic:8s} {ins.op_str:40s} {annotation}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("symbols", nargs="+")
    args = parser.parse_args()
    run(args.elf, args.symbols)
