"""Does the map load, and does the game addon hold, everything the script can draw?  Exit 1 on any gap.

CS2 shows an ERROR model (or nothing) for a model the script SetModels to that the map never loaded, and nothing for a particle
pool entity the map lacks. A model only shows when (1) the map has a prop of it (the cache room: tools/arenas/common.py cache(),
tools/patch_cache.py), and (2) its compiled *_c and every material / texture under it are in the game addon, built from the
content that is there now. This tool lists what the script can use and checks both:

  the script can use   models.json frames (legs, upper), weapons, fx; auras.json parts' states; objectives.json models; the null
                       model; every 'models/...vmdl' literal in src/; the particle pools of fx_particles.json and auras.json
                       (entities ifr_pfx_<kind>_NN, 3 digits for pools of 100+, as 40_fx.js names them)
  PRECACHE             a wanted model with no prop in the vmap (prop_static does not count: it is baked into the world)
  CACHE NAME           an objective marker model whose prop is not named ifr_cache_<key> (45_features.js looks it up by that name)
  POOL                 a pool entity missing from the vmap, or with another effect; the prop template ifr_tpl_prop / _src missing
  COMPILED             a model / particle / material / texture *_c missing from the game addon (stock ones are looked up in
                       CS2's pak01_dir.vpk)
  STALE                the addon's content file differs from the build's (out/addon: not deployed), or a *_c is older than the
                       content it was compiled from

usage: python -I tools/cache_check.py <vmap> [--addon NAME] [--map-only] [--sync] [--compile [--groups frames,weapons,fx,aura,obj,particles]]
                                      [--also GLOB ...] [--json FILE] [--vpk]
       python -I tools/cache_check.py --addon NAME --sync-only
  <vmap>       the map to check: the addon's content map, or a patched copy in out/ (then give --addon)
  --addon      the CS2 addon whose content / game folders are checked (default: from the vmap's path or file name)
  --map-only   only the vmap side (PRECACHE, CACHE NAME, POOL): for a map that is not deployed yet
  --sync       first copy every file of out/addon/{materials,models,particles} (and out/<arena>/addon/... for that arena's addon,
               which wins) that is missing or different in the addon's content. Unchanged files are left alone, so their dates
               keep meaning "last changed"; nothing is deleted.
  --compile    then compile every wanted model and pool particle in the addon WITHOUT -f: resourcecompiler recompiles what is out
               of date (its own input check) and skips the rest; a clean run marks the skipped ones fresh (touches the *_c).
               Never copy *_c files from another addon: the compiler takes them for stale and CS2's tools recompile them at
               map load (minutes of silence).  --also GLOB: more content files to compile the same way (relative to the content).
  --vpk        also require maps/<map>.vpk in the game addon to be newer than the vmap
"""
import argparse, glob, json, os, re, shutil, struct, subprocess, sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PROJ)); CREATE = os.path.join(REPO, 'create')
CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
CONTENT_ROOT = os.path.join(CS2, 'content', 'csgo_addons'); GAME_ROOT = os.path.join(CS2, 'game', 'csgo_addons')
GEN = os.path.join(PROJ, 'out', 'addon', '_gen')
PREFIX = 'ifr'; NULL_MODEL = 'models/ifr/null.vmdl'
SYNC_DIRS = ('materials', 'models', 'particles')
GROUPS = ('frames', 'weapons', 'fx', 'aura', 'obj', 'particles')


# ---------------------------------------------------------------- what the script can use
def _load(gen, name):
    """a _gen list; waits out a writer (models.json.lock, a half-written file) for up to a minute"""
    p = os.path.join(gen, name)
    if not os.path.exists(p): return {}
    for attempt in range(60):
        lock = p + '.lock'
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 900 and attempt < 59: time.sleep(1.0); continue
        try:
            with open(p, encoding='utf-8') as f: return json.load(f)
        except ValueError:
            if attempt == 59: raise
            time.sleep(1.0)
    return {}


