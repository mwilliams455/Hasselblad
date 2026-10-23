#!/usr/bin/env python3
"""Stage41F: bounded, non-executing ownership audit of the Stage41E table.

Export symbol/relocation/control-flow metadata only, never vendor bytes or
arbitrary strings. No frame acquisition or claim of MAIN CCM pixel equivalence.
"""
from __future__ import annotations
import argparse, hashlib, io, json, lzma, struct, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'isp_liveview_stage41'))
from inspect_original_liveview_xrefs41b import PIN, ARCHIVE_SHA, require, sha, code_slice
from inspect_original_sbpc_pointer41e import SAFE_SYMBOL, in_section, relocations_for_label
from inspect_original_sbpc_processing41c import parse_plt

SOURCE = 'system/bin/camera-service'
SLOT = 0x8cd170
LABEL_VA = 0x6c3d63
PRINTER = '_ZNK13DCAMContainer5printEb'
MAX_DEBUG = 64 * 1024 * 1024


def all_symbols(elf):
    """Keep provenance and OBJECT symbols, including bounded mini-debug data."""
    from elftools.elf.elffile import ELFFile
    tables = [(name, elf.get_section_by_name(name)) for name in ('.dynsym', '.symtab')]
    sec = elf.get_section_by_name('.gnu_debugdata')
    if sec:
        require(int(sec['sh_size']) <= MAX_DEBUG, 'compressed_debug_oversize')
        dec = lzma.LZMADecompressor(memlimit=4 * MAX_DEBUG)
        data = dec.decompress(sec.data(), max_length=MAX_DEBUG + 1)
        require(dec.eof and len(data) <= MAX_DEBUG, 'debug_expansion_limit')
        debug = ELFFile(io.BytesIO(data))
        tables.append(('.gnu_debugdata/.symtab', debug.get_section_by_name('.symtab')))
    rows = []
    for source, table in tables:
        if table is None:
            continue
        for sym in table.iter_symbols():
            if sym['st_shndx'] == 'SHN_UNDEF' or not SAFE_SYMBOL.fullmatch(sym.name):
                continue
            kind = sym['st_info']['type']
            if kind not in ('STT_FUNC', 'STT_OBJECT', 'STT_NOTYPE'):
                continue
            rows.append(dict(name=sym.name, start=int(sym['st_value']),
                             size=int(sym['st_size']), kind=kind, symbol_table=source))
    return rows


def owners(rows, addr, kind=None):
    result = [dict(name=r['name'], symbol_table=r['symbol_table'], kind=r['kind'],
                   start_va=hex(r['start']), size=r['size'], offset=addr-r['start'])
              for r in rows if (kind is None or r['kind'] == kind)
              and r['size'] and r['start'] <= addr < r['start']+r['size']]
    return sorted(result, key=lambda x:(x['size'], x['name'], x['symbol_table']))[:24]


def relocations(elf):
    from elftools.elf.relocation import RelocationSection
    result = []
    for sec in elf.iter_sections():
        if isinstance(sec, RelocationSection):
            for r in sec.iter_relocations():
                if r.is_RELA():
                    result.append(dict(site=int(r['r_offset']), target=int(r['r_addend']),
                                       kind=int(r['r_info_type']), section=sec.name))
    return result


def pointer_run(elf, rels, slot):
    by_site = {r['site']:r for r in rels if r['kind'] == 1027}
    def valid(at):
        return at in by_site and in_section(elf, by_site[at]['target']) == '.rodata'
    require(valid(slot), 'anchor_not_rodata_pointer')
    lo = hi = slot
    for _ in range(256):
        if not valid(lo-8): break
        lo -= 8
    for _ in range(256):
        if not valid(hi+8): break
        hi += 8
    require(not valid(lo-8) and not valid(hi+8), 'pointer_run_exceeds_bound')
    return lo, hi+8


def reg_key(ins, reg):
    name = ins.reg_name(reg)
    if name == 'fp': return 'x29'
    if name == 'lr': return 'x30'
    if name.startswith('w') and name[1:].isdigit(): return 'x'+name[1:]
    return name


