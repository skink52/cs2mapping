"""Run the pipeline in a local workspace on the PC instead of the cloud one (Claude Code on the PC).

  python pclocal.py deliver <manifest.json> [...] [--force]   copy prep.py's (staged, PC path) pairs to the PC paths
  python pclocal.py root <addon> [<root>]                     build the stage C working root for an addon
  python pclocal.py apply <addon> [<root>]                    copy stage C's output back to the addon (only changed files, vmaps backed up first)

<root> defaults to C:\\source1\\cs2port\\work. Layout: content\\<addon> (a junction to the real addon: remove it with rmdir, never delete through it),
source1\\maps\\<addon>.vmf, vpk\\cs2_pak01_dir.vpk + csgo_pak01_dir.vpk, embedded\\<addon> (unpacked from maps\\<addon>_embedded*.zip), out\\.
"""
import datetime, filecmp, glob, json, os, shutil, subprocess, sys, zipfile

CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
S1 = r'C:\source1'
DEFAULT_ROOT = os.path.join(S1, 'cs2port', 'work')

def deliver(manifests, force):
    pairs = [p for m in manifests for p in json.load(open(m))]
    clash = [pc for staged, pc in pairs if os.path.exists(pc) and not filecmp.cmp(staged, pc, shallow=False)]
    if clash and not force:
        sys.exit('nothing copied: these already exist and differ (--force to overwrite):\n  ' + '\n  '.join(clash))
    for staged, pc in pairs:
        os.makedirs(os.path.dirname(pc), exist_ok=True)
        shutil.copyfile(staged, pc)
        if os.path.getsize(pc) != os.path.getsize(staged): sys.exit('size mismatch after copying ' + pc)
    print('%d files delivered' % len(pairs))

def copy_if_changed(src, dst):
    if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst) and os.path.getmtime(src) <= os.path.getmtime(dst): return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)

def root(addon, r):
    link = os.path.join(r, 'content', addon); real = os.path.join(CS2, 'content', 'csgo_addons', addon)
    if not os.path.isdir(real): sys.exit('no addon content at ' + real)
    os.makedirs(os.path.dirname(link), exist_ok=True)
    if not os.path.exists(link):
        subprocess.run(['cmd', '/c', 'mklink', '/J', link, real], check=True, stdout=subprocess.DEVNULL)
    copy_if_changed(os.path.join(S1, 'maps', addon + '.vmf'), os.path.join(r, 'source1', 'maps', addon + '.vmf'))
    copy_if_changed(os.path.join(CS2, 'game', 'csgo', 'pak01_dir.vpk'), os.path.join(r, 'vpk', 'cs2_pak01_dir.vpk'))
    copy_if_changed(os.path.join(S1, 'pak01_dir.vpk'), os.path.join(r, 'vpk', 'csgo_pak01_dir.vpk'))
    emb = os.path.join(r, 'embedded', addon); n = 0
    for z in glob.glob(os.path.join(S1, 'maps', addon + '_embedded*.zip')):
        with zipfile.ZipFile(z) as f:
            f.extractall(emb); n += len(f.namelist())
    # the importer turns spaces in material paths into underscores, so the vmap asks for names the BSP never packed
    # (mg_arcs_multigames: 49 of 52 "missing" textures were packed as "materials/MISC/128x128 arena screenie.vmt"): add underscore copies
    alias = 0
    for dp, _, fs in os.walk(emb):
        for fn in fs:
            rel = os.path.relpath(os.path.join(dp, fn), emb)
            if ' ' not in rel: continue
            dst = os.path.join(emb, rel.replace(' ', '_'))
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(os.path.join(dp, fn), dst); alias += 1
    print('root %s ready for %s (%d embedded files%s)' % (r, addon, n, ', %d underscore copies of names with spaces' % alias if alias else ''))

def apply(addon, r):
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); copied = 0
    for src_root, dst_root in ((os.path.join(r, 'out', addon), os.path.join(CS2, 'content', 'csgo_addons', addon)),
                               (os.path.join(r, 'out', addon + '_game'), os.path.join(CS2, 'game', 'csgo_addons', addon))):
        for dp, _, fs in os.walk(src_root):
            for f in fs:
                src = os.path.join(dp, f); dst = os.path.join(dst_root, os.path.relpath(src, src_root))
                if os.path.exists(dst):
                    if filecmp.cmp(src, dst, shallow=False): continue
                    if f.lower().endswith('.vmap'): shutil.copy2(dst, dst + '.bak_' + stamp)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst); copied += 1
    print('%d changed files copied back for %s' % (copied, addon))

if __name__ == '__main__':
    args = sys.argv[1:]; force = '--force' in args; args = [a for a in args if a != '--force']
    if len(args) < 2: sys.exit(__doc__)
    cmd = args[0]
    if cmd == 'deliver': deliver(args[1:], force)
    elif cmd == 'root': root(args[1], args[2] if len(args) > 2 else DEFAULT_ROOT)
    elif cmd == 'apply': apply(args[1], args[2] if len(args) > 2 else DEFAULT_ROOT)
    else: sys.exit(__doc__)
