#!/usr/bin/env python3
"""Audit the user-supplied IMaH tool against private X2D II DSP containers.

Requires an unmodified, separately obtained GPL-3.0-or-later upstream tool.
This wrapper contains no vendor code, vendor key bytes, or firmware payloads.
All attempted plaintext is temporary; failed output is never accepted as code.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import types

from Crypto.Hash import SHA256
from Crypto.Signature import pss
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import numpy as np

UPSTREAM_COMMIT = '195692263c2684cf1ddc4995f2736be6c0fb135e'
UPSTREAM_SHA256 = '955c6798f3e42b07799358208b390e9c5f167479f3a6b81e06f482d200146b9d'
FILENAMES = ('ask_dsp.img', 'ss_dsp0.fw', 'ss_dsp1.fw', 'ss_dsp2.fw')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checksum(data):
    padded = data + bytes((-len(data)) % 4)
    return int(np.frombuffer(padded, dtype='<u4').sum(dtype=np.uint64)) & 0xffffffff


def aes(key, mode, data, encrypt=False):
    cipher = Cipher(algorithms.AES(key), mode)
    operation = cipher.encryptor() if encrypt else cipher.decryptor()
    return operation.update(data) + operation.finalize()


def parse(data):
    if len(data) < 192 or data[:4] != b'IM*H':
        raise ValueError('Missing IMaH header')
    u32 = lambda offset: struct.unpack_from('<I', data, offset)[0]
    n, header_size, signature_size, payload_size = (u32(o) for o in (156, 16, 20, 24))
    if u32(4) != 2 or header_size != 192 + 32 * n or signature_size not in (256, 384):
        raise ValueError('Unsupported layout for this bounded v2 audit')
    total = header_size + signature_size + payload_size
    if total != len(data) or u32(8) != total or u32(28) != total or data[34] != 0:
        raise ValueError('Unexpected length or compression')
    chunks, expected_offset = [], 0
    for i in range(n):
        cid, offset, size, attrib, address = struct.unpack_from('<4sIIIQ', data, 192 + 32 * i)
        name = cid.rstrip(b'\0').decode('ascii')
        padded = size + (-size) % 32
        if not re.fullmatch(r'[A-Za-z0-9]{1,4}', name) or offset != expected_offset or attrib & 1:
            raise ValueError('Audit requires safe chunk names and contiguous encrypted chunks')
        expected_offset = offset + padded
        chunks.append({'id': name, 'offset': offset, 'size': size, 'padded_size': padded,
                       'attrib': attrib, 'load_address': f'0x{address:08x}'})
    if expected_offset != payload_size:
        raise ValueError('Unexpected payload gaps/trailer')
    payload = data[header_size + signature_size:]
    no_checksum = bytearray(data[:header_size])
    struct.pack_into('<I', no_checksum, 108, 0)
    return {
        'version': u32(4), 'auth_algorithm': u32(36), 'header_size': header_size,
        'reserved_field_nonzero': any(data[12:16]),
        'reserved2_field_nonzero': any(data[112:128]),
        'signature_size': signature_size, 'payload_size': payload_size,
        'auth_id': data[40:44].rstrip(b'\0').decode('ascii'),
        'encryption_id': data[44:48].rstrip(b'\0').decode('ascii'),
        'chunks': chunks, 'payload_digest_matches': hashlib.sha256(payload).digest() == data[160:192],
        'encrypted_checksum_matches': (-checksum(bytes(no_checksum) + payload) & 0xffffffff) == u32(108),
    }


def decode_independently(data, info, wrapping_key):
    # This uses cryptography/OpenSSL, independently of upstream PyCryptodome.
    # All audited chunks are contiguous and encrypted; no 32-bit counter wrap
    # can occur in these sub-7 MiB payloads. Reject other layouts in parse().
    scramble = aes(wrapping_key, modes.ECB(), data[48:64])
    return aes(scramble, modes.CTR(bytes(16)), data[info['header_size'] + info['signature_size']:])


def options(path, prefix, keys, force=False):
    return types.SimpleNamespace(sigfile=str(path), mdprefix=str(prefix), key_select=keys,
                                 force_continue=force, show_multiple_keys_warn=False, verbose=0)


def signature_trials(module, data, info):
    header = module.ImgPkgHeader.from_buffer_copy(data[:192])
    result = []
    for name in module.keys:
        if not name.startswith(info['auth_id']):
            continue
        key = module.imah_get_auth_params(options('private-input', 'private-output', [name]), header)
        length_matches = key is not None and key.size_in_bytes() == info['signature_size']
        valid = False
        if length_matches:
            try:
                pss.new(key, salt_bytes=32).verify(SHA256.new(data[:info['header_size']]),
                    data[info['header_size']:info['header_size'] + info['signature_size']])
                valid = True
            except (ValueError, TypeError):
                pass
        result.append({'key_name': name, 'signature_length_matches': length_matches,
                       'signature_verifies_under_upstream_algorithm': valid})
    return result


def synthetic_checks(module):
    """Known-answer positive and rejection cases for the original extractor."""
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    wrapping_key, scramble = bytes(range(16)), bytes(range(16, 32))
    plains = [bytes((j * 17 + i) % 256 for j in range(n)) for i, n in enumerate((17, 48, 65, 100))]
    plain = b''.join(x + bytes((-len(x)) % 32) for x in plains)
    payload = aes(scramble, modes.CTR(bytes(16)), plain, encrypt=True)
    h = module.ImgPkgHeader()
    h.magic, h.header_version, h.header_size, h.signature_size = b'IM*H', 2, 320, 384
    h.payload_size, h.size, h.target_size = len(payload), 704 + len(payload), 704 + len(payload)
    h.auth_alg, h.auth_key, h.enc_key = 0x40003, b'SYNA', b'SYNE'
    h.name, h.type, h.date, h.chunk_num = b'synthetic', b'TEST', 0x20261023, 4
    h.scram_key[:] = aes(wrapping_key, modes.ECB(), scramble, encrypt=True)
    h.plain_cksum = checksum(plain)
    h.payload_digest[:] = hashlib.sha256(payload).digest()
    chunks, offset = [], 0
    for name, value in zip((b'CODI', b'DATI', b'CODE', b'DATE'), plains):
        c = module.ImgChunkHeader()
        c.id, c.offset, c.size, c.attrib = name, offset, len(value), 0
        chunks.append(c)
        offset += len(value) + (-len(value)) % 32
    chunk_bytes = b''.join(bytes(c) for c in chunks)
    h.encr_cksum = -checksum(bytes(h) + chunk_bytes + payload) & 0xffffffff
    header = bytes(h) + chunk_bytes
    signature = signing_key.sign(header, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
    data = header + signature + payload
    module.keys['SYNA'] = signing_key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode('ascii')
    module.keys['SYNE'] = wrapping_key
    outcomes = {}
    try:
        with tempfile.TemporaryDirectory(prefix='imah41r-synthetic-') as name:
            root = Path(name); image = root / 'fixture.img'; image.write_bytes(data)
            po = options(image, root / 'valid', [])
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with image.open('rb') as f:
                    module.imah_unsign(po, f)
            assert [p.read_bytes() for p in [root / f'valid_{n}.bin' for n in ('CODI','DATI','CODE','DATE')]] == plains
            info = parse(data)
            assert decode_independently(data, info, wrapping_key) == plain
            assert info['payload_digest_matches'] and info['encrypted_checksum_matches']
            outcomes['valid_signed_encrypted_fixture_extracts_exactly'] = True
            module.keys['SYNE'] = bytes([wrapping_key[0] ^ 1]) + wrapping_key[1:]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    with image.open('rb') as f:
                        module.imah_unsign(options(image, root / 'wrong', []), f)
                except ValueError as ex:
                    assert str(ex) == 'Decrypted chunks checksum verification failed.'
                    outcomes['wrong_key_rejected_by_plaintext_checksum'] = True
            assert outcomes.get('wrong_key_rejected_by_plaintext_checksum')
            corrupt = data[:-1] + bytes([data[-1] ^ 1])
            corrupt_info = parse(corrupt)
            assert not corrupt_info['payload_digest_matches'] and not corrupt_info['encrypted_checksum_matches']
            outcomes['corrupted_ciphertext_rejected_by_both_integrity_checks'] = True
    finally:
        del module.keys['SYNA'], module.keys['SYNE']
    return outcomes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upstream-tool', type=Path, required=True)
    ap.add_argument('--firmware-root', type=Path, required=True)
    ap.add_argument('--private-dir', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    tool = args.upstream_tool.resolve()
    assert sha(tool.read_bytes()) == UPSTREAM_SHA256, 'Unpinned upstream source'
    spec = importlib.util.spec_from_file_location('imah41r_upstream', tool)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    args.private_dir.mkdir(parents=True, exist_ok=True)
    output = {'schema': 'hasselblad-stage41r-imah-key-compatibility-v1',
        'upstream_repository': 'https://github.com/o-gs/dji-firmware-tools',
        'upstream_commit': UPSTREAM_COMMIT, 'upstream_tool_sha256': UPSTREAM_SHA256,
        'synthetic_checks': synthetic_checks(module), 'files': [],
        'scope': 'Offline data extraction only. No vendor firmware execution/signing, device access or flashing. Only the synthetic test fixture is signed.',
        'signature_warning': 'Ciphertext integrity and plaintext checksum are not substitutes for a verified signature.',
        'production_photo_output_changed': False, 'main_pixel_equation_recovered': False}
    for filename in FILENAMES:
        source = args.firmware_root / 'vendor/firmware/dspf' / filename
        original = source.read_bytes(); source_hash = sha(original)
        info = parse(original)
        assert info['payload_digest_matches'] and info['encrypted_checksum_matches']
        auth = signature_trials(module, original, info)
        compatible_length = [r['key_name'] for r in auth if r['signature_length_matches']]
        assert compatible_length
        enc_names = [k for k in module.keys if k.startswith(info['encryption_id'])]
        row = {'file': filename, 'source_sha256': source_hash, 'bytes': len(original), **info,
               'authentication_trials': auth, 'encryption_trials': []}
        with tempfile.TemporaryDirectory(prefix='imah41r-', dir=args.private_dir) as temp:
            work = Path(temp); image = work / filename; shutil.copyfile(source, image)
            base_command = [sys.executable, str(tool), '-u', '-k', compatible_length[0], '-i', str(image)]
            strict = subprocess.run(base_command + ['-k', enc_names[0], '-m', str(work / 'strict')],
                                    capture_output=True, text=True, timeout=60)
            (args.private_dir / f'{filename}.strict.log').write_text(strict.stdout + strict.stderr)
            row['unmodified_tool_strict_exit'] = strict.returncode
            row['strict_signature_failure_reported'] = 'Image file head signature verification failed.' in strict.stderr
            for enc in enc_names:
                trial = work / enc; trial.mkdir()
                prefix = trial / 'out'
                run = subprocess.run(base_command + ['-k', enc, '-f', '-m', str(prefix)],
                                     capture_output=True, text=True, timeout=60)
                log = run.stdout + run.stderr
                (args.private_dir / f'{filename}.{enc}.log').write_text(log)
                plain = decode_independently(original, info, module.keys[enc])
                matches = checksum(plain) == struct.unpack_from('<I', original, 152)[0]
                counts = {}
                for chunk in info['chunks']:
                    name = chunk['id']; occurrence = counts.get(name, 0)
                    counts[name] = occurrence + 1
                    # Mirrors upstream duplicate chunk output naming, not data.
                    suffix = name if occurrence == 0 else name + chr(96 + occurrence)
                    recovered = (trial / f'out_{suffix}.bin').read_bytes()
                    assert recovered == plain[chunk['offset']:chunk['offset'] + chunk['size']]
                warning = 'Decrypted chunks checksum verification failed.' in log
                assert warning != matches
                row['encryption_trials'].append({'key_name': enc,
                    'forced_tool_exit': run.returncode,
                    'tool_plaintext_checksum_failure_reported': warning,
                    'independent_plaintext_checksum_matches': matches,
                    'independent_decode_matches_all_upstream_chunk_bytes': True,
                    'accepted_as_decrypted_code': False})
                # Deliberately remove this run's unvalidated outputs and derived
                # per-image keys; only logs and aggregate receipts survive.
                shutil.rmtree(trial)
            assert sha(image.read_bytes()) == source_hash
        assert sha(source.read_bytes()) == source_hash
        row['original_unchanged'] = True
        output['files'].append(row)
        print(json.dumps({'file': filename, 'strict_exit': strict.returncode,
              'matching_encryption_keys': [r['key_name'] for r in row['encryption_trials'] if r['independent_plaintext_checksum_matches']],
              'crosschecked_trials': len(row['encryption_trials'])}), flush=True)
    assert sha(tool.read_bytes()) == UPSTREAM_SHA256
    output['upstream_tool_unchanged'] = True
    output['all_originals_unchanged'] = True
    output['validated_decrypted_payloads'] = 0
    assert not any(r['independent_plaintext_checksum_matches'] for f in output['files'] for r in f['encryption_trials']), 'Positive result requires a new, separately reviewed analysis'
    args.receipt.write_text(json.dumps(output, indent=2) + '\n')


if __name__ == '__main__':
    main()
