#!/usr/bin/env python3
"""Read-only native colour/WB inventory; never loads or executes an ELF."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import re
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile

COLOUR = re.compile(r"color|colour|matrix|gamma|tone|curve|rgb|xyz|lab|hsv|hsl|awb|hue|satur|lut|chroma|cct|ccm|whitebalance|white_balance", re.I)
MAX_DEBUGDATA = 64 * 1024 * 1024


def symbol_records(elf, origin):
    for section_name in (".dynsym", ".symtab"):
        section = elf.get_section_by_name(section_name)
        if section is None or not hasattr(section, "iter_symbols"):
            continue
        for symbol in section.iter_symbols():
            if symbol["st_shndx"] == "SHN_UNDEF" or not symbol.name:
                continue
            if COLOUR.search(symbol.name):
                yield {
                    "name": symbol.name,
                    "va": symbol["st_value"],
                    "bytes": symbol["st_size"],
                    "type": symbol["st_info"]["type"],
                    "binding": symbol["st_info"]["bind"],
                    "visibility": symbol["st_other"]["visibility"],
                    "source": origin + section_name,
                }


def inspect(path, root):
    with path.open("rb") as source:
        if source.read(4) != b"\x7fELF":
            return None
        source.seek(0)
        elf = ELFFile(source)
        dynamic = elf.get_section_by_name(".dynamic")
        needed, soname, init = [], None, []
        if dynamic:
            for tag in dynamic.iter_tags():
                kind = tag.entry.d_tag
                if kind == "DT_NEEDED":
                    needed.append(tag.needed)
                elif kind == "DT_SONAME":
                    soname = tag.soname
                elif kind in ("DT_INIT", "DT_INIT_ARRAY", "DT_INIT_ARRAYSZ"):
                    init.append({"tag": kind, "value": tag.entry.d_val})
        records = list(symbol_records(elf, "elf:"))
        debugdata = elf.get_section_by_name(".gnu_debugdata")
        debugdata_status = "absent"
        if debugdata:
            decoder = lzma.LZMADecompressor()
            decoded = decoder.decompress(debugdata.data(), max_length=MAX_DEBUGDATA + 1)
            if len(decoded) > MAX_DEBUGDATA or not decoder.eof:
                debugdata_status = "rejected: decompressed data exceeds bound or is incomplete"
            else:
                records.extend(symbol_records(ELFFile(io.BytesIO(decoded)), "gnu_debugdata:"))
                debugdata_status = f"parsed {len(decoded)} bytes"
        seen = set()
        distinct = []
        for record in records:
            key = (record["name"], record["va"], record["bytes"], record["source"])
            if key not in seen:
                distinct.append(record)
                seen.add(key)
        source.seek(0)
        sha = hashlib.file_digest(source, "sha256").hexdigest()
        return {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha,
            "elf_class": elf.elfclass,
            "machine": elf["e_machine"],
            "little_endian": elf.little_endian,
            "soname": soname,
            "needed": needed,
            "initializers": init,
            "gnu_debugdata": debugdata_status,
            "colour_symbols": distinct,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.firmware_root.resolve(strict=True)
    output = args.output.resolve()
    if output == root or root in output.parents:
        parser.error("output must be outside the read-only firmware input tree")
    records, errors = [], []
    for path in sorted(root.rglob("*.so*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            record = inspect(path, root)
            if record:
                records.append(record)
        except Exception as error:
            errors.append({"path": str(path.relative_to(root)), "error": str(error)})
    payload = {"method": "ELF/static only; no library loaded or invoked", "libraries": records, "errors": errors}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"libraries": len(records), "matching_libraries": sum(bool(r["colour_symbols"]) for r in records), "error_count": len(errors), "first_errors": errors[:3]}))


if __name__ == "__main__":
    main()
