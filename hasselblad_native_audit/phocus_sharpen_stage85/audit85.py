#!/usr/bin/env python3
"""Compare an independent bounded C sharpening port with the original private CPU code."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from check85 import Port, SETTINGS, patterns, host_checks, HERE
from oracle85 import KernelRunner, graph_runner_type


def main():
    parser = argparse.ArgumentParser()
    for key in ('apk','work','safe-receipt'): parser.add_argument('--'+key,required=True,type=Path)
    a = parser.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).hexdigest()
    GraphRunner = graph_runner_type()
    from audit_post55 import load_private
    elf, profile = load_private(a.apk)  # Existing pinned APK/library/profile identities.
    port = Port(a.work); host = host_checks(port)
    kernel = KernelRunner(elf)
    cases = values = table_values = 0
    for settings in SETTINGS:
        for name, pixels in patterns().items():
            native, weights, amounts, noise = kernel.rows(pixels, settings)
            expected_tables = port.tables(settings)
            for actual, expected in zip((weights, amounts, noise), expected_tables):
                assert np.array_equal(actual, expected), ('table', settings, name)
                table_values += actual.size
            actual = port.render(pixels, settings)
            assert np.array_equal(actual, native), ('pixels', settings, name,
                int(np.abs(actual.astype(int)-native.astype(int)).max()))
            cases += 1; values += pixels.size
        print('Original row kernel exact for settings', settings, flush=True)
    # SIMD/tail widths and first/last-row behaviour, including smaller-than-kernel fixtures.
    for w,h in ((1,1),(2,3),(7,9),(8,8),(9,17),(65,71)):
        pixels = patterns(w,h)['random']
        native, *_ = kernel.rows(pixels, SETTINGS[0])
        assert np.array_equal(native,port.render(pixels))
        cases += 1; values += pixels.size
    graph = GraphRunner(elf, profile); binding = graph.graph85()
    full_cases = full_values = 0
    # Original wrapper: real downshift, real row kernel, real upshift; only buffer ownership is a fixture.
    for settings in (SETTINGS[0], SETTINGS[3], SETTINGS[6], SETTINGS[7]):
        for name in ('random','neutral_ramp','impulse','near_black','colour_edges'):
            pixels = (patterns(33,33)[name].astype(np.uint32)*4 + np.random.default_rng(85).integers(0,4,(33,33,3))).astype(np.uint16)
            native = graph.full(pixels, settings)
            expected = (port.render(pixels >> 2, settings).astype(np.uint16) << 2)[4:-4,4:-4]
            assert np.array_equal(native,expected), ('full wrapper',settings,name,
                int(np.abs(native.astype(int)-expected.astype(int)).max()))
            full_cases += 1; full_values += native.size
        print('Original 16-bit wrapper exact for settings', settings, flush=True)
    assert hashlib.sha256(a.apk.read_bytes()).hexdigest() == before
    result = {'schema':'hasselblad-stage85-native-sharpen-v1','status':'PASS_BOUNDED_CPU_SHARPENING',
              'graph_binding':binding,'host_checks':host,
              'native_row_cases':cases,'native_row_rgb14_channels':values,
              'native_table_values_compared':table_values,'native_row_max_abs_difference':0,
              'native_full_wrapper_cases':full_cases,'native_full_wrapper_rgb16_channels':full_values,
              'native_full_wrapper_max_abs_difference':0,'guards_and_input_checks_passed':True,
              'source_apk_unchanged':True,'host_libm_fixture':True,
              'first_and_horizontal_row_extension_executed_natively':True,
              'last_row_replication_fixture':True,'full_wrapper_interior_margin':4,
              'blur_conversion_singleton_fixture_unused_by_verified_path':True,
              'graph_and_buffer_ownership_fixtures':True,
              'android_integrated':False,'capture_renderer_changed':False,'demosaic_retested':False,
              'private_payload_exported':False,'parameters_fitted_to_photos':False,
              'limits':['full-resolution SDR only; no resize compensation, blur or local adjustments',
                        'outer image boundary policy is not established by the interior wrapper comparison',
                        'host reference allocates luma planes; Android needs streaming rows and JNI integration',
                        'no GPU/live-preview or phone-specific sharpening calibration equivalence'],
              'source_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(HERE.iterdir()) if f.suffix in ('.c','.h','.py')}}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS:',cases,'row cases and',full_cases,'original wrapper cases',flush=True)

if __name__=='__main__': main()
