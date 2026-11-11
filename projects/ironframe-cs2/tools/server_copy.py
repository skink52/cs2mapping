"""server_copy.py: put an IRONFRAME map's compiled files on the LOCAL test server, or take them off again.

A dedicated server does not mount game/csgo_addons/<addon>: it needs the map .vpk in game/csgo/maps and the addon's loose compiled
files (script, models, particles, sound events, HUD, materials) under game/csgo. This copies them and writes a manifest of every file
it created, so `remove` deletes exactly those and nothing else. A file that already exists on the server and is not in the manifest
is never overwritten (it is listed as SKIPPED: stock or someone else's).

usage:  python -I tools/server_copy.py copy   mg_ironframe_dunes [--server C:/cs2server]
        python -I tools/server_copy.py remove mg_ironframe_dunes [--server C:/cs2server]
The manifest: logs/server_copy_<addon>.txt (project folder, not in git). Local test server only: never the live server.
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
DIRS = ['maps', 'materials', 'models', 'panorama', 'particles', 'postprocess', 'resource', 'soundevents', 'sounds']   # not cfg, not the tools' caches


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('copy', 'remove'): sys.exit(__doc__)
    what, addon = sys.argv[1], sys.argv[2]
    server = sys.argv[sys.argv.index('--server') + 1] if '--server' in sys.argv else r'C:\cs2server'
    src = os.path.join(CS2, 'game', 'csgo_addons', addon)
    dst = os.path.join(server, 'game', 'csgo')
    man = os.path.join(PROJ, 'logs', 'server_copy_%s.txt' % addon)
    if not os.path.isdir(dst): sys.exit('no server at ' + dst)
    mine = set()
    if os.path.exists(man): mine = set(l.strip() for l in open(man, encoding='utf-8') if l.strip())
    if what == 'remove':
        n = 0
        for rel in sorted(mine):
            p = os.path.join(dst, rel)
            if os.path.isfile(p): os.remove(p); n += 1
        for rel in sorted(set(os.path.dirname(r) for r in mine), key=len, reverse=True):      # folders this left empty
            p = os.path.join(dst, rel)
            while rel and os.path.isdir(p) and not os.listdir(p):
                os.rmdir(p); rel = os.path.dirname(rel); p = os.path.join(dst, rel)
        if os.path.exists(man): os.remove(man)
        print('removed %d files of %s from %s' % (n, addon, dst)); return
    if not os.path.isdir(src): sys.exit('no compiled addon at ' + src)
    copied = same = skipped = size = 0
    os.makedirs(os.path.dirname(man), exist_ok=True)
    with open(man, 'a', encoding='utf-8') as mf:
        for d in DIRS:
            for root, _, files in os.walk(os.path.join(src, d)):
                for f in files:
                    s = os.path.join(root, f); rel = os.path.relpath(s, src); t = os.path.join(dst, rel)
                    if os.path.exists(t) and rel not in mine:
                        skipped += 1
                        if skipped <= 20: print('SKIPPED (exists on the server, not ours): ' + rel)
                        continue
                    st = os.stat(s)
                    if os.path.exists(t) and os.path.getsize(t) == st.st_size and abs(os.path.getmtime(t) - st.st_mtime) < 2: same += 1; continue
                    os.makedirs(os.path.dirname(t), exist_ok=True)
                    shutil.copy2(s, t); copied += 1; size += st.st_size
                    if rel not in mine: mine.add(rel); mf.write(rel + '\n')
                    if copied % 2000 == 0: print('  %d files, %.0f MB ...' % (copied, size / 1e6), flush=True)
    print('%s -> %s: %d copied (%.0f MB), %d up to date, %d skipped; manifest %s (%d files)' % (addon, dst, copied, size / 1e6, same, skipped, man, len(mine)))


if __name__ == '__main__':
    main()
