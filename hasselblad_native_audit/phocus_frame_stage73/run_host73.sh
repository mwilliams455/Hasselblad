#!/bin/sh
set -eu
repo="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
work="${1:-/tmp/hb-frame73-host}"
mkdir -p "$work"
cc="${CC:-gcc}"
base="$repo/hasselblad_native_audit"
source="$base/phocus_frame_stage73"
set -- "$base/phocus_gradient_stage61/gradient_maps61.c" \
 "$base/phocus_interpolation_stage62/interpolation62.c" \
 "$base/phocus_green_stage63/green63.c" \
 "$base/phocus_inline_stage67/raw_gradient67.c" \
 "$base/phocus_inline_stage67/green_site_mask67.c" \
 "$base/phocus_coloursite_stage68/colour_gradient68.c" \
 "$base/phocus_coloursite_stage68/colour_site68.c" \
 "$base/phocus_schedule_stage66/schedule66.c" \
 "$base/phocus_schedule_stage66/wiring66.c" \
 "$base/phocus_integrated_stage69/interpolate69.c" \
 "$source/frame73.c"
"$cc" -std=c11 -O2 -g -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off \
 -fsanitize=address,undefined -fno-sanitize-recover=all "$@" \
 "$source/test_frame73.c" -lm -o "$work/test_frame73"
ASAN_OPTIONS=detect_leaks=1 "$work/test_frame73"
JAVA_HOME="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")}" 
mkdir -p "$work/classes"
"$cc" -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared -fno-fast-math -ffp-contract=off \
 -I"$JAVA_HOME/include" -I"$JAVA_HOME/include/linux" \
 "$@" "$source/jni_bridge73.c" -lm -o "$work/libhbframe73.so"
javac -d "$work/classes" \
 "$source/java/com/particlesdevs/photoncamera/hasselblad/HasselbladPreNoise73.java" \
 "$source/Frame73JvmTest.java"
java -Djava.library.path="$work" -cp "$work/classes" Frame73JvmTest