def address_uses(instructions, lo, hi):
    """Conservative straight-line address tracking; never cross a branch/call.

    Memory indices remain unknown. An indexed load from a known table base is
    reported as such, not as a proven load of the label's particular element.
    """
    from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG, ARM64_OP_MEM
    state = {}
    found = []
    for ins in instructions:
        ops = ins.operands
        m = ins.mnemonic
        dest = None
        value = None
        if m in ('adrp', 'adr') and len(ops) == 2 and ops[1].type == ARM64_OP_IMM:
            dest = reg_key(ins, ops[0].reg)
            value = int(ops[1].imm)
        elif m in ('add', 'sub') and len(ops) == 3 and ops[1].type == ARM64_OP_REG and ops[2].type == ARM64_OP_IMM:
            base = state.get(reg_key(ins, ops[1].reg))
            if base is not None and ins.reg_name(ops[0].reg).startswith('x'):
                shift = int(ops[2].shift.value)
                value = base + (1 if m == 'add' else -1) * (int(ops[2].imm) << shift)
                dest = reg_key(ins, ops[0].reg)
        elif m == 'mov' and len(ops) == 2 and ops[1].type == ARM64_OP_REG and ins.reg_name(ops[0].reg).startswith('x'):
            dest = reg_key(ins, ops[0].reg)
            value = state.get(reg_key(ins, ops[1].reg))
        for op in ops:
            if op.type != ARM64_OP_MEM:
                continue
            base = state.get(reg_key(ins, op.mem.base))
            if base is None:
                continue
            at = base + int(op.mem.disp)
            if lo <= at < hi:
                indexed = bool(op.mem.index)
                found.append(dict(instruction_va=hex(ins.address), kind='indexed_memory' if indexed else 'fixed_memory',
                                  base_or_effective_va=hex(at), offset_from_label_slot=at-SLOT,
                                  exact_label_slot_access=at == SLOT and not indexed,
                                  index_register=ins.reg_name(op.mem.index) if indexed else None,
                                  index_shift=int(op.shift.value) if indexed else None,
                                  operation=m))
        # Any write, including a W-register alias or replacement ADRP, kills the old value.
        _, writes = ins.regs_access()
        for reg in writes:
            state.pop(reg_key(ins, reg), None)
        if dest is not None and value is not None:
            state[dest] = value
            if m != 'adrp' and lo <= value < hi:
                found.append(dict(instruction_va=hex(ins.address), kind='formed_address',
                                  base_or_effective_va=hex(value), offset_from_label_slot=value-SLOT,
                                  exact_label_slot_access=False, operation=m))
        if m in ('bl', 'blr', 'b', 'br', 'ret', 'cbz', 'cbnz', 'tbz', 'tbnz') or m.startswith('b.'):
            state.clear()
    return found


def disassembler():
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    cs = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    cs.detail = True
    return cs


def sign_extend(n, bits):
    return n-(1 << bits) if n & (1 << (bits-1)) else n


def narrow_code_refs(elf, rows, lo, hi, selected_starts):
    """One fixed-word target pass, decode only matching PC-relative windows.

    This is not the prior all-instruction ELF sweep. It targets this data range
    and selected function starts only. No indirect-reference completeness claim.
    """
    sec = elf.get_section_by_name('.text')
    raw = sec.data()
    start = int(sec['sh_addr'])
    require(0 < len(raw) <= 64*1024*1024 and len(raw)%4 == 0, 'invalid_text_extent')
    cs = disassembler()
    refs = []
    calls = []
    seeds = 0
    pages = set(range(lo & ~4095, ((hi-1) & ~4095)+1, 4096))
    for i, (word,) in enumerate(struct.iter_unpack('<I', raw)):
        pc = start+i*4
        seed = False
        if word & 0x9f000000 == 0x90000000:  # ADRP
            imm = sign_extend(((word >> 5) & 0x7ffff)*4+((word >> 29)&3), 21)
            seed = (pc & ~4095)+(imm << 12) in pages
        elif word & 0x9f000000 == 0x10000000:  # ADR
            imm = sign_extend(((word >> 5) & 0x7ffff)*4+((word >> 29)&3), 21)
            seed = lo <= pc+imm < hi
        elif word & 0xfc000000 in (0x94000000, 0x14000000):
            target = pc + 4*sign_extend(word & 0x3ffffff, 26)
            if target in selected_starts:
                calls.append(dict(site_va=hex(pc), target_va=hex(target),
                                  kind='BL' if word & 0x80000000 else 'B',
                                  owners=owners(rows, pc, 'STT_FUNC')))
        if not seed:
            continue
        seeds += 1
        require(seeds <= 2048, 'too_many_target_page_seeds')
        fn = owners(rows, pc, 'STT_FUNC')
        end = min(pc+128, start+len(raw))
        if fn:
            end = min(end, int(fn[0]['start_va'], 16)+fn[0]['size'])
        insns = []
        for ins in cs.disasm(raw[i*4:i*4+end-pc], pc):
            insns.append(ins)
            if ins.mnemonic in ('bl','blr','b','br','ret','cbz','cbnz','tbz','tbnz') or ins.mnemonic.startswith('b.'):
                break
        for ref in address_uses(insns, lo, hi):
            ref['owners'] = owners(rows, int(ref['instruction_va'],16), 'STT_FUNC')
            refs.append(ref)
    dedup = {json.dumps(x, sort_keys=True):x for x in refs}
    require(len(dedup) <= 128 and len(calls) <= 128, 'reference_output_bound_exceeded')
    return dict(method='targeted_A64_word_decode_then_128_byte_straight_line_windows',
                matching_PC_relative_seeds=seeds, address_references=list(dedup.values()),
                direct_selected_function_references=calls,
                indirect_or_cross_basic_block_references_complete=False)