def wanted_models(gen=GEN):
    """{model path: (group, what)} for every model the script may SetModel to, in cache-room order"""
    out = {NULL_MODEL: ('fx', 'null (pool idle model)')}
    j = _load(gen, 'models.json')
    for k, fr in (j.get('frames') or {}).items():
        for part in ('legs', 'upper'):
            if fr.get(part): out.setdefault(fr[part], ('frames', 'frame %s %s' % (k, part)))
    for group in ('weapons', 'fx'):
        for k, v in (j.get(group) or {}).items():
            if isinstance(v, str): out.setdefault(v, (group, '%s %s' % (group, k)))
    for k, fr in (_load(gen, 'auras.json').get('frames') or {}).items():
        for pid, part in (fr.get('parts') or {}).items():
            for st, m in (part.get('states') or {}).items(): out.setdefault(m, ('aura', 'aura %s/%s/%s' % (k, pid, st)))
    for k, m in (_load(gen, 'objectives.json').get('models') or {}).items(): out.setdefault(m, ('obj', 'objective %s' % k))
    return out


def wanted_pools(gen=GEN):
    """{kind: (count, effect)}: the particle pools 40_fx.js looks up (fx_particles.json#pools) + the aura flare pools"""
    out = {}
    for kind, p in (_load(gen, 'fx_particles.json').get('pools') or {}).items():
        if isinstance(p, dict) and p.get('effect'): out[kind] = (int(p.get('count', 4)), p['effect'])
    for kind, p in (_load(gen, 'auras.json').get('pools') or {}).items():
        out.setdefault(kind, (int(p.get('count', 4)), p['effect']))
    return out


def pool_names(kind, count):
    return ['%s_pfx_%s_%0*d' % (PREFIX, kind, 3 if count >= 100 else 2, i) for i in range(count)]


def script_literals(src=os.path.join(PROJ, 'src')):
    """model paths written out in the script source, path prefixes it builds names from, and the models.json#fx keys it asks for"""
    full, prefixes, fxkeys = {}, {}, {}
    for f in sorted(glob.glob(os.path.join(src, '*', '*.js'))):
        txt = open(f, encoding='utf-8', errors='replace').read(); rel = os.path.relpath(f, PROJ).replace(os.sep, '/')
        for m in re.finditer(r'''['"`]((?:models|particles)/[\w/.\-]*)['"`]''', txt):
            s = m.group(1)
            if s.endswith(('.vmdl', '.vpcf')): full.setdefault(s, rel)
            elif s.endswith('/'): prefixes.setdefault(s, rel)
        for m in re.finditer(r'FX_MODELS\.([A-Za-z_]\w*)', txt): fxkeys.setdefault(m.group(1), rel)
    return full, prefixes, fxkeys


# ---------------------------------------------------------------- the map
def read_vmap(path):
    """-> models {model: [(classname, targetname)]} (prop_static left out), particles {targetname: effect}, names {targetname: classname}"""
    sys.path.insert(0, CREATE)
    import dmx
    d = dmx.DMX.load(path); models, effects, names, pnames = {}, set(), {}, {}

    def walk(n):
        for c in n.get('children') or []:
            if c.type == 'CMapEntity':
                ep = c.get('entity_properties'); cls = ep.get('classname') or ''; nm = ep.get('targetname') or ''
                if nm: names[nm] = cls
                m = ep.get('model')
                if m and cls != 'prop_static': models.setdefault(m.replace('\\', '/'), []).append((cls, nm))
                e = ep.get('effect_name')
                if e:
                    effects.add(e.replace('\\', '/'))
                    if nm: pnames[nm] = e.replace('\\', '/')
            walk(c)
    walk(d.root.get('world'))
    return models, effects, names, pnames


# ---------------------------------------------------------------- compiled resources
def rerl(path):
    """the external references of a compiled resource (the RERL block): materials of a model, textures of a material, ..."""
    buf = open(path, 'rb').read()
    off = struct.unpack_from('<I', buf, 8)[0] + 8; n = struct.unpack_from('<I', buf, 12)[0]
    for i in range(n):
        p = off + i * 12
        if buf[p:p + 4] != b'RERL': continue
        o = p + 4 + struct.unpack_from('<I', buf, p + 4)[0]
        eo, cnt = struct.unpack_from('<II', buf, o); base = o + eo; res = []
        for k in range(cnt):
            q = base + k * 16 + 8; q += struct.unpack_from('<q', buf, q)[0]
            res.append(buf[q:buf.index(b'\0', q)].decode('utf-8', 'replace').replace('\\', '/'))
        return res
    return []


