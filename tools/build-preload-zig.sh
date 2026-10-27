#!/bin/bash
# Build DroidDeck's ARM64 runtime preload (libblsession.so) without Docker, with Zig's bundled
# glibc cross toolchain (pip install ziglang). Sources come from a git ref of the DroidDeck
# checkout (the one the installed runtime was built from), with the working tree's noexec.c on top.
#   tools/build-preload-zig.sh <droiddeck checkout> <git ref> <out dir> [exports.map]
# exports.map (optional): a linker version script listing the shipped library's exports, so the
# rebuilt one exports exactly the same symbols (make it from llvm-nm -D of the original).
set -euo pipefail
repo=$1; ref=$2; out=$3; map=${4:-}
ndkbin=${ANDROID_SDK_ROOT:-$HOME/AppData/Local/Android/Sdk}/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin
work=$(mktemp -d)
mkdir -p "$out"
git -C "$repo" archive "$ref" tools/linuxfs/preload tools/quest app/src/main/cpp/adrenotools/src/hook app/src/main/cpp/venc | tar -x -C "$work"
cp "$repo/tools/linuxfs/preload/noexec.c" "$work/tools/linuxfs/preload/noexec.c"
cd "$work"
python -m ziglang cc -target aarch64-linux-gnu.2.28 -shared -fPIC -O2 -Wall -pthread \
    ${map:+-Wl,--version-script=$map} -o "$out/libblsession.so" tools/linuxfs/preload/*.c -ldl
"$ndkbin/llvm-strip.exe" --strip-unneeded "$out/libblsession.so"
"$ndkbin/llvm-readelf.exe" -h "$out/libblsession.so" | grep -E 'Machine'
"$ndkbin/llvm-nm.exe" -D --undefined-only "$out/libblsession.so" | grep -o 'GLIBC_[0-9.]*' | sort -u | tr '\n' ' '; echo
rm -rf "$work"
echo "built $out/libblsession.so"
