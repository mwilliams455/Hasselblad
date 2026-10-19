#!/usr/bin/env python3
"""Verify the actual DEX instruction passing the corrected Software string."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import zipfile

BASE = Path('/workspace/scratch/f4dc23366b1f')
SPEC = importlib.util.spec_from_file_location('dex_inspector', BASE/'hasselblad_native_audit/dex_isolation/inspect_apk_dex.py')
INSPECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTOR)
TARGET = 'Lcom/particlesdevs/photoncamera/processing/DngCreator;'
INSPECTOR.TARGETS = {TARGET: {'setParameters', 'setSoftware'}}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-software', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    apk_data = args.apk.read_bytes()
    assert sha(apk_data) == args.expected_sha256
    owners = []
    inventory = []
    methods = []
    dexdump = Path('/tmp/hasselblad-build-tools/android-sdk/build-tools/35.0.0/dexdump')
    with zipfile.ZipFile(args.apk) as archive, tempfile.TemporaryDirectory(prefix='hb-native1a-dex-') as temporary:
        for item in archive.infolist():
            if not item.filename.startswith('classes') or not item.filename.endswith('.dex'):
                continue
            data = archive.read(item)
            classes = INSPECTOR.defined_classes(data)
            inventory.append({'dex': item.filename, 'bytes': len(data), 'sha256': sha(data)})
            if TARGET in classes:
                owners.append(item.filename)
                path = Path(temporary)/item.filename
                path.write_bytes(data)
                extracted, _ = INSPECTOR.disassemble_selected(dexdump, path)
                methods.extend(m for m in extracted if m['class'] == TARGET)
    assert len(owners) == 1
    parameters = [m for m in methods if m['method'] == 'setParameters']
    assert len(parameters) == 1
    lines = parameters[0]['lines']
    literal = json.dumps(args.expected_software)
    positions = [i for i, line in enumerate(lines) if 'const-string' in line and literal in line]
    assert len(positions) == 1, 'Expected new Software literal absent from compiled setParameters'
    position = positions[0]
    register = re.search(r'const-string(?:/jumbo)?\s+(v\d+),', lines[position]).group(1)
    following = lines[position+1:position+5]
    calls = [line for line in following if '.setSoftware:(Ljava/lang/String;)V' in line]
    assert len(calls) == 1
    arguments = re.search(r'\{([^}]+)\}', calls[0]).group(1).split(', ')
    assert arguments[-1] == register, 'New constant is not the Software call argument'
    assert not any('const-string' in line and 'PhotonCamera v-1' in line for line in lines)
    source = BASE/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/processing/DngCreator.java'
    source_text = source.read_text()
    assert 'import com.particlesdevs.photoncamera.BuildConfig;' in source_text
    assert 'import de.hdodenhof.circleimageview.BuildConfig;' not in source_text
    result = {
        'result': 'pass',
        'artifact': {'filename': args.apk.name, 'bytes': len(apk_data), 'sha256': sha(apk_data)},
        'method': 'Inventoried class definitions in all packaged DEX files, located the unique actual DngCreator definition, and inspected Android SDK dexdump instructions. Verified that the expected Software const-string register is the argument to the immediately following setSoftware(String) call.',
        'expected_software': args.expected_software,
        'source': {'path': str(source), 'sha256': sha(source.read_bytes()), 'uses_app_buildconfig': True},
        'target_class': TARGET, 'target_class_dex': owners[0],
        'verified_instruction_sequence': lines[max(0, position-3):position+5],
        'obsolete_software_literal_in_setParameters': False,
        'dex_inventory': inventory,
        'full_selected_methods': methods,
        'limits': 'Static compiled writer-version provenance only. The synthetic native fixture sets its own Software string; the next physical-device DNG should confirm this Java-to-native tag value.'
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('result', 'artifact', 'expected_software', 'target_class_dex', 'verified_instruction_sequence')}, indent=2))


if __name__ == '__main__':
    main()
