"""Stage A of the CS:GO -> CS2 port pipeline (runs in the cloud workspace).

  python3 prep.py <bsp> [<bsp> ...] [bspname=addonname ...] [--ports=existing_ports.txt]

Addon names default to the BSP name with version/bloat stripped (ports.clean_name: mg_x_v2_final -> mg_x).
With --ports, possible duplicates in existing_ports.txt are printed.
Environment: OUT (output root, default ./prep_out), PORTS (same as --ports=), BSPSRC (BSPSource launcher, default tools/bspsrc.sh,
written by setup_bspsrc.sh). Needs tools/addon_template/content and /game: copy them from <CS2>\\content\\csgo_addons\\addon_template
and <CS2>\\game\\csgo_addons\\addon_template (Valve's files, not in git).
Output per addon: OUT/<addon>/pc/<drive path>/..., OUT/<addon>/zips/, OUT/<addon>/manifest.json.

For each BSP: decompile with BSPSource (embedded files unpacked), rename to the
addon name, apply the Hammer re-save fix, and lay out every file where it goes
on the PC under OUT/<addon>/pc/<drive path>, plus a manifest.json of
(staged path, PC path) pairs ready for device_commit_files.

PC layout produced (same as the manual process):
  C:\\source1\\maps\\<addon>.vmf            Hammer-resave-fixed VMF (import input)
  C:\\source1\\maps\\<addon>.vmx            untouched BSPSource output (backup)
  C:\\source1\\maps\\<addon>\\...           decompiled embedded files
  C:\\source1\\cs2port\\assets\\<addon>[.N].zip  embedded materials/models (lower-cased), unpacked into csgo\\ by run_import.bat
  <CS2>\\content\\csgo_addons\\<addon>\\sounds\\...   embedded sounds (sanitised names)
  <CS2>\\content\\csgo_addons\\<addon>\\<other>\\...  any other embedded file
  addon skeleton copied from addon_template (what the Workshop Tools launcher does)
"""
import os, re, sys, json, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hammer_resave

ROOT = os.path.dirname(os.path.abspath(__file__))
BSPSRC = os.environ.get('BSPSRC', os.path.join(ROOT, 'bspsrc.sh'))
CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
S1 = r'C:\source1'
TEMPLATE = os.path.join(ROOT, 'addon_template')   # content/ and game/ template files
SKIP_EXT = {'.nav', '.ain'}                       # CS:GO nav/AI graphs are useless in CS2

def clean_sound(rel):
    parts = rel.replace('\\', '/').split('/')
    out = []
    for p in parts:
        p = p.lower()
        while re.search(r'\.(mp3|wav)\.(mp3|wav)$', p): p = p[:p.rfind('.')]
        p = re.sub(r'[^a-z0-9_.\-/]+', '_', p).strip('_') or 'x'
        p = re.sub(r'_+', '_', p)
        out.append(p)
    return '/'.join(out)

def winjoin(*a): return '\\'.join(x.strip('\\') for x in a)

