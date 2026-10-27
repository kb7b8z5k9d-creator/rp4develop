#!/bin/bash
# Rebuild DroidDeck-MaliBridge APK with a locally built bridge server (libvkbridge_server.so +
# libvkbridge_jni.so), zipalign it and sign it with the Android debug key.
#   tools/repack-apk.sh <original.apk> <dir with arm64-v8a/libvkbridge_*.so> <out.apk> [extra.list]
# extra.list: optional lines "path/inside/apk=local/file" for further replacements (e.g. a runtime
# preload under assets/linuxfs/).
set -euo pipefail
src=$1
libs=$2/arm64-v8a
out=$3
extra=${4:-/dev/null}
bt=${ANDROID_SDK_ROOT:-$HOME/AppData/Local/Android/Sdk}/build-tools/37.0.0
export JAVA_HOME="C:/Program Files/Android/Android Studio/jbr"
export PATH="$JAVA_HOME/bin:$PATH"
work=$(mktemp -d)
python - "$src" "$libs" "$work/unsigned.apk" "$extra" <<'EOF'
import sys, zipfile, os
src, libs, dst, extra = sys.argv[1:5]
replace = {"lib/arm64-v8a/libvkbridge_server.so": os.path.join(libs, "libvkbridge_server.so"),
           "lib/arm64-v8a/libvkbridge_jni.so": os.path.join(libs, "libvkbridge_jni.so")}
if os.path.isfile(extra):
    for line in open(extra, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            k, v = line.split("=", 1)
            replace[k] = v
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
    for item in zin.infolist():
        if item.filename.startswith("META-INF/") and item.filename.endswith((".RSA", ".SF", ".MF", ".EC")):
            continue
        if item.filename in replace:
            with open(replace[item.filename], "rb") as f:
                data = f.read()
            print("replaced", item.filename, len(data), "bytes")
        else:
            data = zin.read(item.filename)
        zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
        zi.compress_type = item.compress_type
        zi.external_attr = item.external_attr
        zout.writestr(zi, data, compress_type=item.compress_type)
EOF
"$bt/zipalign.exe" -f -p 4 "$work/unsigned.apk" "$work/aligned.apk"
"$bt/apksigner.bat" sign --ks "$HOME/.android/debug.keystore" --ks-pass pass:android --key-pass pass:android \
    --out "$out" "$work/aligned.apk"
"$bt/apksigner.bat" verify --print-certs "$out" | head -3
rm -rf "$work"
echo "wrote $out"
