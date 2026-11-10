"""IRONFRAME frame models: every frame in data/frames.json from the GMod Workshop to CS2 props with create/mdl2cs2.py.

usage: python -I tools/frames.py [--only key,..] [--merge] [--all] [--no-animate] [--download] [--prune] [--no-preview] [--no-compile] [--skip-existing]
  --merge          with --only: models.json keeps every other frame's entry as it is (only the listed frames are rewritten)
  source 'tripo'   frames.json entries with a 'glb' path (rigged Tripo GLB) go through create/glbrig.py inside mdl2cs2
  --download       fetch missing Workshop items with SteamCMD (anonymous), one at a time; otherwise only items already in
                   <steamcmd>/steamapps/workshop/content/4000/<id>/ or already extracted are converted
  --prune          after converting, delete the SteamCMD copy (only items this tool downloaded) and the extract
  --skip-existing  do not reconvert frames whose vmdls are already in out/addon (still re-reads their reports)
  strip            data/frames.json frames.<key>.strip removes the weapons a source model carries (the game hands every mech its own weapon
                   props): {"bodygroups": {part: index of the empty choice}, "drop_parts": [part name patterns], "drop_bones": "<regex>",
                   "drop_materials": [texture names], "drop_boxes": ["x0,y0,z0,x1,y1,z1" in source units: connected pieces inside a box go
                   (one-skin Tripo meshes; `mdl2cs2.py <glb> x y --list-pieces` prints them)], "what": "..."} -> mdl2cs2 --bodygroup /
                   --drop-parts / --drop-bones / --drop-materials / --drop-boxes.
                   The frame is scaled to its class height WITHOUT the stripped parts; material files nothing references afterwards are deleted.
Per frame: download -> extract to <work>/extract/<id> (create/playermodels/gma.py) -> pick the .mdl by the catalog glob (tallest
candidate: full-scale over human-scale variants; no arms/viewmodel files) -> mdl2cs2 with --height = class height and
--split legs/upper (hover/static frames: upper only) -> compile with resourcecompiler in the scratch addon mg_ironframe_dunes ->
out/addon/_gen/models.json (INTERFACES §4 "frames"), docs/MODELS.md, docs/CREDITS.md, preview/frames/<key>.png.
A frame that fails is reported and the rest continue; the exit code is 1 if any failed.
"""
import glob, json, os, re, shutil, subprocess, sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PROJ))
CREATE = os.path.join(REPO, 'create')
sys.path.insert(0, os.path.join(CREATE, 'playermodels'))
import gma                                                    # noqa: E402

RC = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe'
ADDON = 'mg_ironframe_dunes'
CONTENT = r'C:\source1\links\content_addons\%s' % ADDON
GAME = r'C:\source1\links\game_addons\%s' % ADDON
# resourcecompiler must see the real path (it finds the addon from it; through the junction it says "Unable to determine mod")
CONTENT_REAL = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\%s' % ADDON
TEMPLATE = r'C:\source1\cs2port\tools\addon_template'
MIN_FREE_GB = 3.0
ORDER = ['ac3_moa', 'me3_atlas', 'fear3_mule', 'me2_loki', 'ac4a_noblesse', 'ac4a_whiteglint', 'ac4a_hari',
         'tf_atlas', 'tf_stryder', 'tf_ogre', 'gundam_rx78', 'gundam_barbatos', 'gundam_unicorn',
         'ac4a_oldking', 'ac4_berlioz', 'ac4_002b', 'ac4_aretha', 'ac4_normal', 'tf2_legion', 'tf2_ronin']
SKIP_FILES = ('_arms', 'arms_', 'c_arms', 'v_', '_vm', 'ragdoll', 'gib', 'viewmodel', 'hands',
              '_posed', '_animated', '_sky', 'humanscale', 'flightpose', 'shieldfix', '_weapon', 'obj_')   # variants of Moon.'s AC items
# catalog globs that miss the pack's real file (typo'd folder, full-scale variant under another name, a better NORMAL)
GLOB_FIX = {'tf_ogre': 'models/orge/orge.mdl', 'gundam_rx78': 'models/**/rx-78-2_gundam_ragdoll_fs.mdl',
            'ac4a_whiteglint': 'models/ac4/garage/ac_abemarsh_whiteglint.mdl', 'ac4_normal': 'models/ac4/ene/enemy_algebra_mamluk.mdl'}
# bone names that mean legs across the packs: ValveBiped, Moon.'s romaji (kosi hip, momo thigh, sune shin, kakato heel, tuma toe, asi foot),
# Titanfall 2 (def_l_thigh/knee/ankle/ball), ME3 (Hip/Calf/Heel); the catalog regex is OR-ed with this
LEGS_ANY = r'(?i)thigh|knee|calf|ankle|ball|foot|toe|heel|pelvis|hip|lower.?body|(^|_)(momo|sune|kakato|tuma|asi|kosi|bb|kaka_w)'
ARMS_DOWN = 65