_stock = None
def stock_has(res):
    """is <res>_c in CS2's own packs (game/csgo, game/core pak01_dir.vpk)? None when the packs can't be read"""
    global _stock
    if _stock is None:
        _stock = set()
        try:
            sys.path.insert(0, CREATE)
            import vpkdir
            for sub in ('csgo', 'core'):
                p = os.path.join(CS2, 'game', sub, 'pak01_dir.vpk')
                if os.path.exists(p): _stock |= set(vpkdir.read_dir(p))
        except Exception as e:
            print('note: stock packs not readable (%s): stock resources are not verified' % e); _stock = set()
    if not _stock: return None
    return (res + '_c') in _stock


def same_file(a, b):
    try:
        if os.path.getsize(a) != os.path.getsize(b): return False
        with open(a, 'rb') as fa, open(b, 'rb') as fb:
            while True:
                x = fa.read(1 << 20)
                if x != fb.read(1 << 20): return False
                if not x: return True
    except OSError:
        return False


class Addon:
    def __init__(self, name):
        self.name = name; self.content = os.path.join(CONTENT_ROOT, name); self.game = os.path.join(GAME_ROOT, name)
        arena = name.rsplit('_', 1)[-1]
        self.srcs = [os.path.join(PROJ, 'out', 'addon')] + ([os.path.join(PROJ, 'out', arena, 'addon')] if os.path.isdir(os.path.join(PROJ, 'out', arena, 'addon')) else [])

    def c(self, rel): return os.path.join(self.content, rel.replace('/', os.sep))
    def g(self, rel): return os.path.join(self.game, rel.replace('/', os.sep) + '_c')

    def src(self, rel):
        """the build's copy of a content file (the arena's own out folder wins over the shared one), or None"""
        for s in reversed(self.srcs):
            p = os.path.join(s, rel.replace('/', os.sep))
            if os.path.isfile(p): return p
        return None

    def sync(self):
        """copy the build's materials / models / particles that are missing or different in the content; -> (copied, same)"""
        eff = {}
        for s in self.srcs:
            for top in SYNC_DIRS:
                for dp, dn, fn in os.walk(os.path.join(s, top)):
                    for f in fn:
                        if f.endswith(('.lock', '.tmp', '.fxtmp')): continue
                        p = os.path.join(dp, f); eff[os.path.relpath(p, s)] = p
        copied = same = 0
        for rel, p in sorted(eff.items()):
            dst = os.path.join(self.content, rel)
            if os.path.isfile(dst) and same_file(p, dst): same += 1; continue
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(p, dst); copied += 1
        return copied, same


def vmdl_inputs(text):
    """the mesh / animation files a .vmdl names (content-relative)"""
    return sorted({m.group(1).replace('\\', '/') for m in re.finditer(r'(?:filename|source_filename)\s*=\s*"([^"]+\.(?:smd|dmx|fbx|obj|vmesh|vanim))"', text, re.I)})


def vmat_inputs(text):
    return sorted({m.group(1).replace('\\', '/') for m in re.finditer(r'"((?:materials|models)/[^"]+\.(?:png|tga|jpg|jpeg|psd|exr))"', text, re.I)})


