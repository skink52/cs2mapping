"""Remaster step 14: rebuild the weakest props and stage them in out/step14/addon (never the addon).

  wreck_tank        procedural rebuild (tools/p_wreck.py tank2) + LODs from tools/lod_decimate.py (lightmapped pair)
  ext/petrol_can    LOD0 cut 28,884 -> 3,000 triangles (tools/decimate_lod0.py, Blender collapse) + LOD1-4
  ext/helmet_stahl_ext   27,536 -> 6,000 + LOD1-4
  ext/field_telephone    18,577 -> 4,000 + LOD1-4
  ext/stretcher_ext the modern camouflage canvas (an anachronism on a 1917 stretcher) re-made as stained khaki duck; mesh unchanged

Every model keeps its path, origin, scale, footprint and collision hull, so the map needs no change. Writes out/step14/build.json
(triangle counts, bounds before / after) and out/step14/deploy_files.txt.

usage: python tools/build_step14.py [wreck_tank,petrol_can,...] [--no-list]
"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'out', 'step14', 'addon')
os.environ['TW_OUT'] = OUT                 # before build_prop is imported: it reads its output root at import
sys.path.insert(0, HERE)
CONTENT = os.environ.get('TW_CONTENT', r'C:\source1\links\content_addons\mg_trenchwarfare')
import numpy as np                          # noqa: E402

DECIMATE = {'petrol_can': 3000, 'helmet_stahl_ext': 6000, 'field_telephone': 4000}
LM = set(json.load(open(os.path.join(PROJ, 'out', 'step14', 'lightmapped.json'))))   # lod_decimate.lightmapped(final chain map)


def smd_bounds(path):
    import lod_decimate as L
    _, _, A = L.read_smd(path)
    P = A[:, :, :3].reshape(-1, 3); w = np.stack([-P[:, 1], P[:, 0], P[:, 2]], 1)      # SMD (y, -x, z) -> world
    return len(A), w.min(0).round(2).tolist(), w.max(0).round(2).tolist()


def lod0_of(root, mdir, name):
    p = os.path.join(root, 'models', mdir, name + '_lod0.smd')
    return p if os.path.exists(p) else os.path.join(root, 'models', mdir, name + '.smd')


def build_wreck_tank(rep):
    import build_prop, p_wreck, lod_decimate
    spec = p_wreck.specs()['wreck_tank']
    d = os.path.join(OUT, 'models', 'tw', 'wreck_tank')
    if os.path.isdir(d): shutil.rmtree(d)
    build_prop.build('wreck_tank', spec, preview=False)
    lod_decimate.process(OUT, OUT, 'tw/wreck_tank', set(), LM)
    rep['wreck_tank'] = dict(source='procedural, tools/p_wreck.py tank2()', before=smd_bounds(lod0_of(CONTENT, 'tw/wreck_tank', 'wreck_tank')),
                             after=smd_bounds(lod0_of(OUT, 'tw/wreck_tank', 'wreck_tank')))


def build_decimated(name, target, rep):
    import lod_decimate
    mdir = 'tw/ext/' + name
    src = os.path.join(CONTENT, 'models', 'tw', 'ext', name)
    dst = os.path.join(OUT, 'models', 'tw', 'ext', name)
    if os.path.isdir(dst): shutil.rmtree(dst)
    os.makedirs(dst)
    shutil.copy(os.path.join(src, name + '.vmdl'), dst)                 # lod_decimate rewrites its LOD list; the hull is unchanged
    r = subprocess.run([sys.executable, os.path.join(HERE, 'decimate_lod0.py'), os.path.join(src, name + '.smd'), os.path.join(dst, name + '.smd'), str(target)])
    if r.returncode: raise SystemExit('decimate_lod0 failed for ' + name)
    lod_decimate.process(OUT, OUT, mdir, set(), LM)
    rep['ext/' + name] = dict(source='LOD0 decimated (Blender collapse) from the deployed converted model', before=smd_bounds(os.path.join(src, name + '.smd')),
                              after=smd_bounds(os.path.join(dst, name + '.smd')))


def build_stretcher(rep):
    """camouflage pixels (high local colour variance) -> khaki duck canvas with weave, sun-fade, mud and old blood stains"""
    from PIL import Image
    from scipy import ndimage
    from noise import fbm
    rel = 'materials/models/tw/ext/stretcher_ext/stretcher_ext_c0.png'
    im = np.asarray(Image.open(os.path.join(CONTENT, *rel.split('/'))).convert('RGB'), np.float32) / 255.0
    H, W = im.shape[:2]
    lum = im @ np.array([0.3, 0.59, 0.11], np.float32)
    var = sum(ndimage.uniform_filter(im[..., k] ** 2, 21) - ndimage.uniform_filter(im[..., k], 21) ** 2 for k in range(3))
    camo = ndimage.binary_closing(var > 0.004, iterations=6)
    camo = ndimage.binary_opening(camo, iterations=2)
    camo &= ndimage.uniform_filter(lum, 31) > 0.22                                     # the black handle grips stay as they are
    green = (im[..., 1] > im[..., 0] * 1.08) & (im[..., 1] > im[..., 2] * 1.15)             # stray green flecks next to the mask
    camo = camo | (ndimage.binary_dilation(camo, iterations=6) & green)
    soft = np.clip(ndimage.gaussian_filter(camo.astype(np.float32), 1.2), 0, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    weave = 0.5 + 0.5 * np.cos(xx * np.pi / 1.5) * np.cos(yy * np.pi / 1.5)
    n1 = fbm(xx.ravel() * 0.012, yy.ravel() * 0.012, np.zeros(H * W), 4, seed=141).reshape(H, W)
    n2 = fbm(xx.ravel() * 0.05, yy.ravel() * 0.05, np.ones(H * W), 3, seed=142).reshape(H, W)
    base = np.array([0.60, 0.55, 0.43], np.float32)
    col = base * (0.88 + 0.10 * weave[..., None]) * (0.90 + 0.14 * n1[..., None]) * (0.96 + 0.06 * n2[..., None])
    detail = (lum - ndimage.gaussian_filter(lum, 2.0))[..., None]        # keep the source's fine folds, not its blotches
    col = col + 0.35 * detail
    mud = np.clip((n1 - 0.25) * 2.5, 0, 1)[..., None] * 0.55
    col = col * (1 - mud) + np.array([0.30, 0.24, 0.17]) * mud
    blood = np.clip((fbm(xx.ravel() * 0.02, yy.ravel() * 0.02, np.full(H * W, 2.0), 4, seed=143).reshape(H, W) - 0.42) * 3.0, 0, 1)[..., None] * 0.6
    col = col * (1 - blood) + np.array([0.26, 0.11, 0.08]) * blood
    out = im * (1 - soft[..., None]) + np.clip(col, 0, 1) * soft[..., None]
    dst = os.path.join(OUT, *rel.split('/'))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(dst)
    rep['ext/stretcher_ext'] = dict(source='texture re-made (mesh unchanged); converted model "Army Stretcher" by 4mecharmi, CC BY 4.0',
                                    camo_pixels=float(camo.mean()))


def build_tw_de_a(rep):
    """the T player body from the re-welded GLB (tools/soldiers.py weld_mesh); only the body dmx is staged: the vmdl (skeleton,
    hitboxes, attachments, arms) and the materials stay the deployed ones"""
    import tempfile
    tpl = os.environ.get('TW_SOLDIER_TEMPLATE', r'C:\source1\links\content_addons\mg_mario_party\models\player\custom_player\kuristaja\octodad\cs2')
    glb = os.environ.get('TW_SOLDIER_GLBS', r'C:\source1\cs2port\assets\tw')
    tmp = tempfile.mkdtemp(prefix='tw14_soldier_')
    arg = 'tw_de_a=%s@%s' % (os.path.join(glb, '3d modell soldat wehrmacht.glb'), os.path.join(glb, 'wwi+british+soldier+3d+model.glb'))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'soldiers.py'), tpl, tmp, arg], capture_output=True, text=True)
    print(r.stdout.strip()); print(r.stderr.strip()[-2000:])
    if r.returncode: raise SystemExit('soldiers.py failed')
    rel = 'models/tw/players/tw_de_a/tw_de_a_body.dmx'
    dst = os.path.join(OUT, *rel.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(os.path.join(tmp, *rel.split('/')), dst)
    shutil.rmtree(tmp, ignore_errors=True)
    rep['players/tw_de_a'] = dict(source='tools/soldiers.py with weld_mesh (re-welded Tripo GLB before the donor weight transfer)',
                                  log=[l for l in r.stdout.splitlines() if 'tw_de_a' in l])


def write_list(rep):
    skip = ('materials/models/tw/stock/',)       # build_prop's stock copies: the addon's own copies stay (as in step 13)
    rows = []
    for root, _, fs in os.walk(OUT):
        for f in sorted(fs):
            r = os.path.relpath(os.path.join(root, f), OUT).replace('\\', '/')
            if r.startswith(skip): continue
            rows.append(r)
    rows.sort()
    head = """# remaster step 14 (14 Nov 2026, docs/ASSETS.md "Prop rebuilds (step 14)"): the weakest props rebuilt, same model paths, origins,
