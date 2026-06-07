#!/bin/bash
set -e

export ANDROID_HOME="$HOME/android-sdk"
BT="$ANDROID_HOME/build-tools/34.0.0"
PLATFORM="$ANDROID_HOME/platforms/android-34"
PROJECT="$HOME/deskflow-apk"
OUT="$PROJECT/build"
SRC="$PROJECT/app/src/main"

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/gen"

echo "[1/7] Compiling Java..."
javac --release 11 -cp "$PLATFORM/android.jar" -d "$OUT/classes" \
  "$SRC/java/com/deskflow/MainActivity.java"

echo "[2/7] Converting to DEX..."
"$BT/d8" --lib "$PLATFORM/android.jar" --output "$OUT/dex.zip" \
  "$OUT/classes/com/deskflow/"*.class

echo "[3/7] Compiling resources..."
mkdir -p "$OUT/compiled"
for file in $(find "$SRC/res" -type f); do
  "$BT/aapt2" compile -o "$OUT/compiled/" "$file" 2>/dev/null || true
done

echo "[4/7] Linking resources..."
FLAT_FILES=$(find "$OUT/compiled" -name "*.flat")
"$BT/aapt2" link --manifest "$SRC/AndroidManifest.xml" --auto-add-overlay \
  -I "$PLATFORM/android.jar" -o "$OUT/resources.apk" $FLAT_FILES

echo "[5/7] Assembling APK..."
cp "$OUT/resources.apk" "$OUT/app-unsigned.apk"
cd "$OUT"
unzip -o -q dex.zip
zip -q "$OUT/app-unsigned.apk" classes.dex
cd "$PROJECT"
(cd "$SRC" && zip -q -r "$OUT/app-unsigned.apk" "assets/www")

echo "[6/7] Aligning..."
"$BT/zipalign" -f -p 4 "$OUT/app-unsigned.apk" "$OUT/app-aligned.apk"

echo "[7/7] Signing..."
if [ ! -f "$PROJECT/debug.keystore" ]; then
  keytool -genkey -v -keystore "$PROJECT/debug.keystore" \
    -alias debug -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android -dname "CN=DeskFlow"
fi
"$BT/apksigner" sign \
  --ks "$PROJECT/debug.keystore" --ks-pass pass:android \
  --key-pass pass:android \
  --out "$OUT/app-debug.apk" "$OUT/app-aligned.apk"

echo "✅ APK: $OUT/app-debug.apk ($(ls -lh "$OUT/app-debug.apk" | awk '{print $5}'))"
