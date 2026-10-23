#!/usr/bin/env python3
"""Trace private X2D II DSP loading to its TEE service.

Exports structural evidence only. Emulation executes the readable client glue
with synthetic arguments and stubbed TEE calls; it does not decrypt firmware.
Upstream key material is obtained separately and is never copied into output.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import uuid
import zipfile
from importlib.metadata import version

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5,
    UC_ARM64_REG_X6, UC_ARM64_REG_X7, UC_ARM64_REG_X30, UC_ARM64_REG_SP,
    UC_ARM64_REG_PC, UC_ARM64_REG_TPIDR_EL0)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'isp_dsp_stage41r'))
from audit_imah41r import (parse, checksum, decode_independently,
    signature_trials, UPSTREAM_SHA256, UPSTREAM_COMMIT)

PINS = {
 'system/bin/ss_dsp_manager': '8b380e916f46f8fec9d974eb93ee5196c1d3abce16b9765c3a547a8d345e50fe',
 'system/lib64/libfw_util.so': '3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d',
 'system/lib64/libfw_util_ca.so': '96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b',
 'system/lib64/libteec.so': '351c0ced2cef7cf80cc5926b2ec4d06c583d7eb91832fd9d7589d91ab38e683c',
}
TA_NAME = '09db16c0-873b-4fed-b87ea5d2b86293a2.ta'
TA_UUID = '09db16c0-873b-4fed-b87e-a5d2b86293a2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Source:
    def __init__(self, path):
        self.path = path
        self.data = path.read_bytes()
        self.elf = ELFFile(io.BytesIO(self.data))
        assert self.elf['e_machine'] == 'EM_AARCH64'
        self.syms, self.plt = {}, {}
        gd = self.elf.get_section_by_name('.gnu_debugdata')
        tables = [self.elf]
        if gd:
            tables.append(ELFFile(io.BytesIO(lzma.decompress(gd.data()))))
        for elf in tables:
            for section in elf.iter_sections():
                if isinstance(section, SymbolTableSection):
                    for s in section.iter_symbols():
                        if s['st_info']['type'] == 'STT_FUNC' and s['st_shndx'] != 'SHN_UNDEF':
                            self.syms[s.name] = (s['st_value'], s['st_size'])
        self.names = {a: n for n, (a, _) in self.syms.items()}
        rel = self.elf.get_section_by_name('.rela.plt')
        plt = self.elf.get_section_by_name('.plt')
        assert rel is not None and plt is not None
        rs = list(rel.iter_relocations())
        assert plt['sh_size'] == 32 + 16 * len(rs)
        table = self.elf.get_section(rel['sh_link'])
        self.plt = {plt['sh_addr'] + 32 + 16*i: table.get_symbol(r['r_info_sym']).name
                    for i, r in enumerate(rs)}
        self.md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.md.detail = True
        # Check each ordinal against the GOT slot actually loaded by its stub.
        for i, relocation in enumerate(rs):
            address = plt['sh_addr']+32+16*i
            stub = list(self.md.disasm(self.read(address, 16), address))
            assert [x.mnemonic for x in stub] == ['adrp', 'ldr', 'add', 'br']
            assert stub[0].operands[1].imm+stub[1].operands[1].mem.disp == relocation['r_offset']

    def read(self, address, size):
        for s in self.elf.iter_sections():
            if s['sh_type'] != 'SHT_NOBITS' and s['sh_addr'] <= address and address+size <= s['sh_addr']+s['sh_size']:
                return s.data()[address-s['sh_addr']:address-s['sh_addr']+size]
        raise ValueError('Address outside file-backed sections')

    def instructions(self, name):
        a, z = self.syms[name]
        ins = list(self.md.disasm(self.read(a, z), a))
        assert len(ins)*4 == z
        return ins

    def calls(self, name):
        start, size = self.syms[name]
        calls = []
        for i in self.instructions(name):
            if i.mnemonic not in ('b', 'bl') or i.operands[0].type != ARM64_OP_IMM:
                continue
            dst = i.operands[0].imm
            if start <= dst < start+size:
                continue
            calls.append({'site': hex(i.address), 'target': self.plt.get(dst, self.names.get(dst, hex(dst)))})
        return calls

    def receipt(self, selected):
        dynamic = self.elf.get_section_by_name('.dynamic')
        return {'sha256': sha(self.data), 'bytes': len(self.data),
            'needed': [t.needed for t in dynamic.iter_tags() if t.entry.d_tag == 'DT_NEEDED'],
            'functions': {n: {'address': hex(self.syms[n][0]), 'bytes': self.syms[n][1],
                'code_sha256': sha(self.read(*self.syms[n])), 'calls': self.calls(n)} for n in selected}}


def emulate_client(source, invoke_result):
    """Run original fw_util_load with TEE and libc imports intercepted."""
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    base, aux = 0x10000000, 0x30000000
    segments = [s for s in source.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    end = max(s['p_vaddr'] + s['p_memsz'] for s in segments)
    uc.mem_map(base, (end + 4095) & ~4095)
    for s in segments:
        uc.mem_write(base+s['p_vaddr'], s.data())
    uc.mem_map(aux, 0x100000)
    sentinel, tag, buffer = aux+0xff000, aux+0x3000, aux+0x4000
    uc.mem_write(tag, b'dspimage\0')
    uc.reg_write(UC_ARM64_REG_SP, aux+0xf0000)
    uc.reg_write(UC_ARM64_REG_TPIDR_EL0, aux+0x1000)
    uc.reg_write(UC_ARM64_REG_X30, sentinel)
    xregs = [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3,
             UC_ARM64_REG_X4, UC_ARM64_REG_X5, UC_ARM64_REG_X6, UC_ARM64_REG_X7]
    # Deliberately synthetic fd, size and scalar values, not camera inputs.
    for r, value in zip(xregs, [77, 4096, tag, 0x1234, 0x5678]):
        uc.reg_write(r, value)
    result = {'stubbed_tee_result': hex(invoke_result), 'calls': []}
    u32 = lambda p: struct.unpack('<I', uc.mem_read(p, 4))[0]
    u64 = lambda p: struct.unpack('<Q', uc.mem_read(p, 8))[0]

    def hook(u, address, size, _):
        if address == sentinel:
            u.emu_stop()
            return
        name = source.plt.get(address-base)
        if name is None:
            return
        args = [u.reg_read(r) for r in xregs]
        result['calls'].append(name)
        ret = 0
        if name == 'TEEC_OpenSession':
            result['ta_uuid'] = str(uuid.UUID(bytes_le=bytes(u.mem_read(args[2], 16))))
        elif name == 'TEEC_RegisterSharedMemoryFileDescriptor':
            result['input_fd'] = args[2]
            result['input_size'] = u64(args[1]+8)
            result['input_shared_memory_flags'] = u32(args[1]+16)
        elif name == 'TEEC_AllocateSharedMemory':
            assert u64(args[1]+8) == 32
            u.mem_write(args[1], struct.pack('<Q', buffer))
        elif name == 'memset':
            u.mem_write(args[0], bytes([args[1] & 255])*args[2])
            ret = args[0]
        elif name == 'strncpy':
            assert args[2] == 32
            value = bytes(u.mem_read(args[1], 32)).split(b'\0', 1)[0]
            u.mem_write(args[0], value.ljust(32, b'\0'))
            ret = args[0]
        elif name == 'TEEC_InvokeCommand':
            operation = args[2]
            result['command_id'] = args[1]
            result['parameter_types'] = hex(u32(operation+4))
            result['parameters'] = []
            for i in range(4):
                p = operation+8+24*i
                if i < 2:
                    result['parameters'].append({'size': u64(p+8), 'offset': u64(p+16)})
                else:
                    result['parameters'].append({'a': u32(p), 'b': u32(p+4)})
            result['tag'] = bytes(u.mem_read(buffer, 32)).split(b'\0', 1)[0].decode()
            ret = invoke_result
        elif name not in ('TEEC_InitializeContext', 'TEEC_ReleaseSharedMemory',
                          'TEEC_CloseSession', 'TEEC_FinalizeContext', 'printf_2_console'):
            raise AssertionError('Unexpected external call: '+name)
        u.reg_write(UC_ARM64_REG_X0, ret)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(base+source.syms['fw_util_load'][0], sentinel+4, count=10000)
    assert uc.reg_read(UC_ARM64_REG_PC) == sentinel, 'Emulation did not return'
    result['returned_status'] = hex(uc.reg_read(UC_ARM64_REG_X0) & 0xffffffff)
    assert result['returned_status'] == hex(invoke_result)
    assert result['ta_uuid'] == TA_UUID and result['command_id'] == 1
    assert result['parameter_types'] == '0x11dd' and result['tag'] == 'dspimage'
    assert result['input_fd'] == 77 and result['input_size'] == 4096
    assert result['input_shared_memory_flags'] == 1
    assert result['parameters'] == [{'size': 4096, 'offset': 0}, {'size': 32, 'offset': 0},
                                   {'a': 0x1234, 'b': 0}, {'a': 0x5678, 'b': 0}]
    assert result['calls'].count('TEEC_InvokeCommand') == 1
    assert result['calls'].count('TEEC_ReleaseSharedMemory') == 2
    return result


def check_container(label, data, module, tool):
    info = parse(data)
    assert info['payload_digest_matches'] and info['encrypted_checksum_matches']
    auth = signature_trials(module, data, info)
    compatible = next(r['key_name'] for r in auth if r['signature_length_matches'])
    trials = []
    with tempfile.TemporaryDirectory(prefix='stage41s-') as tmp:
        root = Path(tmp)
        image = root/'input.img'
        image.write_bytes(data)
        for key in [n for n in module.keys if n.startswith(info['encryption_id'])]:
            prefix = root/'output'
            proc = subprocess.run([sys.executable, str(tool), '-u', '-f', '-i', str(image),
                '-m', str(prefix), '-k', compatible, '-k', key], capture_output=True, text=True, timeout=30)
            plain = decode_independently(data, info, module.keys[key])
            matches = checksum(plain) == struct.unpack_from('<I', data, 152)[0]
            assert not matches, 'Positive result requires separate structural validation'
            assert 'Decrypted chunks checksum verification failed.' in proc.stdout+proc.stderr
            for chunk in info['chunks']:
                recovered = (root/('output_'+chunk['id']+'.bin')).read_bytes()
                assert recovered == plain[chunk['offset']:chunk['offset']+chunk['size']]
            trials.append({'key_name': key, 'plaintext_checksum_matches': matches,
                'independent_matches_original_tool': True, 'forced_tool_exit': proc.returncode})
            for p in root.glob('output*'):
                p.unlink()
    return {'label': label, 'sha256': sha(data), 'bytes': len(data), **info,
            'authentication_trials': auth, 'encryption_trials': trials}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--firmware-root', type=Path, required=True)
    ap.add_argument('--ota', type=Path, required=True)
    ap.add_argument('--upstream-tool', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    sources = {n: Source(args.firmware_root/n) for n in PINS}
    for n, pin in PINS.items():
        assert sha(sources[n].data) == pin
    teec_path = 'system/lib64/libteec.so'
    selected = {
      'system/bin/ss_dsp_manager': ['load_IMAGE_dsp_firmware', 'load_IMAGE_e2_ask_dsp_firmware'],
      'system/lib64/libfw_util.so': ['plt_fw_load_file', 'plt_fw_load'],
      'system/lib64/libfw_util_ca.so': ['fw_util_load'],
      teec_path: ['TEEC_InitializeContext', 'TEEC_OpenSession', 'TEEC_InvokeCommand'],
    }
    edges = [
      ('system/bin/ss_dsp_manager', 'load_IMAGE_dsp_firmware', 'plt_fw_load_file', '0x59f0'),
      ('system/bin/ss_dsp_manager', 'load_IMAGE_e2_ask_dsp_firmware', 'plt_fw_load_file', '0x5c3c'),
      ('system/lib64/libfw_util.so', 'plt_fw_load_file', 'fw_util_load', '0x2760'),
      ('system/lib64/libfw_util.so', 'plt_fw_load', 'fw_util_load', '0x2560'),
      ('system/lib64/libfw_util_ca.so', 'fw_util_load', 'TEEC_InvokeCommand', '0x162c'),
      (teec_path, 'TEEC_InvokeCommand', 'ioctl', '0x19dc'),
    ]
    for file, caller, callee, site in edges:
        assert {'site': site, 'target': callee} in sources[file].calls(caller)
    ca = sources['system/lib64/libfw_util_ca.so']
    assert str(uuid.UUID(bytes_le=ca.read(0x2a5c, 16))) == TA_UUID
    assert sources['system/bin/ss_dsp_manager'].read(0x1cbbe, 9) == b'dspimage\0'
    assert b'/dev/tee%zu\0' in sources[teec_path].data and b'optee-tz\0' in sources[teec_path].data
    tool = args.upstream_tool.resolve()
    assert sha(tool.read_bytes()) == UPSTREAM_SHA256
    spec = importlib.util.spec_from_file_location('stage41s_upstream', tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs = [(str(p.relative_to(args.firmware_root)), p.read_bytes())
              for p in sorted((args.firmware_root/'vendor/ta').glob('*.ta'))]
    assert {n for n, _ in inputs} == {'vendor/ta/'+TA_NAME,
        'vendor/ta/e91c9402-64a0-470f-88e7bf5d3c606b6a.ta'}
    ta_hashes = {n: sha(b) for n, b in inputs}
    ota_files = {}
    with zipfile.ZipFile(args.ota) as archive:
        for name in ['tos.img', 'bootarea.img']:
            ota_files[name] = archive.read(name)
    inputs.append(('OTA/tos.img', ota_files['tos.img']))
    boot = ota_files['bootarea.img']
    for offset in [1024, 233472]:
        assert boot[offset:offset+4] == b'IM*H'
        length = struct.unpack_from('<I', boot, offset+8)[0]
        inputs.append((f'OTA/bootarea.img@{offset}', boot[offset:offset+length]))
    containers = [check_container(n, data, module, tool) for n, data in inputs]
    result = {'schema': 'hasselblad-stage41s-tee-loader-audit-v1',
      'sources': {n: sources[n].receipt(names) for n, names in selected.items()},
      'verified_edges': [{'file': f, 'caller': a, 'callee': b, 'site': c} for f, a, b, c in edges],
      'service': {'uuid': TA_UUID, 'matched_file': 'vendor/ta/'+TA_NAME,
          'command_id': 1, 'tag': 'dspimage', 'parameter_types': '0x11dd',
          'parameter_directions': ['registered_memory_input', 'registered_memory_input', 'value_input', 'value_input'],
          'plaintext_return_buffer_on_this_request': False,
          'client_device_path_pattern': '/dev/tee%zu', 'client_backend_name': 'optee-tz'},
      'client_emulation': [emulate_client(ca, status) for status in [0, 0xffff0000]],
      'client_emulation_scope': 'Original readable ARM64 client glue only. Synthetic fd/size/scalars; all TEE and libc imports stubbed. No real TEE or DSP execution and no actual decryption.',
      'encrypted_components': containers,
      'ota_member_hashes': {n: sha(b) for n, b in ota_files.items()},
      'bootarea_scope': 'Two bounded IMaH containers tested at offsets 1024 and 233472. Other bytes in bootarea.img are not classified or ruled out as useful.',
      'upstream_commit': UPSTREAM_COMMIT, 'upstream_sha256': UPSTREAM_SHA256,
      'runtime': {n: version(n) for n in ['capstone', 'pyelftools', 'unicorn', 'cryptography', 'pycryptodome', 'numpy']},
      'validated_decrypted_payloads': 0, 'hardware_accessed': False,
      'production_rendering_changed': False, 'main_pixel_equation_recovered': False,
      'limits': ['The TEE client proves the request boundary, not the internal secure implementation.',
        'Key storage, key derivation, hardware binding, and reserved-field semantics remain unknown.',
        'Encrypted TA and TOS presence does not establish that a physical camera is the only route.',
        'No output memory reference on command 1 does not exclude other commands or secure-side memory writes.',
        'No cryptographic authenticity is established by ciphertext consistency checks.']}
    for s in sources.values():
        assert sha(s.path.read_bytes()) == sha(s.data)
    for name, digest in ta_hashes.items():
        assert sha((args.firmware_root/name).read_bytes()) == digest
    assert sha(tool.read_bytes()) == UPSTREAM_SHA256
    result['original_files_unchanged'] = True
    args.receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'service': result['service'], 'verified_edges': len(edges),
        'new_encrypted_components': len(containers),
        'crosschecked_key_trials': sum(len(c['encryption_trials']) for c in containers),
        'client_emulation_cases_passed': len(result['client_emulation']),
        'validated_decrypted_payloads': 0}))


if __name__ == '__main__':
    main()
