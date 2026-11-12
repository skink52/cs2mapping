"""Restages the lost out/ folder (27 Oct handover) from the user's current vmap and the addon, so test/mock.mjs and the radar /
HUD / map tools have their inputs again. Reads the vmap and the addon only; writes only under projects/trenchwarfare-cs2/out/.

usage (from anywhere):  python tools/restage_out.py [--vmap V] [--addon A] [--game G] [--out DIR]
  defaults: --addon C:/source1/links/content_addons/mg_trenchwarfare, --vmap <addon>/maps/mg_trenchwarfare.vmap,
            --game C:/source1/links/game_addons/mg_trenchwarfare, --out <project>/out
Exits 1 if a cross-check fails (a constant that the script, the tools and the shipped files must agree on, a model the script sets
that the addon lacks, a propeller hub that differs between planes of one type).

What it writes, and where each comes from:
  out/digest.json        Full tools/mapdigest.py digest of the vmap (every entity: class, name, origin, angles, logic keys, I/O).
                         Read by tools/check_contract.py. Coordinates rounded to 0.1 (mapdigest convention).
  out/entities.json      Mock input (test/mock.mjs): every named entity plus the info_player_* spawns, as name/cls/origin/angles,
                         the same shape tools/dump_entities.py wrote. Read from the vmap at full precision (repo tools/vmapedit.py).
  out/addon/panorama/    Copy of the addon's content panorama/ (HUD layout xml, css, the tw/ pictures, the radar png/vtex).
                         The mock checks every HUD id against the xml and every class against the css.
  out/addon/models/...   Copies of every .vmdl the script names (CONFIG.UNIFORMS: the 4 soldier models), so the mock's
                         "SetModel to a model the addon lacks" check sees them.
  out/prop_hubs.json     Propeller hub per aircraft model (make_map.py / patch_vmap.py input; split_props.py wrote it). Recovered
                         from the vmap: hub = rotate(-yaw) * (tw_prop_<tg> origin - tw_plane_<tg> origin), the inverse of
                         patch_vmap.hub_at(). The original came from the unsplit SMD (3 decimals); this one agrees across
                         the 5 planes of each type to the tolerance printed.
  out/radar_region.json  {x0, y0, span} for render_top.py: make_radar.py's X0 / Y0 / SCALE * 1024, checked against the shipped
                         overview (game resource/overviews/mg_trenchwarfare.txt) and the script's CONFIG.RADAR.
  out/target_map.json    {ext, size} as render_top.py writes it (EXT, 768), checked against CONFIG.TARGET_EXT.
  out/hud.json           {tm, steps} as tw_hud.py writes it (TM, STEPS), checked against CONFIG.TARGET_STEPS.
  out/restage_manifest.json  What was written, from which vmap (size, mtime, CRC32), and what could not be restaged.

What cannot be restaged (and why):
  radar_clean.png        The unlabelled radar render make_radar.py saves for render_top.py. The addon only has the labelled radar
                         (labels, legend, scale bar drawn over it), which cannot be undone. Rerunning make_radar.py on the vmap
                         (into out/addon, out/game) makes a new one, but that is a regeneration of the radar (remaster step 8),
                         not a restage. Without it render_top.py uses its own terrain render for the mortar sight.
  user_edits.json, gen_twN.vmap   make_map.py's EditKeeper state: needs the exact generated baseline, which no longer exists
                         (docs/research/TW_STATE.md section 7). Map changes are delta patches instead.
  ext_src/, ext_full/    Aircraft sources: weather_ext.py's pre-weathering converter output and split_props.py's unsplit plane SMDs.
                         The addon holds only the weathered, split results. Caution: both tools copy the addon's files in as
                         "source" when these folders are missing, so a rerun would weather twice / split an already split body.
                         Rebuild from the GLBs (C:/source2/projects/trenchwarfare) with glb2cs2_multi.py first.
  props.json             build_all_props.py's record of our procedural props; needs a prop rebuild. placer.py falls back to the
                         addon SMDs and its STOCK table without it.
  overlaps.json          make_map.py's placer audit; placer.py <vmap> writes a new one when wanted.
  the rest of out/addon  The full build (models, materials, sounds). Tools that write the addon take its path as an argument.
"""
import argparse, json, math, os, re, shutil, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO_TOOLS = os.path.normpath(os.path.join(PROJ, '..', '..', 'tools'))
# the project's tools/ has its own dmx.py; the repo readers need the repo's, so take this folder off the path
sys.path[:] = [REPO_TOOLS] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V        # noqa: E402
import mapdigest            # noqa: E402