# frames whose source is not one plain .mdl: assembled from a pack's part files, or a stand-in when the real item is missing
SPECIAL = {
    'ac4a_noblesse': {'item': 3708956431, 'mdls': ['models/naki/ac4a/noblesse oblige - head.mdl', 'models/naki/ac4a/noblesse oblige - core.mdl',
                                                   'models/naki/ac4a/noblesse oblige - arm.mdl', 'models/naki/ac4a/noblesse oblige - leg.mdl'],
                      'note': 'assembled from the model pack\'s head/core/arm/leg files (the 193 MB single-model item is not needed)'},
}
FALLBACK = {   # used when the frame's own item is not available (not downloaded, or its mesh unusable)
    'ac4a_hari': {'item': 3708956431, 'mdls': ['models/naki/ac4/aaliyah.mdl'], 'args': ['--bodygroup', 'back cannon=1'],
                  'note': 'stand-in: 03-AALIYAH (Hari\'s chassis) from the model pack, back cannon off'},
}
UNUSABLE = {   # pack files checked and rejected (reason goes in MODELS.md)
    3708956431: {'whiteglint': 'whiteglint-part1/2.mdl: the mesh is not in its bind pose (each body part sits in its own frame; torso above the head)'},
}


def log(*a):
    print(*a, flush=True)


