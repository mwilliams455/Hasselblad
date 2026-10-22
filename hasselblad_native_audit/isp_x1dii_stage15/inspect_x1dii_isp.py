#!/usr/bin/env python3
"""Pinned, inert X1D II 50C firmware dump / X2D II MAIN CCM lead audit.

Reads ONLY the publicly posted older firmware files, never executes a vendor
binary and publishes only symbol names, hashes, config topology, and filtered
original source-path references. This is NOT a recovered CCM pixel equation.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import io
import json
import re
import tempfile
import urllib.request
from pathlib import Path

REPOSITORY = "derrickyau9/Hasselblad_X1D_II_FirmwareDump"
REV = "f39ac51d6b92c19f9b34e35d5f32f985a1c1cbe5"
ROOT = "_X1D_II_50C_v1_0_0.cim.extracted/system.img/"
MANIFEST = {
    "build.prop": (1839, "53ea0e9607dfe6e3d0c9beb6da3336b752a430b9"),
    "etc/VERSION": (6, "3eefcb9dd5b38e2c1dc061052455dd97bcd51e6c"),
    "etc/dji_rcam.conf": (121, "ceeb3c35c7ca0730948c100086a41d4ef6fefc2e"),
    "etc/dji_camera.conf": (10422, "17927f975dfdbd89838a31938adefef88d467559"),
    "etc/imx161f_ec1704.sp": (24345, "2aeb1893f2467c7501afe91192ae13b5fd9a8f86"),
    "lib/libdcam_frwk.so": (1835764, "f4c48352bbc0effc57d20784e6b174590a3035e9"),
    "lib/libmod_x1dm2.so": (1117316, "481279b6d9bade113dc8e3dfe9fd82c472df1edb"),
    "lib/libmod_dji.so": (526548, "d9a5a25b659c3de645a6c65f0de469bd0187c058"),
    "lib/libdcam_pp.so": (563892, "9842b75a7b5c8035659de9bb40cf52336cba6255"),
    "lib/libdcam_fcali.so": (167512, "cf195a8eb429cc74c8b5f847988be1db4dc54365"),
    "lib/libduml_hal_cam.so": (401760, "d83f9f6102efe21b67701a3f3251b3bbf7444923"),
    "lib/libduml_hal.so": (255968, "e3972855ade08799339ec2adab3a4563f13f6607"),
    "lib/modules/eagle_dsp.ko": (297811, "8dc049434c152e08bf4f2e2176cd98c65bf24fa6"),
}

# IMPORTANT: names of sensor-specific tuning descriptors are distinct from an
# equation that operates on image pixels. Filter does not upgrade evidence.
FOCUS = re.compile(r"(?:ccm|(?:^|_)lmtx|color.?matrix|colour.?matrix|(?:^|_)gamma|"
                   r"(?:^|_)3dlut|lut3d|(?:^|_)lut|(?:^|_)rgb|rgb2|"
                   r"(?:^|_)awb|white.balance|raw2rgb|sensor_calib|"
                   r"(?:^|_)hbl|(?:^|_)color|(?:^|_)colour|"
                   r"(?:^|_)image.*process|adj.*calc|(?:^|_)isp)", re.I)
STRONG_CCM = re.compile(r"ccm|color.?matrix|colour.?matrix|lmtx|rgb.?to.?xyz|"
                        r"xyz.?to.?rgb|matrix.?to.?rgb|rgb.?matrix", re.I)
SOURCE_PATH = re.compile(rb"(?:hardware|frameworks|vendor|system)/[A-Za-z0-9_./+\-]{8,230}\.(?:c|cc|cpp|h)")
FOCUS_CONTEXT = re.compile(rb"(?i)ccm|color.?matrix|colour.?matrix|lmtx|lut3d|3dlut|gamma|"
                            rb"\bawb\b|calibrat|cam.*color|color.*cam|color.order|"
                            rb"(?:^|[ /])rgb[_-]?(?:to|2)[_-]?(?:xyz|yuv|rgb)")


def gitblob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def verify(data: bytes, key: str) -> None:
    length, sha = MANIFEST[key]
    if len(data) != length or gitblob(data) != sha:
        raise ValueError("upstream pinned file mismatch: " + key)


def textstrings(data: bytes, minimum=8, maximum=260) -> list[str]:
    out = []
    for match in re.finditer(rb"[\x20-\x7e]{8,}", data):
        raw = match.group()
        if minimum <= len(raw) <= maximum:
            out.append(raw.decode("ascii"))
    return out


def summarize_elf(data: bytes, label: str) -> dict:
    from elftools.elf.elffile import ELFFile
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
    elf = ELFFile(io.BytesIO(data))
    if elf["e_machine"] != "EM_ARM" or elf.elfclass != 32 or not elf.little_endian:
        raise ValueError("expected little-endian 32-bit ARM ELF: " + label)
    symbs = []
    for section in elf.iter_sections():
        if section["sh_type"] not in ("SHT_DYNSYM", "SHT_SYMTAB"):
            continue
        for s in section.iter_symbols():
            if not s.name:
                continue
            symbs.append({
                "name": s.name,
                "value": int(s["st_value"]),
                "size": int(s["st_size"]),
                "kind": str(s["st_info"]["type"]),
                "defined": s["st_shndx"] != "SHN_UNDEF",
                "table": section.name,
            })
    unique = {}
    for s in symbs:
        # Prefer a defined declaration if present in both symbol tables.
        old = unique.get(s["name"])
        if old is None or (s["defined"] and not old["defined"]):
            unique[s["name"]] = s
    interesting = [s for s in unique.values() if FOCUS.search(s["name"])]
    candidates = [s for s in interesting if STRONG_CCM.search(s["name"])]
    # Do not assume a matching name implies an executable photographic pixel op.
    focused_fn = [s for s in candidates if s["defined"] and s["kind"] == "STT_FUNC" and
                  4 <= s["size"] <= 30000]
    strings = []
    paths = []
    for section_name in (".rodata", ".dynstr"):
        sec = elf.get_section_by_name(section_name)
        if sec is None:
            continue
        payload = sec.data()
        paths.extend(x.decode("ascii", "replace") for x in SOURCE_PATH.findall(payload))
        strings.extend(x for x in textstrings(payload) if FOCUS_CONTEXT.search(x.encode()))
    dynamic = elf.get_section_by_name(".dynamic")
    dependencies = sorted({str(t.needed) for t in dynamic.iter_tags() if t.entry.d_tag == "DT_NEEDED"}) if dynamic else []
    debug = elf.get_section_by_name(".gnu_debuglink")
    debug_name = debug.data().split(b"\x00", 1)[0].decode("ascii", "replace") if debug else None
    sections = {s.name: s for s in elf.iter_sections()}
    funcs = []
    for item in focused_fn[:45]:
        va = item["value"] & ~1
        match = next((s for s in elf.iter_sections() if s["sh_flags"] & 4 and
                     int(s["sh_addr"]) <= va and
                     va + item["size"] <= int(s["sh_addr"]) + int(s["sh_size"])), None)
        if match is None:
            funcs.append({"name":item["name"],"error":"not_mapped_to_executable_section"})
            continue
        off = va - int(match["sh_addr"])
        code = match.data()[off:off + item["size"]]
        thumb = bool(item["value"] & 1)
        engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB if thumb else CS_MODE_ARM)
        engine.detail = False
        mn = collections.Counter(i.mnemonic for i in engine.disasm(code, va))
        filtered = {k:v for k,v in mn.items() if re.match(r"(?:v\w+|[us]?mul\w*|mla\w*|sml\w*|ssat|usat|asr|lsr|smull|smmul|vq\w+|blx?|sdiv|udiv)$", k)}
        funcs.append({
            "name":item["name"],
            "source_elf_offset":int(match["sh_offset"]) + off,
            "virtual_address":hex(va),
            "size":len(code),
            "mode":"THUMB" if thumb else "ARM",
            "sha256":hashlib.sha256(code).hexdigest(),
            "operation_mnemonic_counts":filtered,
            "instructions_decoded":sum(mn.values()),
            "inspected_as_original_code_data_only":True,
        })
    def pick(s):
        return {k:s[k] for k in ("name", "value", "size", "kind", "defined", "table")}
    # Bounded only; no original instruction, table, image, or vendor payload.
    return {
        "file":label,
        "bytes":len(data),
        "sha256":hashlib.sha256(data).hexdigest(),
        "git_blob_sha1":gitblob(data),
        "elf_class":"ELF32", "machine":"EM_ARM", "endianness":"little",
        "has_symtab":elf.get_section_by_name(".symtab") is not None,
        "gnu_debuglink":debug_name,
        "symbols_distinct":len(unique),
        "strong_ccm_named_symbols":[pick(s) for s in candidates[:75]],
        "other_relevant_symbols":[pick(s) for s in interesting if s not in candidates][:65],
        "matching_function_audits":funcs,
        "embedded_source_paths":sorted(set(paths))[:80],
        "filtered_colour_strings":list(dict.fromkeys(strings))[:85],
        "needed_libraries":dependencies,
    }


def parse_configuration(artifacts:dict[str,bytes]) -> dict:
    prop = artifacts["build.prop"].decode("utf-8")
    conf = artifacts["etc/dji_camera.conf"].decode("utf-8")
    rc = json.loads(artifacts["etc/dji_rcam.conf"])
    sp = json.loads(artifacts["etc/imx161f_ec1704.sp"])
    def match_property(k):
        mm = re.search(r"^"+re.escape(k)+r"=(.+)$", prop, re.M)
        return mm.group(1).strip() if mm else None
    groups=[]
    for g in sp["stream_profile"]["stream_groups"]:
        groups.append({
            "id":g["id"],
            "shooter":g.get("shooter_id"),
            "main_nodes": next(([n["id"] for n in p.get("nodes",[])] for p in g.get("still_process_pipe",[]) if p["id"]=="main_pipe"),[]),
            "hdr_nodes": next(([n["id"] for n in p.get("nodes",[])] for p in g.get("still_process_pipe",[]) if p["id"]=="hdr_pipe"),[]),
        })
    section_names=[x for x in re.findall(r"^\[([^\]]+)\]",conf,re.M) if any(n in x for n in ("hiso","pfr","xidiri","shooter","camera"))]
    process_switches={}
    active=None
    for line in conf.splitlines():
        line=line.strip()
        if line.startswith("[") and line.endswith("]"):
            active=line[1:-1]
        elif active in ("hiso:ceva","pfr:ceva","xidiri:ceva") and re.match(r"^process_switch\s*=",line):
            process_switches[active]=line.split("=",1)[1].strip()
    return {
        "platform":{
            "android_release":match_property("ro.build.version.release"),
            "android_sdk":match_property("ro.build.version.sdk"),
            "cpu_abi":match_property("ro.product.cpu.abi"),
            "board":match_property("ro.board.platform"),
            "device":match_property("ro.product.device"),
            "firmware_version":artifacts["etc/VERSION"].decode("ascii").strip(),
        },
        "rcam_sensor_config_table":rc.get("sensor_config_table",[]),
        "stream_groups":groups,
        "process_switches":process_switches,
        "relevant_camera_sections":section_names,
        "note":"Pipeline nodes in configuration are not proof they execute when runtime process_switch says disable/auto",
    }


def download_asset(key: str) -> bytes:
    url = "https://raw.githubusercontent.com/"+REPOSITORY+"/"+REV+"/"+ROOT+key
    req = urllib.request.Request(url, headers={"User-Agent":"HasselbladISPResearchMetadataOnly/1.0"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        if resp.status != 200:
            raise ValueError("Could not retrieve pinned X1DII file: " + key)
        data = resp.read(MANIFEST[key][0]+1)
    verify(data,key)
    return data


def analyze(output:Path):
    from elftools.elf.elffile import ELFFile  # fail early if missing
    from capstone import Cs  # fail early if missing
    records={}
    # Keep each ELF in memory only for the current iteration; no firmware copies
    # written under the workspace, Git repository, or published artifacts.
    for key in MANIFEST:
        data=download_asset(key)
        if key.startswith("lib/"):
            records[key]=summarize_elf(data,key)
            print("INSPECT",key,"ARM32, related symbols",len(records[key]["strong_ccm_named_symbols"]),"all names",records[key]["symbols_distinct"],flush=True)
        else:
            records[key]={"bytes":len(data),"git_blob_sha1":gitblob(data)}
            # need text content only for parsing; temporary in memory
    texts={key:download_asset(key) for key in MANIFEST if not key.startswith("lib/")}
    config=parse_configuration(texts)
    output.parent.mkdir(parents=True,exist_ok=True)
    out={
        "schema":"hasselblad-stage15-x1dii-comparison-v1",
        "status":"inert_public_upstream_source_inspected",
        "upstream_repository":REPOSITORY,"upstream_revision":REV,
        "input_git_blob_integrity_verified":True,
        "source_platform":config,
        "library_inspection":records,
        "comparison_to_x2dii":{
            "x2dii_firmware":"X2D II 100C 1.3.16.2",
            "x2dii_librcam_sha256":"3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66",
            "x2dii_ccm_16x6_coefficients_preparation_proven":True,
            "cross_generation_ccm_equation_proven":False,
            "x1dii_sensor_profiles_suitable_for_x2dii":False,
            "x1dii_original_vendor_code_executed":False,
            "real_isp_pixel_output_compared":False,
        },
        "interpretation":"A same-name IQ CCM tuning descriptor cannot prove the hardware pixel equation or transfer coefficients across ISP generations.",
        "vendor_payloads_in_public_report":False,
    }
    serialized=json.dumps(out,sort_keys=True,indent=2)+"\n"
    if len(serialized)>350000:
        raise ValueError("Unbounded report contents")
    output.write_text(serialized)
    print(json.dumps({"status":"PASS","output":str(output),"bytes":output.stat().st_size,"camera_binaries":sum(k.startswith("lib/") for k in MANIFEST)}),flush=True)


def self_test():
    assert gitblob(b"")=="e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert len(gitblob(b"test"))==40
    assert FOCUS.search("imx378_iq_ccm_settings")
    assert FOCUS.search("x1dm2_iq_apost_lut3d_settings")
    assert STRONG_CCM.search("x1dm2_iq_ccm_settings")
    assert not STRONG_CCM.search("init_allocate_vpld_P_color_LUT")
    assert not STRONG_CCM.search("sky_color_pars_init")
    x=bytes([0, 31])+b"hardware/dji/common/camera/ccm_matrix_calc.c\x00"+bytes([255])
    assert any(b"ccm_matrix_calc.c" in y for y in SOURCE_PATH.findall(x))
    a={"build.prop":b"ro.build.version.release=6.0\nro.build.version.sdk=23\nro.product.cpu.abi=armeabi-v7a\nro.board.platform=eagle\nro.product.device=eagle_ec1704\n",
       "etc/VERSION":b"1.0.0\n", "etc/dji_rcam.conf":b'{"sensor_config_table":[]}',
       "etc/dji_camera.conf":b"[hiso:ceva]\nprocess_switch = auto\n[pfr:ceva]\nprocess_switch = disable\n",
       "etc/imx161f_ec1704.sp":b'{"stream_profile":{"stream_groups":[{"id":"still","still_process_pipe":[{"id":"main_pipe","nodes":[{"id":"input"}]}]}]}}'}
    s=parse_configuration(a)
    assert s["platform"]["android_sdk"]=="23"
    assert s["process_switches"]=={"hiso:ceva":"auto", "pfr:ceva":"disable"}
    assert s["stream_groups"][0]["main_nodes"]==["input"]
    print("PASS Stage15 integrity, evidence-labelling and parser self-test")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.self_test:
        self_test()
        return
    if args.output is None:
        p.error("--output required")
    analyze(args.output)

if __name__=="__main__":main()
