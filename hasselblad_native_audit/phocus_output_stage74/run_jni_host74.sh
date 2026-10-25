#!/bin/sh
set -eu
base="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
out="${1:-/tmp/hb-jni74}"
mkdir -p "$out/classes"
cc="${CC:-gcc}"
java_home="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")}" 
set -- \
 "$base/phocus_gradient_stage61/gradient_maps61.c" \
 "$base/phocus_interpolation_stage62/interpolation62.c" \
 "$base/phocus_green_stage63/green63.c" \
 "$base/phocus_inline_stage67/raw_gradient67.c" \
 "$base/phocus_inline_stage67/green_site_mask67.c" \
 "$base/phocus_coloursite_stage68/colour_gradient68.c" \
 "$base/phocus_coloursite_stage68/colour_site68.c" \
 "$base/phocus_schedule_stage66/schedule66.c" \
 "$base/phocus_schedule_stage66/wiring66.c" \
 "$base/phocus_integrated_stage69/interpolate69.c" \
 "$base/phocus_frame_stage73/frame73.c" \
 "$base/phocus_noise_stage65/noise65.c" \
 "$base/phocus_colour_stage64/ycc64.c" \
 "$base/phocus_output_stage74/output74.c" \
 "$base/phocus_output_stage74/frame74.c" \
 "$base/phocus_output_stage74/jni_bridge74.c"
"$cc" -std=c11 -O2 -fPIC -shared -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off \
 -I"$java_home/include" -I"$java_home/include/linux" \
 "$@" -lm -o "$out/libhbfinal74.so"
source="$base/phocus_output_stage74"
javac -d "$out/classes" \
 "$source/java/com/particlesdevs/photoncamera/hasselblad/HasselbladFinalRaw74.java" \
 "$source/Stage74JvmTest.java"
java -Djava.library.path="$out" -cp "$out/classes" Stage74JvmTest