def save_state(path, state, sections=('frames', 'downloaded')):
    """writes only this tool's sections of <work>/state.json (weapon_props.py owns 'weapons'), so concurrent runs don't clobber each other"""
    cur = {}
    if os.path.exists(path):
        try: cur = json.load(open(path, encoding='utf-8'))
        except ValueError: cur = {}
    for k in sections:
        if k in state: cur[k] = state[k]
    json.dump(cur, open(path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def free_gb(path='C:\\'):
    return shutil.disk_usage(path).free / 1e9


def item_dir(p, wid):
    return os.path.join(os.path.dirname(p['steamcmd']), 'steamapps', 'workshop', 'content', '4000', str(wid))


def has_archive(d):
    return os.path.isdir(d) and any(f.endswith(('.gma', '.bin')) for f in os.listdir(d))


def download(p, wid, state):
    d = item_dir(p, wid)
    if has_archive(d): return d
    if free_gb() < MIN_FREE_GB: raise RuntimeError('only %.1f GB free: not downloading %s' % (free_gb(), wid))
    t = time.time()
    r = subprocess.run([p['steamcmd'], '+login', 'anonymous', '+workshop_download_item', '4000', str(wid), '+quit'],
                       capture_output=True, text=True, errors='replace', timeout=1800)
    ok = [l for l in r.stdout.splitlines() if 'Success' in l or 'ERROR' in l or 'Failed' in l]
    log('  download %s: %s (%.0f s)' % (wid, ok[-1].strip()[:120] if ok else 'no result line', time.time() - t))
    if has_archive(d):
        state.setdefault('downloaded', []).append(int(wid)); return d
    return None


def extract(p, wid):
    out = os.path.join(p['work'], 'extract', str(wid))
    if os.path.isdir(out) and glob.glob(os.path.join(out, 'models', '**', '*.mdl'), recursive=True): return out
    src = item_dir(p, wid)
    arch = [f for f in glob.glob(os.path.join(src, '*')) if f.endswith(('.gma', '.bin'))]
    if not arch: return None
    for a in arch:
        info, files = gma.extract(a, out, only=('models/', 'materials/'))
        log('  extract %s: %d files from %s (%s)' % (wid, len(files), os.path.basename(a), info.get('name', '')[:50]))
    return out


def mdl_height(path):
    try:
        from srcmdl import SrcModel
        m = SrcModel(path)
        return float(m.V[:, 2].max() - m.V[:, 2].min()), len(m.bones), len(m.V)
    except Exception as e:
        return -1.0, 0, 0


def pick_mdl(root, pattern):
    """the catalog glob (models/**/x.mdl) -> the tallest usable candidate (full-scale over human-scale, no arms/viewmodels)"""
    cands = glob.glob(os.path.join(root, *pattern.split('/')), recursive=True)
    if not cands:                                           # the pack names it differently: try the key word anywhere in the name
        base = os.path.basename(pattern)
        cands = glob.glob(os.path.join(root, 'models', '**', '*' + base.lstrip('*')), recursive=True)
    good = [c for c in cands if not any(s in os.path.basename(c).lower() for s in SKIP_FILES)]
    cands = good or cands
    scored = []
    for c in cands:
        h, nb, nv = mdl_height(c)
        if h > 0: scored.append((h, nv, c))
    if not scored: return None, cands
    scored.sort(key=lambda t: (-round(t[0]), -t[1], len(t[2])))      # tallest, then most detailed, then the plainest name
    return scored[0][2], [(round(h), nv, os.path.relpath(c, root).replace('\\', '/')) for h, nv, c in scored]


def run_mdl2cs2(mdls, key, height, legs, out_root, preview_png, report_json, extra):
    cmd = [sys.executable, '-X', 'utf8', '-I', os.path.join(CREATE, 'mdl2cs2.py'), ','.join(mdls), out_root, key,
           '--sub', 'models/ifr/frames/%s' % key, '--matsub', 'materials/ifr/frames/%s' % key, '--height', str(height),
           '--split', ('legs=(?i)(?:%s)|(?:%s);upper=.*' % (legs.replace('(?i)', ''), LEGS_ANY.replace('(?i)', ''))) if legs else 'upper=.*', '--report', report_json, '--surface', 'metal',
           '--dynamic', '--damage-skins', '--arms-down', str(ARMS_DOWN)] + ([] if '--no-animate' in sys.argv else ['--animate']) + [
           '--credit', 'GMod Workshop port, see docs/CREDITS.md'] + (['--preview', preview_png] if preview_png else []) + list(extra)
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
    return r.returncode, (r.stdout + r.stderr), time.time() - t


def strip_args(strip):
    """frames.json 'strip' -> mdl2cs2 arguments (see the module docstring)"""
    a = []
    for part, ix in (strip.get('bodygroups') or {}).items(): a += ['--bodygroup', '%s=%d' % (part, ix)]
    if strip.get('drop_parts'): a += ['--drop-parts', ','.join(strip['drop_parts'])]
    if strip.get('drop_bones'): a += ['--drop-bones', strip['drop_bones']]
    if strip.get('drop_materials'): a += ['--drop-materials', ','.join(strip['drop_materials'])]
    if strip.get('drop_boxes'): a += ['--drop-boxes', ';'.join(strip['drop_boxes'])]
    return a


def prune_unreferenced(out_root, key):
    """delete the material files of a frame that nothing references any more (the vmats and textures only the stripped parts used):
    kept = every vmat named in the frame's vmdls (default and damage material groups) and every file those vmats name; -> names deleted"""
    mdir = os.path.join(out_root, 'materials', 'ifr', 'frames', key); rel = 'materials/ifr/frames/%s/' % key
    if not os.path.isdir(mdir): return []
    keep = set()
    for v in glob.glob(os.path.join(out_root, 'models', 'ifr', 'frames', key, '*.vmdl')):
        keep |= {m.lower() for m in re.findall(re.escape(rel) + r'([^"/]+\.vmat)', open(v, encoding='utf-8', errors='replace').read())}
    if not keep: return []                                   # no vmdl names a material here: leave the folder alone
    for vm in list(keep):
        q = os.path.join(mdir, vm)
        if os.path.exists(q): keep |= {m.lower() for m in re.findall(re.escape(rel) + r'([^"/]+)"', open(q, encoding='utf-8', errors='replace').read())}
    gone = []
    for f in os.listdir(mdir):
        q = os.path.join(mdir, f)
        if os.path.isfile(q) and f.lower() not in keep: os.remove(q); gone.append(f)
    return gone


def ensure_addon():
    if not os.path.isdir(GAME):
        os.makedirs(os.path.join(GAME, 'cfg', 'maps'), exist_ok=True); os.makedirs(os.path.join(GAME, 'maps'), exist_ok=True)
        for d in ('postprocess', 'soundevents', 'sounds'):
            s = os.path.join(TEMPLATE, 'game', d)
            if os.path.isdir(s) and not os.path.isdir(os.path.join(GAME, d)): shutil.copytree(s, os.path.join(GAME, d))
    os.makedirs(os.path.join(CONTENT, 'maps', 'scripts'), exist_ok=True)
    for d in ('postprocess', 'soundevents'):
        s = os.path.join(TEMPLATE, 'content', d)
        if os.path.isdir(s) and not os.path.isdir(os.path.join(CONTENT, d)): shutil.copytree(s, os.path.join(CONTENT, d))


def rc_text(raw):
    return raw.decode('utf-16le', 'replace') if b'\x00' in raw[:8] else raw.decode('utf-8', 'replace')


def compile_models(out_root, copy_dirs, vmdls, log_path):
    """copies the given out/addon folders into the scratch addon and compiles each vmdl; -> {vmdl: (ok, seconds, problems)}"""
    ensure_addon()
    for rel in copy_dirs:                       # folders (replaced) or single files
        src = os.path.join(out_root, rel.replace('/', os.sep)); dst = os.path.join(CONTENT, rel.replace('/', os.sep))
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst); continue
        if not os.path.isdir(src): continue
        if os.path.isdir(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst)
    res = {}
    with open(log_path, 'wb') as lf:
        for v in vmdls:
            path = os.path.join(CONTENT_REAL, v.replace('/', os.sep))
            t = time.time()
            try:
                r = subprocess.run([RC, '-f', '-i', path], capture_output=True, timeout=900)
                txt = rc_text(r.stdout + r.stderr)
            except subprocess.TimeoutExpired:
                txt = 'TIMEOUT after 900 s'
            lf.write(('==== %s\n' % v).encode('utf-8') + txt.encode('utf-8', 'replace'))
            ok = re.search(r'\b1 compiled, 0 failed', txt) is not None
            probs = [l.strip() for l in txt.splitlines() if re.search(r'(?i)RESOURCE COMPILE (ERROR|WARNING)|error:|failed to|TIMEOUT', l)]
            probs = [x for x in probs if 'Only a single LOD group' not in x]
            res[v] = (ok, round(time.time() - t, 1), probs[:8])
    return res


def main():
    args = sys.argv[1:]
    only = None
    if '--only' in args: only = set(args[args.index('--only') + 1].split(','))
    do_download, prune, no_preview, no_compile, skip_existing = '--download' in args, '--prune' in args, '--no-preview' in args, '--no-compile' in args, '--skip-existing' in args
    cat = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))
    parts = json.load(open(os.path.join(PROJ, 'data', 'parts.json'), encoding='utf-8'))
    p = dict(cat['paths']); p['steamcmd'] = os.environ.get('STEAMCMD', p['steamcmd']); p['work'] = os.environ.get('IF_WORK', p['work'])
    out_root = os.path.join(PROJ, p.get('out', 'out/addon').replace('/', os.sep))
    for d in ('extract', 'logs', 'reports'): os.makedirs(os.path.join(p['work'], d), exist_ok=True)
    os.makedirs(os.path.join(PROJ, 'preview', 'frames'), exist_ok=True); os.makedirs(os.path.join(out_root, '_gen'), exist_ok=True)
    state_path = os.path.join(p['work'], 'state.json')
    state = json.load(open(state_path, encoding='utf-8')) if os.path.exists(state_path) else {}
    results = state.setdefault('frames', {})
    frame_parts = {x['model']: x for x in parts['parts'] if x.get('kind') == 'frame'}
    keys = [k for k in ORDER if k in cat['frames']] + [k for k in cat['frames'] if k not in ORDER]
    if only: keys = [k for k in keys if k in only]
    failed = []
    for key in keys:
        fr = cat['frames'][key]
        height = {'boss': 700}.get(fr['class']) or parts['classes'][fr['class']]['height']
        if fr['class'] in parts['classes']: height = parts['classes'][fr['class']]['height']
        log('\n== %s  (%s, %s, item %s, %s MB, %.1f GB free)' % (key, fr['title'], fr['class'], fr['item'], fr.get('size_mb'), free_gb()))
        res = {'key': key, 'item': fr['item'], 'title': fr['title'], 'author': fr['author'], 'class': fr['class'], 'height': height, 'when': time.strftime('%Y-%m-%d %H:%M')}
        report_json = os.path.join(p['work'], 'reports', key + '.json')
        preview_png = None if no_preview else os.path.join(PROJ, 'preview', 'frames', key + '.png')
        model_dir = 'models/ifr/frames/%s' % key
        try:
            if skip_existing and os.path.exists(os.path.join(out_root, model_dir.replace('/', os.sep), key + '_upper.vmdl')) and os.path.exists(report_json):
                res.update(results.get(key, {})); res['skipped'] = True; results[key] = res; log('  kept existing conversion'); continue
            mdls, extra, note, root = [], [], '', None
            if fr.get('source') == 'tripo':           # a rigged Tripo GLB (create/glbrig.py through mdl2cs2), not a Workshop item
                if not os.path.exists(fr['glb']): raise RuntimeError('GLB missing: %s' % fr['glb'])
                mdls = [fr['glb']]; note = 'Tripo AI GLB (%s)' % os.path.basename(fr['glb'])
                extra = (['--decimate', str(fr['decimate'])] if fr.get('decimate') else []) + (['--retint', str(fr['retint'])] if fr.get('retint') else []) + \
                        ['--credit', fr.get('credit', 'Tripo AI (generated)')] + (['--torso-to-upper'] if fr.get('torso_to_upper') else [])
            spec = SPECIAL.get(key) if not mdls else None
            if spec:
                root = extract(p, spec['item']) if (has_archive(item_dir(p, spec['item'])) or os.path.isdir(os.path.join(p['work'], 'extract', str(spec['item'])))) else None
                if root is None and do_download and download(p, spec['item'], state): root = extract(p, spec['item'])
                if root:
                    mdls = [os.path.join(root, m) for m in spec['mdls']]; note = spec['note']; res['source_item'] = spec['item']
            if not mdls:
                d = item_dir(p, fr['item'])
                if not has_archive(d) and not os.path.isdir(os.path.join(p['work'], 'extract', str(fr['item']))) and do_download:
                    download(p, fr['item'], state)
                root = extract(p, fr['item'])
                if root:
                    unusable = UNUSABLE.get(fr['item'], {})
                    mdl, cands = pick_mdl(root, GLOB_FIX.get(key, fr['mdl']))
                    if mdl and any(u in os.path.basename(mdl).lower() for u in unusable):
                        res['warning_source'] = unusable[[u for u in unusable if u in os.path.basename(mdl).lower()][0]]; mdl = None
                    if mdl:
                        mdls = [mdl]; res['source_item'] = fr['item']; res['candidates'] = cands[:6]
                        if len(cands) > 1: note = 'picked the tallest of %d candidates' % len(cands)
            if not mdls and key in FALLBACK:
                fb = FALLBACK[key]
                root = extract(p, fb['item']) if (has_archive(item_dir(p, fb['item'])) or os.path.isdir(os.path.join(p['work'], 'extract', str(fb['item'])))) else None
                if root:
                    mdls = [os.path.join(root, m) for m in fb['mdls']]; extra = fb.get('args', []); note = fb['note']; res['source_item'] = fb['item']; res['standin'] = True
            if not mdls:
                raise RuntimeError('no source model (item %s not downloaded%s)' % (fr['item'], '' if do_download else '; run with --download'))
            res['mdls'] = [os.path.relpath(m, os.path.join(p['work'], 'extract')).replace('\\', '/') for m in mdls]; res['note'] = note
            strip = fr.get('strip') or {}
            if strip:
                extra = list(extra) + strip_args(strip); res['strip'] = strip.get('what') or ' '.join(strip_args(strip))
                log('  strip: %s (%s)' % (res['strip'], ' '.join(strip_args(strip))))
            rc, out, secs = run_mdl2cs2(mdls, key, height, fr.get('legs'), out_root, preview_png, report_json, extra)
            tail = '\n'.join(out.strip().splitlines()[-12:])
            log('  mdl2cs2 rc %d in %.0f s\n    ' % (rc, secs) + tail.replace('\n', '\n    '))
            if rc != 0: raise RuntimeError('mdl2cs2 failed: ' + tail[-400:])
            rep = json.load(open(report_json, encoding='utf-8'))
            res['report'] = {k: rep[k] for k in ('height', 'hip_z', 'bounds', 'spheres', 'warnings', 'yaw', 'yaw_how', 'scale', 'pose') if k in rep}
            res['models'] = {g: {k: v for k, v in m.items() if k in ('vmdl', 'tris', 'bounds', 'hardpoints', 'muzzles', 'boosters', 'hardpoint_sources', 'materials', 'anims', 'anim_len', 'anim_family', 'gait')} for g, m in rep['models'].items()}
            res['materials'] = {t: {k: v for k, v in i.items() if k in ('flat', 'missing', 'selfillum', 'glass', 'additive', 'shader')} for t, i in rep['materials'].items()}
            if strip:
                gone = prune_unreferenced(out_root, key)
                if gone: log('  strip: %d material files of the stripped parts deleted (%s ...)' % (len(gone), ', '.join(sorted(gone)[:4])))
            res['textures'] = len(glob.glob(os.path.join(out_root, 'materials', 'ifr', 'frames', key, '*_color.png')))
            if not no_compile:
                vmdls = [m['vmdl'] for m in rep['models'].values()]
                cres = compile_models(out_root, [model_dir, 'materials/ifr/frames/%s' % key], vmdls, os.path.join(p['work'], 'logs', 'rc_%s.log' % key))
                res['compiled'] = {v: {'ok': ok, 'seconds': s, 'problems': pr} for v, (ok, s, pr) in cres.items()}
                for v, (ok, s, pr) in cres.items(): log('  compile %-50s %s %5.1fs %s' % (os.path.basename(v), 'OK ' if ok else 'FAIL', s, '; '.join(pr)[:200]))
                if not all(ok for ok, _, _ in cres.values()): res['error'] = 'compile failed'
            res['ok'] = 'error' not in res
        except Exception as e:
            res['error'] = str(e)[:600]; res['ok'] = False
            log('  FAILED: %s' % res['error'])
        results[key] = res
        if not res.get('ok'): failed.append(key)
        save_state(state_path, state)
        if prune: prune_item(p, fr, res, state, keys, cat)
    write_models_json(out_root, cat, results, frame_parts)
    write_models_md(cat, results, frame_parts, p)
    write_credits(cat, results)
    save_state(state_path, state)
    log('\n%d frames ok, %d failed%s' % (sum(1 for k in keys if results.get(k, {}).get('ok')), len(failed), (': ' + ', '.join(failed)) if failed else ''))
    log('free disk %.1f GB' % free_gb())
    return 1 if failed else 0


