#!/usr/bin/env bash
set -euo pipefail
source_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(CDPATH= cd -- "$source_dir/../.." && pwd)"
root="${ANDROID_NDK_HOME:-}"
if [[ ! -f "$root/build/cmake/android.toolchain.cmake" ]]; then
  sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/usr/local/lib/android/sdk}}"
  if [[ -d "$sdk/ndk" ]]; then
    root="$(find "$sdk/ndk" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
  fi
fi
if [[ ! -f "$root/build/cmake/android.toolchain.cmake" ]]; then
  echo 'Android NDK was not found in ANDROID_NDK_HOME or ANDROID_HOME/ndk' >&2
  exit 2
fi
out="${1:-/tmp/hb74-ndk}"
for arch in arm64-v8a x86_64; do
  cmake -S "$source_dir" -B "$out/$arch" \
    -DCMAKE_TOOLCHAIN_FILE="$root/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$arch" -DANDROID_PLATFORM=android-24 -DCMAKE_BUILD_TYPE=Release
  cmake --build "$out/$arch" --config Release --parallel 2
  test -s "$out/$arch/libhbfinal74.so"
  file "$out/$arch/libhbfinal74.so"
done
printf '%s\n' 'STAGE74_REAL_ANDROID_NDK_ARM64_X86_64_PASS'
