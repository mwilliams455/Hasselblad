#!/usr/bin/env python3
"""Verify X2D II container signatures with the public key in bootarea.img.

Reads private firmware; exports structural facts and aggregate checks only.
No key bytes, firmware bytes, disassembly or candidate plaintext are exported.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import zipfile
from importlib.metadata import version

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'isp_dsp_stage41r'))
from audit_imah41r import parse, options, UPSTREAM_SHA256, UPSTREAM_COMMIT

BOOT_SHA = '0fb41e070f52cf6e0e6f36f6cce1b5d20bb8c2512afb73dcdcf7f38ce6d8d9e5'
KEY_RECORD_SHA = '8335ac87baa1465a4d04805ce660f801d9eadaaf46f933f75f6f8e7ebfcfa080'
PINS = {
 'vendor/firmware/dspf/ask_dsp.img': 'bc64b8862f5e0eb2026eb90e20c6efb3e6d31ee2934bd20d93656747fde40128',
 'vendor/firmware/dspf/ss_dsp0.fw': '5dd6da299227bca0d4bf3c1e92482ebcebf709216fc1e1e9efde8bd2cfab5344',
 'vendor/firmware/dspf/ss_dsp1.fw': '03f08813e18b577219986495c653b8ad1b58ed9edaad10ffb86cab4c29890572',
 'vendor/firmware/dspf/ss_dsp2.fw': '037fdd1476fcb0d738b1ce0f5933d8ddd64ce0a87862e0209dda394e5c6d8b5f',
 'vendor/ta/09db16c0-873b-4fed-b87ea5d2b86293a2.ta': '69433f4aca40dde5b950d80e232489e5ff4e9bd0dfa1b72332a8a565e6fcde0b',
 'vendor/ta/e91c9402-64a0-470f-88e7bf5d3c606b6a.ta': '9a271b4c8f62c1e3e7de07bd7ae58b06ed3ed89deb15d26194d78a9cedf15db4',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def public_key(boot):
    words, n0inv = struct.unpack_from('<II', boot)
    assert words == 96
    n = int.from_bytes(boot[8:8+4*words], 'little')
    rr = int.from_bytes(boot[8+4*words:8+8*words], 'little')
    e = struct.unpack_from('<I', boot, 8+8*words)[0]
    record = boot[:12+8*words]
    assert sha(record) == KEY_RECORD_SHA
    assert n.bit_length() == 3072 and e == 65537
    assert (n0inv*n+1) % (1 << 32) == 0
    assert rr == pow(2, 64*words, n)
    pycrypto = RSA.construct((n, e))
    openssl = rsa.RSAPublicNumbers(e, n).public_key()
    spki = openssl.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return record, pycrypto, openssl, {
        'file_offset': 0, 'record_bytes': len(record), 'modulus_bits': n.bit_length(),
        'exponent': e, 'record_sha256': sha(record), 'spki_sha256': sha(spki),
        'montgomery_n0inv_matches': True, 'montgomery_rr_matches': True,
        'contains_private_key': False}


def verifies(key, header, signature, backend):
    try:
        if backend == 'pycryptodome':
            pss.new(key, salt_bytes=32).verify(SHA256.new(header), signature)
        else:
            key.verify(signature, header,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
        return True
    except (ValueError, InvalidSignature):
        return False


def changed(data, at):
    out = bytearray(data)
    out[at] ^= 1
    return bytes(out)


def verify_container(label, data, keys, module):
    info = parse(data)
    h, z = info['header_size'], info['signature_size']
    header, signature = data[:h], data[h:h+z]
    checks = {}
    for backend, key in keys.items():
        assert verifies(key, header, signature, backend)
        assert not verifies(key, changed(header, 64), signature, backend)
        assert not verifies(key, header, changed(signature, 0), backend)
        checks[backend] = {'original_signature_passes': True,
            'modified_header_rejected': True, 'modified_signature_rejected': True}
    assert info['payload_digest_matches'] and info['encrypted_checksum_matches']
    altered_payload = changed(data, len(data)-1)
    altered_info = parse(altered_payload)
    assert not altered_info['payload_digest_matches'] and not altered_info['encrypted_checksum_matches']
    # The header signature is unchanged by a payload-only edit. The signed
    # digest is what binds the payload; validate both, not the signature alone.
    assert all(verifies(k, altered_payload[:h], altered_payload[h:h+z], backend)
               for backend, k in keys.items())
    with tempfile.TemporaryDirectory(prefix='stage41t-strict-') as tmp:
        root = Path(tmp)
        source = root/'input.img'
        source.write_bytes(data)
        po = options(source, root/'out', ['PRAK-X2DII-1.3.16.2', 'TBIE-2021-08'], force=False)
        po.verbose = 2
        out, err = io.StringIO(), io.StringIO()
        reason = None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                with source.open('rb') as stream:
                    module.imah_unsign(po, stream)
            except ValueError as exc:
                reason = str(exc)
        signature_pass = 'Image file head signature verification passed.' in out.getvalue()
        assert signature_pass and reason == 'Decrypted chunks checksum verification failed.'
        reserved_warning = "Header field 'reserved' is non-zero" in err.getvalue()
        assert sha(source.read_bytes()) == sha(data)
        # Context cleanup removes all attempted plaintext and generated INIs.
    return {'label': label, 'source_sha256': sha(data), 'bytes': len(data),
        'header_bytes': h, 'signature_bytes': z, 'auth_id': info['auth_id'],
        'encryption_id': info['encryption_id'], 'signature_scheme': 'RSA-PSS/SHA256/MGF1-SHA256/salt32',
        'verification': checks, 'original_payload_digest_matches': True,
        'original_encrypted_checksum_matches': True,
        'payload_only_mutation': {'header_signature_still_passes': True,
            'payload_digest_rejects': True, 'encrypted_checksum_rejects': True},
        'upstream_strict_check': {'force_continue': False, 'signature_pass_reported': signature_pass,
            'encryption_variant': 'TBIE-2021-08', 'stopped_at': reason,
            'reserved_field_warning': reserved_warning},
        'validated_plaintext_recovered': False}


def boot_layout(boot):
    ranges = [(0, 780, 'RSA_public_record'), (780, 1024, 'unclassified_prefix_tail'),
        (1024, 210368, 'encrypted_IMaH_bootloader'), (210368, 229376, 'zero_padding'),
        (229376, 230176, 'PLI_partition_table'), (230176, 233472, 'zero_padding'),
        (233472, 234112, 'encrypted_IMaH_board_info'), (234112, 262144, 'zero_padding'),
        (262144, 557056, 'zero_extended_16bit_values_in_32bit_slots')]
    rows = []
    cursor = 0
    for start, end, kind in ranges:
        assert start == cursor
        block = boot[start:end]
        if kind == 'zero_padding':
            assert not any(block)
        rows.append({'offset': start, 'bytes': len(block), 'classification': kind,
            'sha256': sha(block), 'nonzero_bytes': sum(x != 0 for x in block)})
        cursor = end
    assert cursor == len(boot)
    table = boot[0x38000:0x38320]
    magic, reserved, size, count, *tail = struct.unpack_from('<8I', table)
    assert magic == int.from_bytes(b'PL*I', 'little') and reserved == 0
    assert size == len(table) == 800 and count == 16 and tail == [0]*4
    area_names, partition_names = [], []
    for lo, hi, target in [(32, 288, area_names), (288, 800, partition_names)]:
        for offset in range(lo, hi, 32):
            name = table[offset+16:offset+32].split(b'\0', 1)[0]
            if name:
                assert all(32 <= x < 127 for x in name)
                target.append(name.decode('ascii'))
    assert area_names == ['userarea', 'bootarea'] and len(partition_names) == count
    values = struct.unpack('<'+str((len(boot)-0x40000)//4)+'I', boot[0x40000:])
    assert all(x <= 0xffff for x in values)
    pages = []
    for offset in range(0x40000, len(boot), 4096):
        data = boot[offset:offset+4096]
        if any(data):
            pages.append(offset)
    runs = []
    for page in pages:
        if runs and runs[-1]['end'] == page:
            runs[-1]['end'] += 4096
        else:
            runs.append({'start': page, 'end': page+4096})
    return {'complete_byte_coverage': True, 'regions': rows,
        'partition_table': {'offset': 0x38000, 'bytes': size, 'declared_partition_count': count,
            'area_names': area_names, 'partition_names': partition_names,
            'numeric_field_units_not_established': True},
        'tail_storage': {'offset': 0x40000, 'u32_slots': len(values),
            'all_upper_16bits_zero': True, 'nonzero_page_runs': runs,
            'instruction_set_identified': False, 'function_identified': False,
            'decryption_or_MAIN_ISP_code_established': False}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--firmware-root', type=Path, required=True)
    ap.add_argument('--ota', type=Path, required=True)
    ap.add_argument('--upstream-tool', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    tool = args.upstream_tool.resolve()
    assert sha(tool.read_bytes()) == UPSTREAM_SHA256
    with zipfile.ZipFile(args.ota) as archive:
        boot, tos = archive.read('bootarea.img'), archive.read('tos.img')
    assert sha(boot) == BOOT_SHA
    assert sha(tos) == '6a92ba4e36a286a9e372599ff76419a0c6258721cc5583269d60fba55c0b927b'
    record, pycrypto, openssl, key_info = public_key(boot)
    spec = importlib.util.spec_from_file_location('stage41t_upstream', tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundled_matches = []
    for name in [n for n in module.keys if n.startswith('PRAK')]:
        header = module.ImgPkgHeader.from_buffer_copy(tos[:192])
        candidate = module.imah_get_auth_params(options('input', 'out', [name]), header)
        if candidate and candidate.n == pycrypto.n and candidate.e == pycrypto.e:
            bundled_matches.append(name)
    assert not bundled_matches
    key_info['matching_bundled_PRAK_variants'] = bundled_matches
    module.keys['PRAK-X2DII-1.3.16.2'] = record
    inputs = []
    for name, pin in PINS.items():
        data = (args.firmware_root/name).read_bytes()
        assert sha(data) == pin
        inputs.append((name, data))
    inputs.append(('OTA/tos.img', tos))
    for offset in [1024, 233472]:
        size = struct.unpack_from('<I', boot, offset+8)[0]
        inputs.append((f'OTA/bootarea.img@{offset}', boot[offset:offset+size]))
    keys = {'pycryptodome': pycrypto, 'cryptography_openssl': openssl}
    try:
        rows = [verify_container(name, data, keys, module) for name, data in inputs]
    finally:
        del module.keys['PRAK-X2DII-1.3.16.2']
    for name, pin in PINS.items():
        assert sha((args.firmware_root/name).read_bytes()) == pin
    assert sha(tool.read_bytes()) == UPSTREAM_SHA256
    result = {'schema': 'hasselblad-stage41t-embedded-public-key-audit-v1',
        'bootarea_sha256': BOOT_SHA, 'public_key': key_info, 'boot_layout': boot_layout(boot),
        'containers': rows, 'verified_containers': len(rows),
        'independent_crypto_backends': 2, 'upstream_strict_signature_passes': len(rows),
        'upstream_tool_sha256': UPSTREAM_SHA256, 'upstream_commit': UPSTREAM_COMMIT,
        'runtime': {n: version(n) for n in ['cryptography', 'pycryptodome', 'numpy']},
        'trust_scope': 'Signatures verify against the public key embedded in this same firmware package. No independent manufacturer trust anchor or live-device fuse comparison is asserted.',
        'encryption_key_recovered': False, 'decrypted_DSP_or_TEE_recovered': False,
        'main_pixel_equation_recovered': False, 'production_rendering_changed': False,
        'hardware_accessed': False, 'vendor_code_executed': False,
        'original_inputs_and_upstream_source_unchanged': True,
        'private_key_material_or_vendor_payload_exported': False}
    args.receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'verified_containers': len(rows), 'crypto_backends': 2,
        'strict_signature_passes': len(rows), 'strict_stops_at_plaintext_checksum': len(rows),
        'embedded_public_key_spki_sha256': key_info['spki_sha256'],
        'bootarea_complete_coverage': result['boot_layout']['complete_byte_coverage'],
        'encryption_key_recovered': False}))


if __name__ == '__main__':
    main()