def prune_item(p, fr, res, state, keys, cat):
    """delete the SteamCMD copy (only if this tool downloaded it) and the extract, unless another frame still to come uses the item"""
    for wid in {fr['item'], res.get('source_item')} - {None}:
        later = [k for k in keys if k != fr['model'] if False]       # placeholder for clarity
        users = [k for k, f in cat['frames'].items() if f['item'] == wid or f.get('alt_item') == wid or SPECIAL.get(k, {}).get('item') == wid or FALLBACK.get(k, {}).get('item') == wid]
        pending = [k for k in users if k in keys and not state['frames'].get(k, {}).get('ok') and k != res['key']]
        if pending: continue
        if wid in cat.get('weapon_props', {}).get('items', []) or wid == 3708956431: continue   # weapon_props.py still needs the AC pack
        ex = os.path.join(p['work'], 'extract', str(wid))
        if os.path.isdir(ex): shutil.rmtree(ex, ignore_errors=True); log('  pruned extract %s' % wid)
        if wid in state.get('downloaded', []):
            d = item_dir(p, wid)
            if os.path.isdir(d): shutil.rmtree(d, ignore_errors=True); log('  pruned SteamCMD copy %s' % wid)


def frame_entry(res):
    ms = res.get('models', {})
    up = ms.get('upper') or next(iter(ms.values()), None)
    if not up: return None
    legs = ms.get('legs')
    rep = res.get('report', {})
    e = {'legs': legs['vmdl'] if legs else None, 'upper': up['vmdl'], 'height': rep.get('height', res['height']),
         'hip_z': rep.get('hip_z', legs['bounds'][1][2] if legs else 0),
         'spheres': rep.get('spheres', []), 'hardpoints': up.get('hardpoints', {}),
         'muzzles': {k: v for k, v in up.get('muzzles', {}).items() if k in ('ra', 'la')}, 'boosters': up.get('boosters', []), 'anims': {'legs': [], 'upper': []}, 'anim_len': {}}
    for g in ('legs', 'upper'):
        m = ms.get(g)
        if m and m.get('anims'):
            e['anims'][g] = m['anims']; e['anim_len'].update(m.get('anim_len', {}))
    e['skins'] = 3     # material groups 0 default, 1 scorched, 2 wrecked (mdl2cs2 --damage-skins)
    gt = (legs or {}).get('gait')
    if gt:      # weighty-gait data for the script: stride length / natural speed per cycle, foot-plant fractions, hip drop (see create/mech_anim.py)
        e['stride'] = gt['stride']
        e['steps'] = {k: sorted([v['l'], v['r']]) for k, v in gt['steps'].items() if k in ('walk', 'run', 'walk_back', 'strafe_l', 'strafe_r')}
        e['steps_side'] = gt['steps']
        e['hip_drop'] = gt['hip_drop']; e['leg_len'] = gt['leg_len']
        # hip motion the legs clips no longer carry (the pelvis bone never leaves the origin): the script moves BOTH props by it.
        # loops: 16 samples, sample i at t = i/16 * clip length; land / qb_*: one-shots, sample i at t = i/15 * length. z up, sway = model +Y.
        if gt.get('hip_curve'): e['hip_curve'] = gt['hip_curve']; e['sway_curve'] = gt['sway_curve']
        if gt.get('hip_curve'): e['hip_curve_info'] = 'hip_curve[clip] = vertical offset (units) to add to BOTH props; sway_curve[clip] = lateral (+Y) offset. Loops (walk, walk_back, strafe_l, strafe_r, run): 16 samples, sample i at t = i/16*clip length, read with a PERIODIC CATMULL-ROM (linear is off by up to ~4 u on run). One-shots (land, qb_l, qb_r): 16 samples, sample i at t = i/15*clip length. The legs clips keep the pelvis on the origin and solve the feet against this curve.'
        up_clips = e['anims'].get('upper', [])
        e['sway'] = {k: k + '_sway' for k in ('walk', 'run', 'walk_back', 'strafe_l', 'strafe_r') if k + '_sway' in up_clips}
    return e


