#!/usr/bin/env python3
"""Reproduce selected X2D II dispatch relationships and DSP container checks.

Reads separately supplied, hash-pinned firmware. Does not execute vendor code,
start services, contact a device, fetch files, or save firmware/plaintext bytes.
Requires pyelftools and capstone; the optional published-key check also requires
cryptography. Public key material is read from a separately supplied, pinned
upstream source file by parsing literal AST nodes, never by executing that file.
"""

import argparse
import ast
import hashlib
import importlib.metadata
import io
import json
import lzma
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG
from elftools.elf.elffile import ELFFile


PINS = {
    "system/lib64/libdcam_pp.so": "bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9",
    "system/lib64/libdcam_pp_base.so": "72934142975fa88ee65e331767e8b9badd9ca40bc987e3c9a2a5cf0ff60b3f76",
    "system/lib64/libdsp_frwk.so": "4d82ab4602c063a52c53250344ea3a55fa6c4502f0a54d90ab8883ed7c5cbfff",
    "system/lib64/libduml_hal.so": "adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20",
    "system/lib64/libfw_util.so": "3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d",
    "system/bin/ss_dsp_manager": "8b380e916f46f8fec9d974eb93ee5196c1d3abce16b9765c3a547a8d345e50fe",
    "system/lib/modules/eagle_dsp.ko": "080fb631390a92a45925a9353a906fa3789790576b9c39c25cd5b2c5a83af222",
    "system/etc/dspf/json/dspf_icc_chnl_cfg.json": "5da4cf07b089f5f623d879db37927b0616fedc5f879280a972c9ae3cd291bdf0",
    "system/etc/dji.json": "227de872ed7079fe9dedbe001f9a008d6d6acee7d46b99999cb4a973f899da2b",
    "vendor/firmware/dspf/ss_dsp0.fw": "5dd6da299227bca0d4bf3c1e92482ebcebf709216fc1e1e9efde8bd2cfab5344",
    "vendor/firmware/dspf/ss_dsp1.fw": "03f08813e18b577219986495c653b8ad1b58ed9edaad10ffb86cab4c29890572",
    "vendor/firmware/dspf/ss_dsp2.fw": "037fdd1476fcb0d738b1ce0f5933d8ddd64ce0a87862e0209dda394e5c6d8b5f",
    "vendor/firmware/dspf/ask_dsp.img": "bc64b8862f5e0eb2026eb90e20c6efb3e6d31ee2934bd20d93656747fde40128",
}

PUBLIC_SOURCE = {
    "repository": "o-gs/dji-firmware-tools",
    "path": "dji_imah_fwsig.py",
    "git_blob_sha1": "aa8d75548db2958685cfb643f2ab0bc9c8b8b823",
    "sha256": "534680d1fb0ced5f6425b276fcd421456a45a513cf625d73566b2150c2ed6760",
    "bytes": 74094,
    "blob_api_url": "https://api.github.com/repos/o-gs/dji-firmware-tools/git/blobs/aa8d75548db2958685cfb643f2ab0bc9c8b8b823",
    "format_references": {
        "header_and_chunks": [511, 646],
        "v2_crypto_parameters": [769, 795],
        "chunk_decryption_and_plain_checksum": [1143, 1235],
    },
}

PUBLIC_LABELS = (
    "TBIE-2021-08", "TBIE-2021-06", "TBIE-2020-04",
    "TBIE-2020-02", "TBIE-2019-11", "TBIE-2018-07",
)

