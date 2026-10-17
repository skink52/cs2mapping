#!/bin/sh
# usage: setup_bspsrc.sh <path to staged C:\source1\bspsrc-windows\lib\modules> <dest dir>
# Extracts BSPSource from the BSPSource jlink image in C:\source1\bspsrc-windows and patches the Java 24 class files so they run on the workspace's Java 21.
set -e
MOD="$1"; DEST="$2"; mkdir -p "$DEST/jimg"
jimage extract --dir "$DEST/jimg" "$MOD"
python3 - "$DEST/jimg" <<'PY'
import os,struct,sys
r=sys.argv[1]
for m in os.listdir(r):
    if m.startswith(('java.','jdk.')): continue
    for dp,_,fs in os.walk(os.path.join(r,m)):
        for f in fs:
            if f.endswith('.class'):
                p=os.path.join(dp,f); b=bytearray(open(p,'rb').read())
                if struct.unpack('>H',b[6:8])[0]>65: b[6:8]=struct.pack('>H',65); open(p,'wb').write(b)
PY
mods=$(ls "$DEST/jimg" | grep -v '^java\.\|^jdk\.' | sed "s#^#$DEST/jimg/#" | paste -sd:)
printf '#!/bin/sh\nexec java -p "%s" -m info.ata4.bspsrc.app/info.ata4.bspsrc.app.src.BspSourceLauncher "$@" 2>&1 | grep -v JAVA_TOOL\n' "$mods" > "$DEST/bspsrc.sh"
chmod +x "$DEST/bspsrc.sh"; echo "ready: $DEST/bspsrc.sh"