def frame_pivot(out_root, key, res):
    """waist pivot [x, y] in the feet-origin model frame: the pelvis/hip bone, else the x,y centre of the legs (or upper) mesh bounds"""
    sys.path.insert(0, CREATE)
    import mech_anim
    try:
        sk = json.load(open(os.path.join(out_root, 'models', 'ifr', 'frames', key, key + '_skeleton.json'), encoding='utf-8'))
        if sk.get('bones_reliable') and len(sk['bones']) > 2:
            i = mech_anim.waist_bone(sk['bones'])
            if i is not None: res['waist_z'] = round(sk['bones'][i]['pos'][2], 1); return [round(sk['bones'][i]['pos'][0], 1), round(sk['bones'][i]['pos'][1], 1)]
    except Exception as ex:
        log('  pivot: skeleton unreadable (%s)' % ex)
    ms = res.get('models', {}); m = ms.get('legs')
    if not m: return [0.0, 0.0]          # hover frame: the feet-origin is already the centre of its lowest part
    lo, hi = m['bounds']
    return [round((lo[0] + hi[0]) / 2, 1), round((lo[1] + hi[1]) / 2, 1)]


def write_models_json(out_root, cat, results, frame_parts):
    path = os.path.join(out_root, '_gen', 'models.json')
    data = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    frames = {}
    for key, res in results.items():
        if not res.get('ok'): continue
        if cat['frames'].get(key, {}).get('status', 'review') != 'approved' and '--all' not in sys.argv: continue    # skink52 approves frames by hand
        e = frame_entry(res)
        if e:
            e['pivot'] = frame_pivot(out_root, key, res)
            if res.get('waist_z'): e['waist_z'] = res['waist_z']   # the waist joint's height: where 30_render.js joins the legs and the upper body
            frames[key] = e
    if '--merge' in sys.argv and '--only' in sys.argv:      # touch only the frames of this run (other tools tune the rest in place)
        only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
        old = data.get('frames', {})
        frames = {k: v for k, v in list(old.items()) + [(k, v) for k, v in frames.items() if k in only]}
    data['frames'] = frames
    data.setdefault('weapons', {}); data.setdefault('fx', {})
    json.dump(data, open(path, 'w', encoding='utf-8'), indent=1)
    log('models.json: %d frames' % len(frames))