FUNCTIONS = {
    "libdcam_pp.so": [
        "raw2rgb_proc", "_raw2rgb_pull_buf_cb", "proc_hbl_calib", "hbl_calib_build",
        "min_ev_raw2rgb", "med_ev_raw2rgb", "raw2rgb_hlrec_drc", "raw2rgb",
    ],
    "libdcam_pp_base.so": [
        "message_trans_arm_proc_pull", "sl_message_trans_arm_proc_pull",
        "pp_create_dsp_frwk_dev_ctx", "_pp_dsp_frwk_sl_process",
        "pp_new_ss_function_client", "pp_call_ss_function_client",
    ],
    "libdsp_frwk.so": [
        "ss_dsp_function_client_new", "ss_dsp_function_client_call",
        "ss_icc_dsp_function_rpc", "ss_icc_dsp_function_rpc_async",
        "ss_icc_send_sync", "ss_icc_send_sync_nowait",
    ],
    "libduml_hal.so": ["duss_hal_icc_send", "duss_hal_attach_linux_icc"],
    "libfw_util.so": ["plt_fw_load_file", "plt_fw_load"],
    "ss_dsp_manager": ["ss_load_dsp_firmware", "load_IMAGE_dsp_firmware"],
}

CALLS = {
    "libdcam_pp.so": [
        (0x1D16B4, "message_trans_arm_proc_pull@plt"),
        (0x1D19D8, "message_trans_arm_proc_pull@plt"),
        (0xD5974, "message_trans_arm_proc_pull@plt"),
        (0xD5160, "hbl_calib_build"), (0xD529C, "hbl_calib_build"),
        (0x1D9700, "raw2rgb_proc@plt"), (0x1DB030, "raw2rgb_proc@plt"),
        (0x1B6F18, "raw2rgb_proc@plt"), (0x1DF040, "raw2rgb_proc@plt"),
        (0x1D1A64, "memcpy@plt"), (0x1D1A78, "memcpy@plt"), (0x1D1A8C, "memcpy@plt"),
    ],
    "libdcam_pp_base.so": [
        (0x3A354, "sl_message_trans_arm_proc_pull@plt"),
        (0x5B98C, "pp_new_ss_function_client@plt"),
        (0x5B9A4, "pp_call_ss_function_client@plt"),
        (0x6E4A0, "ss_dsp_function_client_new@plt"),
        (0x6EEC0, "ss_dsp_function_client_call@plt"),
    ],
    "libdsp_frwk.so": [
        (0xAFC4, "ss_icc_dsp_function_rpc@plt"),
        (0xB108, "ss_icc_dsp_function_rpc_async@plt"),
        (0xB168, "ss_icc_dsp_function_rpc_async@plt"),
        (0xFFF4, "ss_icc_send_sync@plt"),
        (0x10200, "ss_icc_send_sync_nowait@plt"),
        (0xD0C8, "ss_icc_send_sync_nowait@plt"),
        (0xD10C, "ss_icc_wait_ack@plt"),
        (0xCF4C, "duss_hal_icc_send@plt"),
    ],
    "libduml_hal.so": [(0x3605C, "ioctl@plt")],
    "libfw_util.so": [(0x2760, "fw_util_load@plt"), (0x2560, "fw_util_load@plt")],
    "ss_dsp_manager": [
        (0x6F44, "load_IMAGE_dsp_firmware"), (0x6F70, "load_IMAGE_dsp_firmware"),
        (0x59F0, "plt_fw_load_file@plt"), (0x5A64, "duss_hal_dsp_launch@plt"),
    ],
}