def prep(bsp, addon, out_root, log):
    work = os.path.join(out_root, addon); shutil.rmtree(work, ignore_errors=True)
    dec = os.path.join(work, 'decompile'); os.makedirs(dec)
    base = os.path.splitext(os.path.basename(bsp))[0]
    r = subprocess.run([BSPSRC, '--unpack_embedded', '-o', os.path.join(dec, base + '.vmf'), bsp], capture_output=True, text=True)
    if not os.path.exists(os.path.join(dec, base + '.vmf')):
        raise RuntimeError('bspsrc failed for %s:\n%s' % (bsp, r.stdout + r.stderr))
    pc = os.path.join(work, 'pc'); manifest = []; notes = []
    def put(src_path, pc_path, data=None):
        staged = os.path.join(pc, pc_path.replace(':', '').replace('\\', '/'))
        os.makedirs(os.path.dirname(staged), exist_ok=True)
        if data is not None: open(staged, 'wb').write(data)
        else: shutil.copyfile(src_path, staged)
        manifest.append((staged, pc_path))
    raw = open(os.path.join(dec, base + '.vmf'), 'rb').read()
    text = raw.decode('utf-8', 'surrogateescape')
    vnotes = []
    fixed = hammer_resave.resave(text, vnotes).replace('\r\n', '\n').replace('\n', '\r\n')
    put(None, winjoin(S1, 'maps', addon + '.vmf'), fixed.encode('utf-8', 'surrogateescape'))
    put(None, winjoin(S1, 'maps', addon + '.vmx'), raw)
    if os.path.exists(os.path.join(dec, base + '.log')):
        put(os.path.join(dec, base + '.log'), winjoin(S1, 'maps', addon + '.log'))
    emb = os.path.join(dec, base); sound_map = {}
    if os.path.isdir(emb):
        for dp, _, fs in os.walk(emb):
            for f in fs:
                src = os.path.join(dp, f); rel = os.path.relpath(src, emb).replace(os.sep, '/')
                put(src, winjoin(S1, 'maps', addon, rel.replace('/', '\\')))
                top = rel.split('/')[0].lower(); ext = os.path.splitext(f)[1].lower()
                if top in ('materials', 'models'):
                    put(src, winjoin(CS2, 'csgo', rel.lower().replace('/', '\\')))
                elif top == 'sound':
                    new = clean_sound(rel.split('/', 1)[1])
                    sound_map[rel.split('/', 1)[1]] = 'sounds/' + new
                    put(src, winjoin(CS2, 'content', 'csgo_addons', addon, 'sounds', new.replace('/', '\\')))
                elif ext in SKIP_EXT:
                    notes.append('skipped %s (CS:GO nav/graph data, not usable in CS2)' % rel)
                else:
                    put(src, winjoin(CS2, 'content', 'csgo_addons', addon, rel.lower().replace('/', '\\')))
    if sound_map:
        put(None, winjoin(CS2, 'content', 'csgo_addons', addon, 'maps', addon + '_sound_renames.json'), json.dumps(sound_map, indent=1).encode())
    # addon skeleton (Workshop Tools "Create New Addon" copies addon_template and renames xxx_mapname_xxx)
    for side in ('content', 'game'):
        tdir = os.path.join(TEMPLATE, side)
        for dp, _, fs in os.walk(tdir):
            for f in fs:
                rel = os.path.relpath(os.path.join(dp, f), tdir).replace(os.sep, '/')
                if rel.startswith('maps/xxx_mapname_xxx.vmap'): continue   # the importer writes the real vmap
                if rel in ('addoninfo.txt', 'readonly_tools_asset_info.bin'): continue   # template markers: with them the launcher lists the addon as a read-only example
                data = open(os.path.join(dp, f), 'rb').read()
                put(None, winjoin(CS2, side, 'csgo_addons', addon, rel.replace('xxx_mapname_xxx', addon).replace('/', '\\')), data)
    # materials/models -> C:\source1\cs2port\assets\<addon>.zip (+ .2/.3/.4.zip, each <=14 MB) instead of
    # writing into csgo\ directly; run_import.bat unpacks them into csgo\ with tar -k (existing files kept)
    csg = winjoin(CS2, 'csgo') + '\\'
    loose = [(s, p) for s, p in manifest if p.startswith(csg)]
    manifest[:] = [(s, p) for s, p in manifest if not p.startswith(csg)]
    if loose:
        import zipfile
        part, cur, seen, zf = 1, 0, set(), None
        def zpath(n): return os.path.join(work, 'zips', addon + ('' if n == 1 else '.%d' % n) + '.zip')
        os.makedirs(os.path.join(work, 'zips'), exist_ok=True)
        zf = zipfile.ZipFile(zpath(1), 'w', zipfile.ZIP_DEFLATED, compresslevel=9)
        for s, p in loose:
            rel = p[len(csg):].replace('\\', '/')
            if rel in seen: continue
            seen.add(rel); sz = os.path.getsize(s)
            if cur and cur + sz > 14e6:
                zf.close(); part += 1; zf = zipfile.ZipFile(zpath(part), 'w', zipfile.ZIP_DEFLATED, compresslevel=9); cur = 0
            zf.write(s, rel); cur += os.path.getsize(s) // 3
        zf.close()
        if part > 4: notes.append('WARNING: %d asset zips, run_import.bat only unpacks 4' % part)
        for n in range(1, part + 1):
            manifest.append((zpath(n), winjoin(S1, 'cs2port', 'assets', os.path.basename(zpath(n)))))
    json.dump(manifest, open(os.path.join(work, 'manifest.json'), 'w'), indent=1)
    log.append('%s -> %s: %d files, %d embedded sounds%s' % (base, addon, len(manifest), len(sound_map), ''.join('\n   ' + n for n in notes + vnotes)))
    return manifest

if __name__ == '__main__':
    import ports
    args = sys.argv[1:]; names = {}; ports_txt = os.environ.get('PORTS')
    out_root = os.environ.get('OUT', os.path.join(os.getcwd(), 'prep_out'))
    bsps = []
    for a in args:
        if a.startswith('--ports='): ports_txt = a.split('=', 1)[1]
        elif '=' in a: k, v = a.split('=', 1); names[k] = v
        else: bsps.append(a)
    log = []
    for b in bsps:
        base = os.path.splitext(os.path.basename(b))[0]
        addon = names.get(base, ports.clean_name(base))
        if addon != base.lower(): log.append('%s: addon name cleaned to %s' % (base, addon))
        if ports_txt and os.path.exists(ports_txt):
            for r, ln in ports.check(open(ports_txt, encoding='utf-8', errors='replace').read(), [base])[base][1]:
                log.append('   POSSIBLE EXISTING PORT (%.2f): %s' % (r, ln))
        prep(b, addon, out_root, log)
    print('\n'.join(log))
