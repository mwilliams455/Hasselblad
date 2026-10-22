#!/usr/bin/env python3
"""Source-only audit of the existing Photon RAW WB/lens-map boundary.

This verifies code contracts at an exact repository revision. It neither
executes Android OpenGL nor claims that a CPU map replay equals the GPU output.
"""
import argparse,hashlib,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    pre='HasselbladPhoton/app/src/main/'
    names={
        'pipeline':pre+'java/com/particlesdevs/photoncamera/processing/opengl/postpipeline/PostPipeline.java',
        'bayer':pre+'java/com/particlesdevs/photoncamera/processing/opengl/postpipeline/Bayer2Float.java',
        'parameters':pre+'java/com/particlesdevs/photoncamera/processing/render/Parameters.java',
        'shader':pre+'assets/shaders/Bayer2Float/tofloat.glsl',
        'initial':pre+'java/com/particlesdevs/photoncamera/processing/opengl/postpipeline/Initial.java',
    }
    sources={key:(a.repo/path).read_text() for key,path in names.items()}
    checks={
        'default_chain_uses_bayer2float':'add(new Bayer2Float())' in sources['pipeline'],
        'default_chain_initial_tone_path':'add(new Initial())' in sources['pipeline'],
        'prelinear_uploads_parameter_gainmap':'new GLTexture(basePipeline.mParameters.mapSize' in sources['bayer'] and
                'basePipeline.mParameters.gainMap' in sources['bayer'],
        'prelinear_binds_gainmap':'glProg.setTexture("GainMap", gainMapTex)' in sources['bayer'],
        'prelinear_binds_whitepoint':'glProg.setVar("whitePoint", basePipeline.mParameters.whitePoint)' in sources['bayer'],
        'camera2_map_loaded':'lensMap.copyGainFactors(gainMap, 0)' in sources['parameters'],
        'shader_gainmap_enabled':'#define USEGAIN 1' in sources['shader'],
        'shader_green_average':'gains.rgb = vec3(gains.r,(gains.g+gains.b)/2.0,gains.a);' in sources['shader'],
        'shader_normalises_shading_gain':'gains.rgb /= max(dot(gains.rgb,vec3(1.0/3.0)), 1e-4);' in sources['shader'],
        'shader_whitepoint_divides_bayer':'float hlVal = (Output - levelC)/denom/balance;' in sources['shader'],
        'shader_whitepoint_by_site':all('balance = whitePoint.'+c+';' in sources['shader'] for c in 'rgb'),
        'shader_gain_channel_applies_to_bayer':'Output = clamp(gainC * hlVal, 0.0, 1.0);' in sources['shader'],
        'rgb_alternative_is_separate':'#if RGBLAYOUT == 1' in sources['shader'],
        'initial_consumes_gainmap':'glProg.setTexture("GainMap", ((PostPipeline)basePipeline).GainMap);' in sources['initial'],
    }
    failures=[key for key,ok in checks.items() if not ok]
    report={
        'status':'PASS' if not failures else 'FAIL',
        'scope':'static source contract only; no GPU parity, no device invocation',
        'checks':checks,'check_count':len(checks),
        'failures':failures,
        'boundary':'Default PostPipeline Bayer2Float per-CFA-site WB division plus mean-normalised chromatic lens map, before Initial tone processing',
        'photon_neutral_from_camera2_metadata_premise':'Verified separately in the Domain3 original capture sidecar, not fitted here',
        'hal_neutral_reused_as_new_awb_fallback':False,
        'renderer_changed':False,
        'shader_source_sha256':{key:hashlib.sha256(src.encode()).hexdigest() for key,src in sources.items()},
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(checks),'failed':failures,'render_modified':False}))
    if failures:raise SystemExit('Photon Bayer2Float source contract moved: '+','.join(failures))

if __name__=='__main__':main()