def write_models_md(cat, results, frame_parts, p):
    lines = ['# IRONFRAME frame models', '',
             'Generated by `tools/frames.py` (do not edit; every frame\'s source and conversion result). Sources are GMod Workshop ports of',
             'commercial game assets: see [CREDITS.md](CREDITS.md) for the porters and the permission status. Positions below are in the',
             'frame\'s model frame after scaling (x forward, y left, z up, origin under the feet).', '',
             '| Key | Part | Class / height | Source item | Author | Size | Tris legs / upper (LOD0) | Textures | Compiled | Warnings | Preview |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for key, fr in cat['frames'].items():
        res = results.get(key, {})
        part = frame_parts.get(key, {})
        ms = res.get('models', {})
        tris = ' / '.join(str(ms[g]['tris'][0]) for g in ('legs', 'upper') if g in ms) if ms else '-'
        comp = '-' if 'compiled' not in res else ('yes' if all(v['ok'] for v in res['compiled'].values()) else 'NO')
        warns = []
        if res.get('error'): warns.append('FAILED: ' + res['error'][:160])
        if res.get('standin'): warns.append(res.get('note', 'stand-in'))
        elif res.get('note'): warns.append(res['note'])
        if res.get('warning_source'): warns.append(res['warning_source'])
        if res.get('strip'): warns.append('stripped: ' + res['strip'])
        warns += [w[:120] for w in res.get('report', {}).get('warnings', [])][:3]
        flat = [t for t, i in res.get('materials', {}).items() if i.get('flat')]
        if flat: warns.append('flat grey: ' + ', '.join(flat[:4]))
        src = '[%s](https://steamcommunity.com/sharedfiles/filedetails/?id=%s)' % (fr['item'], fr['item'])
        if fr.get('source') == 'tripo': src = 'Tripo AI GLB `%s`' % os.path.basename(fr.get('glb', ''))
        elif res.get('source_item') and res['source_item'] != fr['item']:
            src += ' via [%s](https://steamcommunity.com/sharedfiles/filedetails/?id=%s)' % (res['source_item'], res['source_item'])
        prev = '![%s](../preview/frames/%s.png)' % (key, key) if os.path.exists(os.path.join(PROJ, 'preview', 'frames', key + '.png')) else '-'
        lines.append('| `%s` | %s | %s / %s | %s | %s | %s MB | %s | %s | %s | %s | %s |' % (
            key, part.get('name', '-'), fr['class'], res.get('height', '-'), src, fr['author'], fr.get('size_mb', '?'), tris,
            res.get('textures', '-'), comp, '; '.join(warns).replace('|', '/') or '-', prev))
    lines += ['', '## Per-frame data (models.json)', '']
    for key, res in results.items():
        if not res.get('ok'): continue
        e = frame_entry(res)
        if not e: continue
        lines.append('### %s' % key)
        lines.append('- legs `%s`, upper `%s`; height %s, hip_z %s' % (e['legs'], e['upper'], e['height'], e['hip_z']))
        lines.append('- hit spheres (x y z r): %s' % '; '.join(' '.join(str(v) for v in s) for s in e['spheres']))
        hs = res.get('models', {}).get('upper', {}).get('hardpoint_sources', {})
        lines.append('- hardpoints: %s' % ', '.join('%s %s (%s)' % (k, v, hs.get(k, '')) for k, v in e['hardpoints'].items()))
        lines.append('- boosters: %s (%s)' % (e['boosters'], hs.get('boosters', '')))
        lods = {g: m['tris'] for g, m in res.get('models', {}).items()}
        lines.append('- LOD triangles: %s' % lods)
        lines.append('- source: %s%s' % (', '.join(res.get('mdls', [])), ('; ' + res['note']) if res.get('note') else ''))
        lines.append('')
    lines += ['## Not converted', '']
    for key, fr in cat['frames'].items():
        res = results.get(key)
        if res is None: lines.append('- `%s`: not attempted (item %s, %s MB)' % (key, fr['item'], fr.get('size_mb')))
        elif not res.get('ok'): lines.append('- `%s`: %s' % (key, res.get('error', '?')))
    lines.append('')
    open(os.path.join(PROJ, 'docs', 'MODELS.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))


DOGFIGHT_CREDITS = r'C:\source2\projects\dogfight\dogfight\project\models\CREDITS.txt'


def write_credits(cat, results):
    lines = ['# IRONFRAME asset credits', '',
             'Mech frames and the AC weapon props are **ports made by Garry\'s Mod Workshop authors of assets from commercial games**',
             '(Armored Core 4 / For Answer, Titanfall 1/2, Mobile Suit Gundam, Mass Effect 2/3, F.E.A.R. 3). The game studios own the',
             'originals; the porters own their conversion work. Each line records the permission status from `data/frames.json`',
             '(`asked` / `granted` / `none`): items marked `none` are for private-server use only and are kept in the build only while',
             '`IF_ALL_FRAMES=1` (DESIGN.md §10). The Workshop description of the addon lists every port and its author.', '',
             '| Used as | Item | Title | Author | Link | Licence note |', '|---|---|---|---|---|---|']
    seen = set()
    rows = []
    tripo = sorted(k for k, f in cat['frames'].items() if f.get('source') == 'tripo')
    for key, fr in cat['frames'].items():
        if fr.get('source') == 'tripo': continue
        for wid, title, author, note in [(fr['item'], fr['title'], fr['author'], 'port of %s assets' % game_of(fr['title']))] + \
                ([(fr['alt_item'], 'Armored Core Model Pack Reupload', 'Nakkitsunami', 'port of Armored Core 4 / For Answer assets')] if fr.get('alt_item') else []):
            if wid in seen: continue
            seen.add(wid)
            used = [k for k, f in cat['frames'].items() if f['item'] == wid] + [k for k, r in results.items() if r.get('source_item') == wid and cat['frames'][k]['item'] != wid]
            perm = fr.get('permission', 'none') if wid == fr['item'] else 'none'
            rows.append('| frames: %s | %s | %s | %s | [workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=%s) | %s; permission: %s |' % (
                ', '.join(sorted(set(used))) or '-', wid, title, author, wid, note, perm))
    state_path = os.path.join(p_work_of(cat), 'state.json')
    weapons = (json.load(open(state_path, encoding='utf-8')).get('weapons', {}) if os.path.exists(state_path) else {})
    by_item = {}
    for k, r in weapons.items():
        if r.get('ok') and r.get('item'): by_item.setdefault(r['item'], []).append(k)
    titles = {268093486: 'Titanfall - Titan Weapon Model Pack (GMod, Part 1)', 268097317: 'Titanfall - Titan Weapon Model Pack (GMod, Part 2)',
              268095616: 'Titanfall - Titan Weapon Model Pack (GMod, Part 3)'}
    for wid in cat.get('weapon_props', {}).get('items', []):
        if wid in seen: continue
        seen.add(wid)
        rows.append('| weapon props: %s | %s | %s | Workshop porter (see item page) | [workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=%s) | port of Titanfall assets; permission: none |' % (
            ', '.join(sorted(by_item.get(wid, []))) or 'none yet (tools/weapon_props.py --titan)', wid, titles.get(wid, '(Workshop weapon pack)'), wid))
    if by_item.get(3708956431):
        rows = [r.replace('| frames: ', '| frames: ', 1) for r in rows]
        rows.append('| weapon props: %s | 3708956431 | Armored Core Model Pack Reupload | Nakkitsunami | [workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3708956431) | port of Armored Core 4 / For Answer assets; permission: none |' % ', '.join(sorted(by_item[3708956431])))
    procedural = sorted(k for k, r in weapons.items() if r.get('ok') and not r.get('item'))
    lines += rows
    if tripo:
        lines += ['', 'AI-generated frames (ours): %s: generated with Tripo AI from skink52\'s prompts (docs/TRIPO_PROMPTS.md), rigged GLBs converted by '
                  'create/glbrig.py + create/mdl2cs2.py; credit "Tripo AI (generated, skink52)", CC BY-NC 4.0 like our other assets.' % ', '.join(tripo)]
    if procedural: lines += ['', 'Procedural weapon props (ours, CC BY-NC 4.0): ' + ', '.join(procedural) + '.']
    lines += ['', '## Creative Commons models (Dogfight, reused)', '']
    if os.path.exists(DOGFIGHT_CREDITS):
        lines += ['The missile model `models/ifr/fx/missile` is the Dogfight port of "Game Ready R-73" by SydneeFlop (jokesforboats), Sketchfab,',
                  'CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), modified (markings removed, repainted, converted for Counter-Strike 2):',
                  'https://sketchfab.com/3d-models/game-ready-r-73-00e9be4be4d447a7963eae1fa4ab5cb9', '']
    else:
        lines += ['(Dogfight\'s CC BY models were not available on this PC; the missile is procedural.)', '']
    lines += ['## Our own assets', '',
              'Procedural weapon props, effect models, sounds and the arena are made by this project\'s tools and are CC BY-NC 4.0',
              '(LICENSE-CC-BY-NC-4.0.txt); the code is PolyForm Noncommercial (LICENSE).', '']
    open(os.path.join(PROJ, 'docs', 'CREDITS.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))


def p_work_of(cat):
    return os.environ.get('IF_WORK', cat['paths']['work'])


def game_of(title):
    t = title.lower()
    for k, g in (('armored core 4', 'Armored Core 4 / For Answer'), ('armored core 3', 'Armored Core 3'), ('armored core', 'Armored Core'),
                 ('titanfall 2', 'Titanfall 2'), ('titanfall', 'Titanfall'), ('gundam', 'Mobile Suit Gundam'), ('mass effect 3', 'Mass Effect 3'),
                 ('mass effect 2', 'Mass Effect 2'), ('fear 3', 'F.E.A.R. 3')):
        if k in t: return g
    return 'game'


if __name__ == '__main__':
    sys.exit(main())
