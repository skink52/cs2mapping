"""Make import_map_auto.py: Valve's import_map_community.py without the "Enter to Continue, Esc to Quit" prompt.

run_import.bat runs Valve's map importer once per queued map, unattended, so the keypress prompt has to go.
Valve's script isn't redistributed in this repo; this patches your own copy instead.

    py make_import_map_auto.py ["<CS2>\\game\\csgo\\import_scripts\\import_map_community.py"] [output path]

Defaults: the standard Steam library path for input, C:\\source1\\cs2port\\import_map_auto.py for output
(run_import.bat copies it next to Valve's script before every import).
"""
import os, re, sys

CS2 = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CS2, r"game\csgo\import_scripts\import_map_community.py")
dst = sys.argv[2] if len(sys.argv) > 2 else r"C:\source1\cs2port\import_map_auto.py"

text = open(src, encoding="utf-8", errors="replace").read()
nl = "\r\n" if "\r\n" in text else "\n"
pat = re.compile(r'utl\.print_color\( "WARNING.*?\n(bRunImport = True\r?\nwhile True:.*?break\r?\n\r?\n)', re.S)
m = pat.search(text)
if not m:
    if "cs2port: unattended copy" in text:
        sys.exit("%s is already patched" % src)
    sys.exit("could not find the Enter/Esc prompt in %s - Valve may have changed the script; patch it by hand" % src)
new = "# cs2port: unattended copy of import_map_community.py - the Enter/Esc confirmation is skipped" + nl + "bRunImport = True" + nl
text = text[:m.start()] + new + text[m.end():]
open(dst, "w", encoding="utf-8", newline="").write(text)
print("wrote", dst)