def inspect(root):
    from elftools.elf.elffile import ELFFile
    from capstone.arm64 import ARM64_OP_IMM
    require((root/'system/etc/VERSION').read_text().strip() == '1.3.16.2', 'wrong_version')
    path = root/SOURCE
    require(sha(path) == PIN[SOURCE], 'wrong_original_camera_service_hash')
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        require(elf['e_machine'] == 'EM_AARCH64', 'wrong_architecture')
        anchor = relocations_for_label(elf, LABEL_VA)
        require(len(anchor) == 1 and anchor[0]['site_va'] == SLOT and anchor[0]['reloc_type'] == 1027,
                'stage41e_anchor_mismatch')
        rd = elf.get_section_by_name('.rodata')
        off = LABEL_VA-int(rd['sh_addr'])
        label = b'liveview_after_sbpc\0'
        require(rd.data()[off:off+len(label)] == label, 'original_label_mismatch')
        rows = all_symbols(elf)
        rels = relocations(elf)
        lo, hi = pointer_run(elf, rels, SLOT)
        bysite = {r['site']:r for r in rels}
        executable = []
        selected = {}
        for delta in (32,40,48,56,64):
            r = bysite[SLOT+delta]
            require(r['kind'] == 1027 and in_section(elf,r['target']) == '.text', 'neighbor_contract_changed')
            own = owners(rows,r['target'],'STT_FUNC')
            executable.append(dict(offset_from_label_slot=delta, target_va=hex(r['target']),
                                   relocation_kind=r['kind'], owners=own,
                                   exact_function_entry=any(o['offset'] == 0 for o in own)))
            for o in own: selected[int(o['start_va'],16)] = o
        for r in rows:
            if r['name'] == PRINTER and r['kind'] == 'STT_FUNC':
                selected[r['start']] = dict(name=r['name'],start_va=hex(r['start']),size=r['size'])
        plt, plt_ok = parse_plt(elf)
        functions = []
        cs = disassembler()
        for start, row in sorted(selected.items()):
            require(4 <= row['size'] <= 64*1024, 'selected_function_oversize')
            code = code_slice(elf,start,row['size'])
            insns = list(cs.disasm(code,start))
            require(len(insns)*4 == len(code), 'incomplete_selected_decode')
            direct = Counter()
            indirect = []
            for ins in insns:
                if ins.mnemonic == 'bl' and ins.operands[0].type == ARM64_OP_IMM:
                    target = int(ins.operands[0].imm)
                    own = owners(rows,target,'STT_FUNC')
                    name = plt.get(target) or (own[0]['name'] if own else 'unresolved')
                    direct[name] += 1
                elif ins.mnemonic in ('br','blr'):
                    indirect.append(dict(site_va=hex(ins.address), kind=ins.mnemonic))
            functions.append(dict(name=row['name'],start_va=hex(start),size=len(code),
                                  code_sha256=hashlib.sha256(code).hexdigest(),
                                  direct_callees=[dict(name=n,count=c) for n,c in sorted(direct.items())[:64]],
                                  direct_callees_truncated=len(direct)>64,
                                  indirect_transfers=indirect,
                                  table_refs=address_uses(insns,lo,SLOT+72)))
        data_refs = [dict(site_va=hex(r['site']),target_va=hex(r['target']),kind=r['kind'],
                          source_section=in_section(elf,r['site']),
                          owners=owners(rows,r['site'],'STT_OBJECT'))
                     for r in rels if r['kind'] == 1027 and lo <= r['target'] < SLOT+72]
        require(len(data_refs) <= 128, 'data_reference_bound_exceeded')
        neighborhood = [dict(name=r['name'],kind=r['kind'],start_va=hex(r['start']),size=r['size'],
                             symbol_table=r['symbol_table'],offset_from_label_slot=r['start']-SLOT)
                        for r in rows if r['kind'] != 'STT_FUNC' and lo-64 <= r['start'] < SLOT+128]
        require(len(neighborhood)<=128, 'symbol_neighborhood_bound_exceeded')
        return dict(schema='hasselblad-stage41f-original-table-ownership-v1',
                    status='PASS_exact_original_table_ownership_audit',source_sha256=PIN[SOURCE],
                    archive_sha256=ARCHIVE_SHA,label_slot_va=hex(SLOT),
                    label_slot_object_owners=owners(rows,SLOT,'STT_OBJECT'),
                    neighboring_named_data_symbols=neighborhood,
                    contiguous_rodata_pointer_run=dict(start_va=hex(lo),end_exclusive_va=hex(hi),
                        pointer_count=(hi-lo)//8,label_index=(SLOT-lo)//8,
                        same_high_level_object_proven=False),
                    executable_neighbors=executable,selected_functions=functions,
                    PLT_mapping_validated=plt_ok,
                    reverse_data_relocations=data_refs,
                    targeted_code_references=narrow_code_refs(elf,rows,lo,SLOT+72,set(selected)),
                    active_frame_producer_proven=False,MAIN_CCM_pixel_oracle_proven=False,
                    original_camera_or_DSP_executed=False,vendor_bytes_or_raw_strings_exported=False,
                    Photon_photo_renderer_modified=False)


