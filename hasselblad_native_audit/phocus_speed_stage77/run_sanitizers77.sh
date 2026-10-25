#!/bin/sh
set -eu
base="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
out="${1:-/tmp/hb77-sanitizers}"
mkdir -p "$out"
python3 - "$base" "$out" <<'PY'
from pathlib import Path
import re,subprocess,sys,os
base,out=map(Path,sys.argv[1:]);script=(base/'phocus_output_stage74/run_host74.sh').read_text()
units=list(dict.fromkeys(base/p for p in re.findall(r'"\$base/([^"\n]+\.c)"',script) if '/test_' not in p))
subprocess.run(['cc','-std=c11','-pthread','-O2','-g','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-fsanitize=address,undefined','-fno-sanitize-recover=all',*map(str,units),str(base/'phocus_speed_stage77/frame77.c'),str(base/'phocus_speed_stage77/test77.c'),'-lm','-o',str(out/'test77')],check=True)
subprocess.run([str(out/'test77')],check=True,env={**os.environ,'ASAN_OPTIONS':os.environ.get('ASAN_OPTIONS','detect_leaks=1')})
PY