def check_resource(ad, res, why, gaps, seen, depth=0):
    """one wanted resource and everything under it: compiled there, content deployed, compiled not older than its content"""
    if res in seen: return
    seen.add(res)
    g = ad.g(res); c = ad.c(res)
    ours = os.path.isfile(c) or os.path.isfile(g) or ad.src(res) is not None
    if not os.path.isfile(g):
        if ours or depth == 0: gaps.append(('COMPILED', res, 'no %s_c in the game addon (%s)' % (os.path.basename(res), why)))
        else:
            st = stock_has(res)
            if st is False: gaps.append(('COMPILED', res, 'not in the game addon and not in CS2\'s packs (%s)' % why))
        return
    inputs = []
    if os.path.isfile(c):
        inputs.append(res)
        if res.endswith(('.vmdl', '.vmat')):
            try: txt = open(c, encoding='utf-8', errors='replace').read()
            except OSError: txt = ''
            inputs += [f for f in (vmdl_inputs(txt) if res.endswith('.vmdl') else vmat_inputs(txt)) if os.path.isfile(ad.c(f))]
    elif ad.src(res): gaps.append(('STALE', res, 'the build has this file but the addon content does not: deploy / --sync (%s)' % why))
    gt = os.path.getmtime(g)
    for f in inputs:
        s = ad.src(f)
        if s and not same_file(s, ad.c(f)): gaps.append(('STALE', res, 'content %s differs from the build (%s): deploy / --sync' % (f, os.path.relpath(s, PROJ).replace(os.sep, '/')))); break
        if os.path.getmtime(ad.c(f)) > gt + 2:
            gaps.append(('STALE', res, 'compiled %s is older than its content %s (%s): --compile' % (time.strftime('%d %b %H:%M', time.localtime(gt)), f, time.strftime('%d %b %H:%M', time.localtime(os.path.getmtime(ad.c(f))))))); break
    try: refs = rerl(g)
    except Exception as e:
        gaps.append(('COMPILED', res, 'unreadable compiled file: %s' % e)); return
    for r in refs: check_resource(ad, r, '%s <- %s' % (r.rsplit('/', 1)[-1], why), gaps, seen, depth + 1)


def compiled_outputs(ad, res, acc, seen):
    """the *_c files of a resource and of everything of ours under it"""
    if res in seen: return
    seen.add(res); g = ad.g(res)
    if not os.path.isfile(g): return
    acc.append(g)
    try: refs = rerl(g)
    except Exception: refs = []
    for r in refs: compiled_outputs(ad, r, acc, seen)


def rc_busy():
    return 'resourcecompiler.exe' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq resourcecompiler.exe'], capture_output=True, text=True).stdout.lower()