# scale, footprints and collision hulls (no map change). Files to copy into content\\csgo_addons\\mg_trenchwarfare\\ (addon-relative);
# sources relative to projects/trenchwarfare-cs2. Built by tools/build_step14.py; the T player body by tools/soldiers.py (re-welded GLB).
# - wreck_tank: procedural rebuild (tools/p_wreck.py tank2), 5,406 -> %(wt)s triangles, LODs by lod_decimate (lightmapped pair).
# - ext/petrol_can 28,884 -> 3,000; ext/helmet_stahl_ext 27,536 -> 6,000; ext/field_telephone 18,577 -> 4,000 (LOD0 cut in Blender,
#   new LOD1-4 by lod_decimate). Their materials and hulls are unchanged (not re-sent).
# - ext/stretcher_ext: colour texture only (camouflage -> stained khaki canvas).
# - players/tw_de_a: tw_de_a_body.dmx rebuilt from the re-welded Tripo GLB (0 open edges, was 154); vmdl, skeleton and scale unchanged.
# Then compile (force): resourcecompiler -f -i models/tw/wreck_tank/wreck_tank.vmdl, models/tw/ext/petrol_can/petrol_can.vmdl,
# models/tw/ext/helmet_stahl_ext/helmet_stahl_ext.vmdl, models/tw/ext/field_telephone/field_telephone.vmdl,
# models/tw/ext/stretcher_ext/stretcher_ext.vmdl (the png changed; the vmdl did not, so force it) and
# models/tw/players/tw_de_a/tw_de_a.vmdl (the dmx changed, the vmdl did not: force it). Assets before the map.
# Left in the addon, unused after this (harmless): models/tw/wreck_tank/wreck_tank_lod1.smd (the old generated LOD1).
# Test-compiled in the scratch addon tw_weapontest (14 Nov 2026): each of the six vmdls 1 compiled, 0 failed, no warnings.
""" % dict(wt=format(rep.get('wreck_tank', {}).get('after', [0])[0], ','))
    lines = [head.rstrip('\n')] + ['%s   <- out/step14/addon/%s' % (r, r) for r in rows]
    p = os.path.join(PROJ, 'out', 'step14', 'deploy_files.txt')
    open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('deploy list: %s (%d files)' % (p, len(rows)))


def main(argv):
    only = set(argv[0].split(',')) if argv and not argv[0].startswith('--') else None
    rp = os.path.join(PROJ, 'out', 'step14', 'build.json')
    rep = json.load(open(rp)) if os.path.exists(rp) else {}
    want = lambda k: only is None or k in only
    if want('wreck_tank'): build_wreck_tank(rep)
    for n, t in DECIMATE.items():
        if want(n): build_decimated(n, t, rep)
    if want('stretcher_ext'): build_stretcher(rep)
    if want('tw_de_a'): build_tw_de_a(rep)
    json.dump(rep, open(rp, 'w'), indent=1)
    for k, v in rep.items(): print('%-22s %s' % (k, {a: b for a, b in v.items() if a != 'source'}))
    if '--no-list' not in argv: write_list(rep)


if __name__ == '__main__':
    main(sys.argv[1:])