SCRIPT = os.path.join(PROJ, 'src', 'mg_trenchwarfare.js')
problems = []


def bad(msg):
    problems.append(msg); print('  FAIL ' + msg)


def const(path, name):
    """a module-level numeric constant from a tool, read as text (the tools run their whole job on import)"""
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^([A-Za-z_][\w, ]*?)\s*=\s*([-0-9.,\s]+?)\s*(#.*)?$', line.rstrip('\n'))
        if not m: continue
        names = [n.strip() for n in m.group(1).split(',')]
        if name in names:
            vals = [float(v) for v in m.group(2).split(',') if v.strip()]
            if len(vals) == len(names): return vals[names.index(name)]
    raise SystemExit('restage: cannot find the constant %s in %s' % (name, path))


def crc32(path):
    c = 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): c = zlib.crc32(b, c)
    return '%08x' % c


def write_json(path, data, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f: json.dump(data, f, indent=indent)


def main():
    ap = argparse.ArgumentParser(description='Restage projects/trenchwarfare-cs2/out/ from the vmap and addon (read-only on both)')
    ap.add_argument('--addon', default='C:/source1/links/content_addons/mg_trenchwarfare')
    ap.add_argument('--vmap')
    ap.add_argument('--game', default='C:/source1/links/game_addons/mg_trenchwarfare')
    ap.add_argument('--out', default=os.path.join(PROJ, 'out'))
    a = ap.parse_args()
    vmap = a.vmap or os.path.join(a.addon, 'maps', 'mg_trenchwarfare.vmap')
    out = os.path.abspath(a.out)
    for p in (vmap, a.addon, SCRIPT):
        if not os.path.exists(p): raise SystemExit('restage: missing ' + p)
    for p in (a.addon, a.game):      # never write into the addon (the links are junctions: compare real paths)
        rp = os.path.normcase(os.path.realpath(p))
        if os.path.normcase(os.path.realpath(out)).startswith(rp): raise SystemExit('restage: --out is inside ' + p)
    js = open(SCRIPT, encoding='utf-8').read()
    written = []
    t0 = time.time()

    # 1. digest (every entity) and the mock's entity list
    print('reading %s (%d bytes)' % (vmap, os.path.getsize(vmap)))
    d = mapdigest.digest(vmap)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'digest.json'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(mapdigest.dumps(d))
    written.append('digest.json')
    print('  digest.json: %d entities' % len(d['entities']))
    m = V.Map(vmap)
    ents = []
    for e in m.entities():
        cls, nm = m.cls(e), m.name(e)
        if nm or cls.startswith('info_player'):
            ang = m.g(e, b'angles') or [0, 0, 0]
            ents.append(dict(name=nm, cls=cls, origin=[float(v) for v in m.origin(e)], angles=[float(v) for v in ang], model=m.P(e, 'model') or ''))
    write_json(os.path.join(out, 'entities.json'), [{k: v for k, v in x.items() if k != 'model'} for x in ents], indent=0)
    written.append('entities.json')
    print('  entities.json: %d entities (named + spawns)' % len(ents))

    # 2. propeller hubs (inverse of patch_vmap.hub_at)
    by = {x['name']: x for x in ents}
    hubs = {}
    for x in ents:
        if x['cls'] != 'prop_dynamic' or not re.fullmatch(r'tw_plane_(t|ct)_\d+', x['name']): continue
        pr = by.get('tw_prop_' + x['name'][len('tw_plane_'):])
        if not pr: bad('no tw_prop_ for ' + x['name']); continue
        pl = x['model'].replace('\\', '/').split('/')[-2]
        yaw = math.radians(x['angles'][1]); dx, dy = pr['origin'][0] - x['origin'][0], pr['origin'][1] - x['origin'][1]
        hubs.setdefault(pl, []).append((dx * math.cos(yaw) + dy * math.sin(yaw), -dx * math.sin(yaw) + dy * math.cos(yaw), pr['origin'][2] - x['origin'][2]))
    hub_out = {}
    for pl, hs in sorted(hubs.items()):
        mean = [sum(h[k] for h in hs) / len(hs) for k in range(3)]
        spread = max(math.dist(h, mean) for h in hs)
        hub_out[pl] = [round(v, 3) for v in mean]
        print('  prop hub %s: %s from %d planes, spread %.3f u' % (pl, hub_out[pl], len(hs), spread))
        if spread > 0.5: bad('propeller hubs of %s differ by %.2f u between planes (a plane or propeller was moved)' % (pl, spread))
    write_json(os.path.join(out, 'prop_hubs.json'), hub_out, indent=1)
    written.append('prop_hubs.json')

    # 3. constants the script, tools and shipped files share
    mr = os.path.join(HERE, 'make_radar.py')
    x0, y0, scale = const(mr, 'X0'), const(mr, 'Y0'), const(mr, 'SCALE')
    region = dict(x0=x0, y0=y0, span=scale * 1024)
    ov = os.path.join(a.game, 'resource', 'overviews', 'mg_trenchwarfare.txt')
    if os.path.exists(ov):
        t = open(ov, encoding='utf-8', errors='replace').read()
        got = {k: float(re.search(r'"%s"\s+"([-0-9.]+)"' % k, t).group(1)) for k in ('pos_x', 'pos_y', 'scale')}
        if (got['pos_x'], got['pos_y'], got['scale']) != (x0, y0, scale): bad('overview %s != make_radar.py %s' % (got, (x0, y0, scale)))
        else: print('  overview matches make_radar.py: pos %g %g scale %.2f' % (x0, y0, scale))
    else:
        print('  (no shipped overview at %s; not cross-checked)' % ov)
    mrad = re.search(r'RADAR:\s*\{\s*x0:\s*([-0-9.]+),\s*y0:\s*([-0-9.]+),\s*span:\s*([-0-9.]+)', js)
    if not mrad or any(abs(float(mrad.group(i + 1)) - v) > 0.05 for i, v in enumerate((x0, y0, scale * 1024))):
        bad('script CONFIG.RADAR %s != make_radar.py region %s' % (mrad and mrad.groups(), region))
    write_json(os.path.join(out, 'radar_region.json'), region)
    written.append('radar_region.json')

    ext = const(os.path.join(HERE, 'render_top.py'), 'EXT')
    mext = re.search(r'TARGET_EXT:\s*([0-9.]+)', js)
    if not mext or float(mext.group(1)) != ext: bad('script TARGET_EXT %s != render_top.py EXT %g' % (mext and mext.group(1), ext))
    write_json(os.path.join(out, 'target_map.json'), dict(ext=ext, size=768))
    written.append('target_map.json')

    th = os.path.join(HERE, 'tw_hud.py')
    tm, steps = int(const(th, 'TM')), int(const(th, 'STEPS'))
    mst = re.search(r'TARGET_STEPS:\s*(\d+)', js)
    if not mst or int(mst.group(1)) != steps: bad('script TARGET_STEPS %s != tw_hud.py STEPS %d' % (mst and mst.group(1), steps))
    write_json(os.path.join(out, 'hud.json'), dict(tm=tm, steps=steps))
    written.append('hud.json')
    print('  radar_region.json %s, target_map.json ext %g, hud.json tm %d steps %d' % (region, ext, tm, steps))

    # 4. addon files the mock reads: panorama (HUD xml/css/pictures) and the models the script sets
    src_pan, dst_pan = os.path.join(a.addon, 'panorama'), os.path.join(out, 'addon', 'panorama')
    if os.path.isdir(dst_pan): shutil.rmtree(dst_pan)          # only ever under out/ (checked above)
    shutil.copytree(src_pan, dst_pan)
    n = sum(len(f) for _, _, f in os.walk(dst_pan))
    written.append('addon/panorama/ (%d files)' % n)
    print('  addon/panorama: %d files' % n)
    for rel in sorted(set(re.findall(r'"(models/[^"]+\.vmdl)"', js))):
        s = os.path.join(a.addon, rel)
        if not os.path.exists(s): bad('the script sets %s, which the addon lacks' % rel); continue
        dst = os.path.join(out, 'addon', rel); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(s, dst)
        written.append('addon/' + rel)
    print('  addon/models: %d vmdl the script names' % sum(1 for w in written if w.startswith('addon/models')))

    st = os.stat(vmap)
    write_json(os.path.join(out, 'restage_manifest.json'), dict(
        tool='tools/restage_out.py', at=time.strftime('%Y-%m-%d %H:%M:%S'), vmap=os.path.basename(vmap), vmap_bytes=st.st_size,
        vmap_mtime=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)), vmap_crc32=crc32(vmap), written=written,
        not_restaged=['radar_clean.png', 'user_edits.json', 'gen_twN.vmap', 'ext_src/', 'ext_full/', 'props.json', 'overlaps.json',
                      'the full out/addon build'], problems=problems), indent=1)
    print('restaged %d outputs into %s in %.1f s' % (len(written) + 1, out, time.time() - t0))
    if problems:
        print('%d cross-check failure(s)' % len(problems)); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