def compile_addon(ad, resources, log_dir, tag):
    """non-forced resourcecompiler over the content files (batches of 24); a clean run marks every output fresh. -> ok"""
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    import rcompile
    paths = [(r, ad.c(r)) for r in resources if os.path.isfile(ad.c(r))]
    t0 = time.time()
    while rc_busy():
        if time.time() - t0 > 900: print('another resourcecompiler has been running for 15 min: not compiling'); return False
        time.sleep(3)
    os.makedirs(log_dir, exist_ok=True)
    tot = dict(compiled=0, failed=0, skipped=0); ok = True; t_start = time.time(); nb = (len(paths) + 23) // 24
    for i in range(0, len(paths), 24):
        chunk = paths[i:i + 24]; log = os.path.join(log_dir, 'rc_%s_%s.%02d.log' % (ad.name, tag, i // 24))
        try: r = rcompile.compile_assets([p for _, p in chunk], force=False, log=log, timeout=3600)
        except Exception as e:
            print('  batch %d / %d: %s' % (i // 24 + 1, nb, e), flush=True); ok = False; continue
        s = r.get('summary') or {}
        for k in tot: tot[k] += int(s.get(k) or 0)
        ok = ok and bool(r.get('ok'))
        print('  compile batch %d / %d (%s ...): %s compiled, %s failed, %s skipped, %.0f s' % (i // 24 + 1, nb, chunk[0][0].rsplit('/', 1)[-1], s.get('compiled', '?'), s.get('failed', '?'),
                                                                                           s.get('skipped', '?'), r.get('seconds') or 0), flush=True)
        for k in ('compile_errors', 'errors'):
            for x in (r.get(k) or [])[:5]: print('    %s: %s' % (k, x))
        if r.get('ok'):          # everything in this batch is now what the compiler calls up to date: date the outputs so
            acc, seen = [], set()
            for res, _ in chunk: compiled_outputs(ad, res, acc, seen)
            now = time.time()
            for g in acc:
                try: os.utime(g, (now, now))
                except OSError: pass
    print('compile %s: %d files, %d compiled, %d failed, %d skipped in %.0f s (logs %s)' % (ad.name, len(paths), tot['compiled'], tot['failed'], tot['skipped'], time.time() - t_start,
                                                                                         os.path.join(log_dir, 'rc_%s_%s.*.log' % (ad.name, tag))), flush=True)
    return ok and tot['failed'] == 0


def addon_of(vmap, given):
    if given: return given
    real = os.path.realpath(vmap).replace('\\', '/')
    m = re.search(r'/csgo_addons/([^/]+)/maps/', real)
    if m: return m.group(1)
    stem = os.path.splitext(os.path.basename(vmap))[0]
    if os.path.isdir(os.path.join(CONTENT_ROOT, stem)): return stem
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description='script models / particles against the map precache and the game addon')
    ap.add_argument('vmap', nargs='?'); ap.add_argument('--addon'); ap.add_argument('--gen', default=GEN)
    ap.add_argument('--map-only', action='store_true'); ap.add_argument('--sync', action='store_true'); ap.add_argument('--sync-only', action='store_true')
    ap.add_argument('--compile', action='store_true'); ap.add_argument('--groups', default=','.join(GROUPS)); ap.add_argument('--also', action='append', default=[])
    ap.add_argument('--json'); ap.add_argument('--vpk', action='store_true'); ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)
    name = addon_of(a.vmap, a.addon) if a.vmap else a.addon
    ad = Addon(name) if name else None
    if a.sync or a.sync_only:
        if not ad: sys.exit('--sync needs --addon (or a vmap inside the addon)')
        copied, same = ad.sync()
        print('sync %s: %d files copied into the content, %d already the same (%s)' % (name, copied, same, ' + '.join(os.path.relpath(s, PROJ).replace(os.sep, '/') for s in ad.srcs)))
        if a.sync_only: return 0
    if not a.vmap: sys.exit(__doc__)
    models = wanted_models(a.gen); pools = wanted_pools(a.gen)
    lit, prefixes, fxkeys = script_literals()
    gaps, warns = [], []
    for m, f in lit.items():
        if m.endswith('.vmdl') and m not in models: models[m] = ('fx', 'written out in %s' % f)
    fx = _load(a.gen, 'models.json').get('fx') or {}
    for k, f in sorted(fxkeys.items()):
        if k not in fx: warns.append('the script asks for models.json#fx.%s (%s) but tools/fx.py does not make it: its fallback is drawn' % (k, f))
    for p, f in sorted(prefixes.items()):
        n = sum(1 for m in models if m.startswith(p))
        if not n: warns.append('%s builds model names under %s but no wanted model is there' % (f, p))

    # ---- the map
    vm, veff, vnames, vpfx = read_vmap(a.vmap)
    for m, (grp, why) in models.items():
        if m not in vm: gaps.append(('PRECACHE', m, 'no prop of it in the map (%s)' % why))
        elif grp == 'obj':
            want = '%s_cache_%s' % (PREFIX, os.path.splitext(os.path.basename(m))[0].lower())
            if want not in vnames: gaps.append(('CACHE NAME', m, 'its prop is not named %s (the script then draws the stock fallback)' % want))
    for tn in ('%s_tpl_prop' % PREFIX, '%s_tpl_prop_src' % PREFIX):
        if tn not in vnames: gaps.append(('POOL', tn, 'the prop pool template entity is missing'))
    for kind, (count, eff) in pools.items():
        miss = [n for n in pool_names(kind, count) if n not in vpfx]; other = [n for n in pool_names(kind, count) if n in vpfx and vpfx[n] != eff]
        if miss: gaps.append(('POOL', kind, '%d of %d pool entities missing (%s ...) for %s' % (len(miss), count, miss[0], eff)))
        if other: gaps.append(('POOL', kind, '%d pool entities have another effect (%s: %s, wanted %s)' % (len(other), other[0], vpfx[other[0]], eff)))

    # ---- the addon
    did_compile = None
    if not a.map_only:
        if not ad or not os.path.isdir(ad.game): sys.exit('no game addon for this map: give --addon NAME (or --map-only)')
        groups = set(a.groups.split(','))
        if a.compile:
            res = [m for m, (grp, why) in models.items() if grp in groups]
            if 'particles' in groups: res += sorted({eff for count, eff in pools.values() if os.path.isfile(ad.c(eff))})
            for pat in a.also: res += sorted(os.path.relpath(p, ad.content).replace(os.sep, '/') for p in glob.glob(os.path.join(ad.content, pat.replace('/', os.sep))))
            did_compile = compile_addon(ad, list(dict.fromkeys(res)), os.path.join(PROJ, 'logs'), 'assets')
            if not did_compile: gaps.append(('COMPILED', name, 'the asset compile reported failures (logs/rc_%s_assets.*.log)' % name))
        seen = set()
        for m, (grp, why) in models.items(): check_resource(ad, m, why, gaps, seen)
        for e in sorted(veff | {eff for count, eff in pools.values()}):
            if os.path.isfile(ad.c(e)) or os.path.isfile(ad.g(e)) or ad.src(e): check_resource(ad, e, 'particle', gaps, seen)
            elif stock_has(e) is False: gaps.append(('COMPILED', e, 'particle not in the addon and not in CS2\'s packs'))
        for k, e in sorted((_load(a.gen, 'fx_particles.json').get('stock') or {}).items()):
            if isinstance(e, str) and stock_has(e) is False: warns.append('fx_particles.json#stock.%s = %s is not in CS2\'s packs' % (k, e))
        if a.vpk:
            vpk = os.path.join(ad.game, 'maps', os.path.splitext(os.path.basename(a.vmap))[0] + '.vpk')
            if not os.path.isfile(vpk): gaps.append(('VPK', vpk, 'the map is not built'))
            elif os.path.getmtime(vpk) < os.path.getmtime(a.vmap): gaps.append(('VPK', vpk, 'built %s, before the vmap was written (%s): rebuild the map' % (
                time.strftime('%d %b %H:%M', time.localtime(os.path.getmtime(vpk))), time.strftime('%d %b %H:%M', time.localtime(os.path.getmtime(a.vmap))))))

    # ---- report
    by = {}
    for kind, what, why in gaps: by.setdefault(kind, []).append((what, why))
    ngrp = {}
    for m, (grp, why) in models.items(): ngrp[grp] = ngrp.get(grp, 0) + 1
    print('cache_check %s%s' % (a.vmap, (' (addon %s)' % name) if name else ''))
    print('  the script can use %d models (%s), %d particle pools (%d entities); the map loads %d models, %d particle effects' % (
        len(models), ', '.join('%s %d' % (g, n) for g, n in ngrp.items()), len(pools), sum(c for c, e in pools.values()), len(vm), len(veff)))
    for w in warns: print('  note: ' + w)
    for kind in ('PRECACHE', 'CACHE NAME', 'POOL', 'COMPILED', 'STALE', 'VPK'):
        rows = by.get(kind) or []
        if not rows: continue
        print('  %s: %d' % (kind, len(rows)))
        for what, why in rows[:(8 if a.quiet else 400)]: print('    %-58s %s' % (what, why))
        if a.quiet and len(rows) > 8: print('    ... %d more' % (len(rows) - 8))
    if a.json:
        json.dump(dict(vmap=a.vmap, addon=name, models=len(models), pools=len(pools), gaps=[dict(kind=k, what=w, why=y) for k, w, y in gaps], notes=warns, compiled=did_compile),
                  open(a.json, 'w', encoding='utf-8'), indent=1)
    if gaps:
        print('GAPS: %d (%s)%s' % (len(gaps), ', '.join('%s %d' % (k, len(v)) for k, v in by.items()), ' [map side only]' if a.map_only else '')); return 1
    print('OK: no gaps%s' % (' [map side only: the addon was not checked]' if a.map_only else '')); return 0


if __name__ == '__main__':
    sys.exit(main())