def synthetic():
    # Original-authored AArch64 fixtures: no vendor instructions.
    from inspect_original_sbpc_pointer41e import code_uses_pointer
    cs = disassembler()
    base = 0x1000
    page = SLOT & ~4095
    imm = (page-(base & ~4095)) >> 12
    adrp = 0x90000000 | ((imm & 3)<<29) | (((imm>>2)&0x7ffff)<<5)
    add = 0x91000001 | ((SLOT-page)<<10)  # add x1,x0,#offset
    def decoded(words):
        return list(cs.disasm(struct.pack('<'+'I'*len(words),*words),base))
    def hits(words):
        return address_uses(decoded(words),SLOT,SLOT+8)
    cases = {}
    cases['valid_adrp_add'] = bool(hits([adrp,add]))
    cases['overwrite_x0_rejected'] = not hits([adrp,0xd2800000,add])
    cases['overwrite_w0_rejected'] = not hits([adrp,0x52800000,add])
    cases['replacement_adrp_rejected'] = not hits([adrp,0x90000000,add])
    cases['call_boundary_rejected'] = not hits([adrp,0x94000010,add])
    cases['branch_boundary_rejected'] = not hits([adrp,0x14000002,add])
    cases['copy_x_register_preserved'] = bool(hits([adrp,0xaa0003e2,add+(2<<5)]))
    # The old implementation incorrectly reports this overwritten register.
    raw = struct.pack('<III',adrp,0xd2800000,add)
    class Section:
        def __getitem__(self,k): return {'sh_addr':base,'sh_size':len(raw)}[k]
        def data(self): return raw
    class Elf:
        def get_section_by_name(self,n): return Section() if n == '.text' else None
    old = code_uses_pointer(Elf(),[{'site_va':SLOT}],{'fixture':(base,len(raw))})
    cases['stage41e_false_positive_reproduced'] = old['candidate_count'] == 1
    examples = [{'name':'table','start':100,'size':24,'kind':'STT_OBJECT','symbol_table':'.gnu_debugdata/.symtab'}]
    cases['object_start_inclusive'] = len(owners(examples,100,'STT_OBJECT')) == 1
    cases['object_end_exclusive'] = not owners(examples,124,'STT_OBJECT')
    cases['function_type_not_invented'] = not owners(examples,108,'STT_FUNC')
    cases['signed_branch_offsets'] = sign_extend(0x3ffffff,26) == -1
    require(all(cases.values()), 'synthetic_failure_'+','.join(k for k,v in cases.items() if not v))
    return dict(status='PASS_synthetic',checks=len(cases),results=cases,
                stage41e_stale_register_bug_reproduced=True,original_firmware_loaded=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    d = synthetic() if a.self_test else inspect(a.firmware_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':d['status'],'checks':d.get('checks'),
                      'label_object_owners':d.get('label_slot_object_owners'),
                      'executable_neighbors':d.get('executable_neighbors'),
                      'MAIN_CCM_pixel_oracle_proven':False},sort_keys=True))


if __name__ == '__main__':
    main()