def check(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ElfView:
    def __init__(self, data):
        self.data = data
        self.elf = ELFFile(io.BytesIO(data))
        check(self.elf["e_machine"] == "EM_AARCH64" and self.elf.little_endian,
              "Expected little-endian AArch64 host ELF")
        symbols = []
        for name in (".dynsym", ".symtab"):
            sec = self.elf.get_section_by_name(name)
            if sec is not None:
                symbols.extend(sec.iter_symbols())
        debug = self.elf.get_section_by_name(".gnu_debugdata")
        if debug is not None:
            # Inputs are full-file hash pinned before this decompression.
            raw = lzma.decompress(debug.data())
            check(len(raw) < 64 * 1024 * 1024, "Excessive mini-debug size")
            de = ELFFile(io.BytesIO(raw))
            symbols.extend(de.get_section_by_name(".symtab").iter_symbols())
        self.names, self.addresses = {}, {}
        for s in symbols:
            if s.name and s["st_shndx"] != "SHN_UNDEF":
                self.names[s.name] = (s["st_value"], s["st_size"])
                self.addresses.setdefault(s["st_value"], set()).add(s.name)
        dyn = self.elf.get_section_by_name(".dynsym")
        plt = self.elf.get_section_by_name(".plt")
        rel = self.elf.get_section_by_name(".rela.plt")
        if rel is not None:
            for i, r in enumerate(rel.iter_relocations()):
                va = plt["sh_addr"] + 32 + 16 * i
                self.addresses.setdefault(va, set()).add(dyn.get_symbol(r["r_info_sym"]).name + "@plt")
        self.md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.md.detail = True

    def read(self, va, size):
        for seg in self.elf.iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_vaddr"] <= va:
                off = va - seg["p_vaddr"]
                if off + size <= seg["p_filesz"]:
                    return self.data[seg["p_offset"] + off:seg["p_offset"] + off + size]
        raise ValueError(f"Address range not file-backed: {va:#x}/{size}")

    def instruction(self, va):
        ins = list(self.md.disasm(self.read(va, 4), va))
        check(len(ins) == 1 and ins[0].size == 4, f"Cannot decode instruction at {va:#x}")
        return ins[0]

    def function(self, name):
        va, size = self.names[name]
        check(0 < size < 256 * 1024, f"Unbounded function: {name}")
        return {"name": name, "va": hex(va), "bytes": size, "sha256": digest(self.read(va, size))}

    def direct_call(self, va, name):
        ins = self.instruction(va)
        check(ins.mnemonic == "bl" and ins.operands[0].type == ARM64_OP_IMM,
              f"Expected direct call at {va:#x}")
        target = ins.operands[0].imm
        check(name in self.addresses.get(target, set()), f"Unexpected call target at {va:#x}: {name}")
        return {"call_va": hex(va), "target_va": hex(target), "target": name, "pass": True}

    def string(self, va, expected):
        check(self.read(va, len(expected) + 1) == expected.encode("ascii") + b"\0",
              f"Unexpected string at {va:#x}")
        return {"va": hex(va), "text": expected}


def reg(ins, op):
    return ins.reg_name(op.reg)


def wide_constant(view, low_va, high_va):
    low, high = view.instruction(low_va), view.instruction(high_va)
    check(low.mnemonic == "mov" and high.mnemonic == "movk", "Unexpected constant construction")
    check(reg(low, low.operands[0]) == reg(high, high.operands[0]), "Constant register mismatch")
    check(low.operands[1].type == high.operands[1].type == ARM64_OP_IMM, "Not immediate")
    value = (low.operands[1].imm & ~(0xFFFF << high.operands[1].shift.value))
    value |= high.operands[1].imm << high.operands[1].shift.value
    return {"low_va": hex(low_va), "high_va": hex(high_va), "value": hex(value)}


def indirect_slot(view, load_va, call_va, offset, branch="blr"):
    load, call = view.instruction(load_va), view.instruction(call_va)
    check(load.mnemonic == "ldr" and load.operands[1].type == ARM64_OP_MEM,
          "Expected callback pointer load")
    check(load.operands[1].mem.disp == offset, "Callback slot mismatch")
    check(call.mnemonic == branch and call.operands[0].type == ARM64_OP_REG,
          "Expected indirect callback branch")
    check(reg(load, load.operands[0]) == reg(call, call.operands[0]), "Callback register mismatch")
    return {"load_va": hex(load_va), "call_va": hex(call_va), "slot": hex(offset), "pass": True}


def callback_table(view):
    """Evaluate only straight-line ADRP/ADD address construction and STP stores.

    This is not a general emulator. The full input hash and bounded constructor
    make these selected register facts sufficient for this exact firmware.
    """
    values, slots = {}, {}
    for va in range(0x57D4C, 0x57E2C, 4):
        ins = view.instruction(va)
        ops = ins.operands
        if ins.mnemonic == "adrp":
            values[reg(ins, ops[0])] = ops[1].imm
        elif ins.mnemonic == "add" and ops[2].type == ARM64_OP_IMM:
            dest, source = reg(ins, ops[0]), reg(ins, ops[1])
            if source in values:
                values[dest] = values[source] + (ops[2].imm << ops[2].shift.value)
            else:
                values.pop(dest, None)
        elif ins.mnemonic == "stp" and ops[2].type == ARM64_OP_MEM:
            mem = ops[2].mem
            if ins.reg_name(mem.base) == "x20" and 0 <= mem.disp <= 0x70:
                for i in range(2):
                    name = reg(ins, ops[i])
                    check(name in values, f"Unknown callback address at {va:#x}")
                    address = values[name]
                    slots[mem.disp + 8 * i] = {
                        "store_va": hex(va), "target_va": hex(address),
                        "target_symbols": sorted(view.addresses.get(address, set())),
                    }
    check(len(slots) == 16, "Incomplete DSP callback table")
    check("_pp_dsp_frwk_sl_process" in slots[0x18]["target_symbols"], "Process callback mismatch")
    check("_pp_dsp_frwk_sl_pull_buf" in slots[0x38]["target_symbols"], "Pull callback mismatch")
    return {hex(k): v for k, v in sorted(slots.items())}


def imah_metadata(data):
    check(data[:4] == b"IM*H", "Not an IMaH image")
    version = struct.unpack_from("<I", data, 4)[0]
    header, signature, payload = struct.unpack_from("<III", data, 16)
    plain_checksum, count = struct.unpack_from("<II", data, 152)
    check(version == 2 and header == 192 + 32 * count and count == 4, "Unexpected DSP container layout")
    check(header + signature + payload == len(data), "Container length mismatch")
    check(data[40:48] == b"PRAKTBIE", "Unexpected authentication/encryption identifiers")
    payload_hash = digest(data[header + signature:])
    check(payload_hash == data[160:192].hex(), "Encrypted payload digest mismatch")
    chunks = []
    previous_end = 0
    for i in range(count):
        name, off, size, attrib, address = struct.unpack_from("<4sIIIQ", data, 192 + 32 * i)
        pad = (-size) % 32 if not attrib & 1 else 0
        check(attrib == 0, "Expected all chunks encrypted in these pinned images")
        check(off >= previous_end and off + size + pad <= payload, "Invalid chunk bounds")
        previous_end = off + size + pad
        chunks.append({"index": i, "id": name.decode("ascii"), "payload_offset": off,
                       "bytes": size, "padded_bytes": size + pad, "attributes": attrib,
                       "encrypted_by_format": not bool(attrib & 1), "load_address": hex(address)})
    return {"header_version": version, "header_bytes": header, "signature_bytes": signature,
            "payload_bytes": payload, "auth_identifier": "PRAK", "encryption_identifier": "TBIE",
            "image_name": data[64:96].split(b"\0")[0].decode("ascii"),
            "image_type": data[96:100].decode("ascii"),
            "build_date_bcd": hex(struct.unpack_from("<I", data, 104)[0]),
            "os_byte": data[32], "architecture_byte": data[33], "compression_byte": data[34],
            "encrypted_payload_sha256": payload_hash, "encrypted_payload_hash_matches_header": True,
            "stored_plaintext_checksum": hex(plain_checksum), "chunks": chunks,
            "exact_dsp_isa_established": False}


def public_keys(path):
    data = path.read_bytes()
    check(len(data) == PUBLIC_SOURCE["bytes"] and digest(data) == PUBLIC_SOURCE["sha256"],
          "Published source byte count/SHA256 mismatch; require exact Git blob bytes")
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    check(blob == PUBLIC_SOURCE["git_blob_sha1"], "Published Git blob identity mismatch")
    keys = {}
    for node in ast.parse(data).body:
        if not isinstance(node, ast.Assign) or not any(isinstance(t, ast.Name) and t.id == "keys" for t in node.targets):
            continue
        check(isinstance(node.value, ast.Dict), "Public key map is not a literal dictionary")
        for k, v in zip(node.value.keys, node.value.values):
            label = ast.literal_eval(k)
            if not isinstance(label, str) or not label.startswith("TBIE-"):
                continue
            check(isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "bytes"
                  and len(v.args) == 1 and not v.keywords, "Unsupported key literal")
            value = bytes(ast.literal_eval(v.args[0]))
            check(len(value) == 16, "Expected a 16-byte public variant")
            keys[label] = value
    check(set(keys) == set(PUBLIC_LABELS), "Published TBIE key set differs from pinned expectation")
    return keys


def test_public_keys(data, metadata, keys):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    start = metadata["header_bytes"] + metadata["signature_bytes"]
    expected = int(metadata["stored_plaintext_checksum"], 16)
    results = []
    for label in PUBLIC_LABELS:
        unwrap = Cipher(algorithms.AES(keys[label]), modes.ECB()).decryptor()
        data_key = unwrap.update(data[48:64]) + unwrap.finalize()
        # The upstream 32-bit counter starts at zero. These <7 MB payloads never
        # approach its overflow, so a zero-initialized 128-bit CTR is equivalent.
        decrypt = Cipher(algorithms.AES(data_key), modes.CTR(bytes(16))).decryptor()
        checksum = 0
        for chunk in metadata["chunks"]:
            off = start + chunk["payload_offset"]
            decoded = decrypt.update(data[off:off + chunk["padded_bytes"]])
            check(len(decoded) % 4 == 0, "Checksum input is not word aligned")
            checksum = (checksum + sum(x[0] for x in struct.iter_unpack("<I", decoded))) & 0xFFFFFFFF
            del decoded
        check(decrypt.finalize() == b"", "Unexpected CTR remainder")
        results.append({"public_key_label": label, "computed_plaintext_checksum": hex(checksum),
                        "plaintext_checksum_match": checksum == expected})
    return results


def run(root, public_source):
    blobs, files, views = {}, {}, {}
    for rel, pin in PINS.items():
        data = (root / rel).read_bytes()
        check(digest(data) == pin, f"Firmware identity mismatch: {rel}")
        blobs[rel] = data
        files[rel] = {"bytes": len(data), "sha256": pin}
        if data.startswith(b"\x7fELF"):
            elf = ElfView(data)
            files[rel]["host_elf_machine"] = elf.elf["e_machine"]
            views[Path(rel).name] = elf
    functions = {name: [views[name].function(n) for n in names] for name, names in FUNCTIONS.items()}
    calls = {name: [views[name].direct_call(va, target) for va, target in entries] for name, entries in CALLS.items()}
    pp, base, hal, manager = (views[n] for n in ("libdcam_pp.so", "libdcam_pp_base.so", "libduml_hal.so", "ss_dsp_manager"))
    constants = {
        "raw2rgb_libpp_operation": wide_constant(pp, 0x1D15F0, 0x1D15F4),
        "hbl_calib_base_operation": wide_constant(pp, 0xD5004, 0xD500C),
        "linux_icc_ioctl_request": wide_constant(hal, 0x36040, 0x36048),
    }
    check(constants["raw2rgb_libpp_operation"]["value"] == "0x110009", "Raw2rgb operation mismatch")
    check(constants["hbl_calib_base_operation"]["value"] == "0x2e0001", "Calibration operation mismatch")
    check(constants["linux_icc_ioctl_request"]["value"] == "0x40184905", "ICC ioctl mismatch")
    indirect = [indirect_slot(base, load, call, slot) for load, call, slot in (
        (0x38A48, 0x38A4C, 8), (0x38AA4, 0x38AA8, 0x18),
        (0x38BF8, 0x38BFC, 0x18), (0x38F98, 0x38F9C, 0x30),
        (0x39270, 0x39274, 0x38),
    )]
    hal_pointer = struct.unpack("<Q", hal.read(0xFD758, 8))[0]
    check(hal_pointer == 0x36020, "ICC send table pointer differs")
    strings = {
        "libdcam_pp_base.so": [
            base.string(0x820D9, "cam_libpp_function_entry"),
            base.string(0x82189, "framework_sdk_e2_proxy_demo_op"),
            base.string(0x81902, "hardware/dji/common/camera/libpp_proxy/pp_proxy/platform/dspf10/pp_dspf_api.c"),
        ],
        "ss_dsp_manager": [
            manager.string(0x1DDFA, "/vendor/firmware/dspf/ss_dsp0.fw"),
            manager.string(0x1DE1B, "/vendor/firmware/dspf/ss_dsp1.fw"),
            manager.string(0x1DE3C, "/vendor/firmware/dspf/ss_dsp2.fw"),
            manager.string(0x200AA, "ceva version:[%08x], build:%s ,time:%s \r\n"),
            manager.string(0x20A4B, "SS_CEVA_DMA"),
        ],
    }
    config = json.loads(blobs["system/etc/dspf/json/dspf_icc_chnl_cfg.json"])
    channels = [c["chnl_name"] for row in config["icc_chnl_info"] for c in row["chnl_cfg"]
                if c["source"] == "ICC_EP_LINUX" and c["target"] in ("ICC_EP_DSP0", "ICC_EP_DSP1", "ICC_EP_DSP2")]
    check(config["apply_json_cfg"] == 1 and len(channels) == 14, "Unexpected ICC channel configuration")
    check(b"duss_hal_attach_linux_icc" in blobs["system/etc/dji.json"], "ICC HAL attachment absent from device configuration")
    keys = public_keys(public_source) if public_source else None
    dsp = {}
    for rel, data in blobs.items():
        if rel.startswith("vendor/firmware/dspf/"):
            meta = imah_metadata(data)
            if keys is not None:
                meta["tested_public_variants"] = test_public_keys(data, meta, keys)
                meta["all_tested_public_variants_failed_plaintext_checksum"] = all(
                    not x["plaintext_checksum_match"] for x in meta["tested_public_variants"])
            dsp[rel] = meta
    return {
        "schema": 1, "audit_date": "2026-10-19", "firmware": "X2D II 1.3.16.2",
        "script_sha256": digest(Path(__file__).read_bytes()),
        "dependencies": {p: importlib.metadata.version(p) for p in
                         (["pyelftools", "capstone", "cryptography"] if keys else ["pyelftools", "capstone"])},
        "mode": "static metadata and optional in-memory published-variant checks; no vendor execution",
        "files": files, "functions": functions, "verified_direct_calls": calls,
        "verified_constant_construction": constants, "verified_dispatch_callback_slots": indirect,
        "verified_dsp_device_callback_installation": callback_table(base),
        "linux_icc_send_callback": {"table_va": "0xfd738", "slot": "0x20", "target_va": hex(hal_pointer),
                                    "bounded_region_bytes": 208, "bounded_region_sha256": digest(hal.read(hal_pointer, 208)),
                                    "name_is_analyst_assigned": True, "ioctl_call_va": "0x3605c"},
        "selected_strings": strings,
        "configured_linux_to_dsp_channels": channels,
        "dsp_images": dsp, "public_imah_source": PUBLIC_SOURCE,
        "public_variant_check_performed": keys is not None,
        "scope": {
            "operation_selector_is_not_the_resolved_rpc_function_id": True,
            "remote_entry": "cam_libpp_function_entry",
            "remote_function_id": "resolved from DSP name-to-ID map at runtime; numeric value not recovered",
            "ceva_evidence": "host strings refer to CEVA; exact DSP ISA/model not established",
            "saved_pixel_algorithm_implementation_recovered": False,
            "main_3dlut_or_main_hncs_inside_this_rpc_proven": False,
            "generic_dispatcher_all_possible_contexts_proven_dsp": False,
            "rsa_signature_authenticity_verified_here": False,
            "key_test_limit": "Only the six TBIE variants in the pinned public source; no global claim about other keys",
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", type=Path, required=True)
    parser.add_argument("--public-imah-source", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="Metadata JSON only; no firmware bytes are written")
    args = parser.parse_args()
    result = run(args.firmware_root, args.public_imah_source)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": str(args.out), "firmware_files_verified": len(result["files"]),
                      "functions_pinned": sum(map(len, result["functions"].values())),
                      "direct_calls_verified": sum(map(len, result["verified_direct_calls"].values())),
                      "public_variant_check_performed": result["public_variant_check_performed"]}))
