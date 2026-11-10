"""IRONFRAME effect models (out/addon/models/ifr/...), recorded in out/addon/_gen/models.json#fx. All are props a script moves
(model_archetype "", prop_dynamic), forward = +x, built with create/fx_models.py + geo/modelio:
  null         models/ifr/null.vmdl            one 0.01-unit triangle: the prop pool's idle model and the point_template source prop
  placeholder  models/ifr/fx/placeholder.vmdl  grey box mech 288 u tall (torso + two legs + head), used when a frame's model is missing
  tracer       warm rifle tracer streak (110 u, head at the origin)      tracer_heavy  autocannon streak (160 u, thicker)
  beam         cyan laser bar, 100 u along +x (legacy: the objective column fallback)     beam_red      the red one
  beam_c_<L> / beam_r_<L>   the beam ladder (cyan / red): 16 fixed lengths L = 64 .. 11585 u in x1.41 steps, 0..L along +x. CS2 props only
               scale uniformly, so the script picks the length nearest the shot and scales by 0.84-1.19: the width stays constant
               whatever the range (30_render.js beamPick). Each is a thin self-lit core (r 2.6, near white) inside six additive
               shells (r 3.9-13, the soft glow), thicker at the muzzle, tapered to a point at both ends. --beams-only builds these.
  bubble       translucent sphere r 150 for the pulse-shield bubble (the script scales effects by radius / 150)
  ring         lock marker: ring + ticks facing +x                       landing       predicted-landing ground ring (lies flat)
  missile      Dogfight's CC BY R-73 (models copied from C:/source2 when present, else a procedural finned missile), nose at +x
  iff          IFF diamond marker 60 u (white emissive, tinted by SetColor)   drone  emissive disc 40 u   mine  red-lit puck 50 u
  crate        supply crate 96 x 96 x 80 (pixel-art hazard-stripe panels), feet at z 0; --crate-only builds just this one
  shield       translucent sphere r 100 (the script scales it to the bubble radius)
usage: python -I tools/fx.py [--no-compile] [--crate-only | --beams-only]
Every write of out/addon/_gen/models.json takes out/addon/_gen/models.json.lock first (other tools write the file too).
"""
import json, math, os, shutil, sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.join(os.path.dirname(os.path.dirname(PROJ)), 'create')
sys.path.insert(0, HERE); sys.path.insert(0, CREATE); sys.path.insert(0, os.path.join(CREATE, 'playermodels'))
os.environ.setdefault('CS2_MODEL_PREFIX', 'ifr')
import geo, modelio, fx_models                               # noqa: E402
import frames as FR                                          # noqa: E402

OUT = os.path.join(PROJ, 'out', 'addon')
REL_M, REL_T = 'models/ifr/fx', 'materials/ifr/fx'
DOGFIGHT = r'C:\source2\projects\dogfight\dogfight\addon\content\dogfight'


def flat_vmat(name, rgb, rough=0.6, metal=0.3, translucent=None, backfaces=False, comment='IRONFRAME effect material (generated)'):
    """csgo_complex with a flat colour; translucent = constant alpha 0..1"""
    d = os.path.join(OUT, REL_T); os.makedirs(d, exist_ok=True)
    Image.new('RGB', (4, 4), tuple(rgb)).save(os.path.join(d, name + '_color.png'))
    Image.new('L', (4, 4), int(rough * 255)).save(os.path.join(d, name + '_rough.png'))
    lines = ['// ' + comment, 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1', '\tTextureColor "%s/%s_color.png"' % (REL_T, name),
             '\tg_flModelTintAmount "1.000"', '\tTextureNormal "materials/default/default_normal.tga"',
             '\tTextureRoughness "%s/%s_rough.png"' % (REL_T, name), '\tg_flMetalness "%.3f"' % metal]
    if translucent is not None:
        Image.new('L', (4, 4), int(translucent * 255)).save(os.path.join(d, name + '_trans.png'))
        lines += ['\tF_TRANSLUCENT 1', '\tTextureTranslucency "%s/%s_trans.png"' % (REL_T, name)]
    if backfaces: lines.append('\tF_RENDER_BACKFACES 1')
    lines.append('}')
    open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return '%s/%s.vmat' % (REL_T, name)


def write_model(rel_dir, name, mesh, vmat, uv=None, hull=False, vmdl_path=None):
    d = os.path.join(OUT, rel_dir); os.makedirs(d, exist_ok=True)
    if uv is None: uv = np.zeros((len(mesh.V), 2))
    modelio.write_smd(os.path.join(d, name + '.smd'), mesh, uv, name + '.vmat')
    hulls = []
    if hull:
        lo, hi = mesh.V.min(0), mesh.V.max(0)
        modelio.write_hull_smd(os.path.join(d, name + '_hull.smd'), [np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])])
        hulls = [name + '_hull']
    txt = modelio.vmdl_text(name, rel_dir, [name], [(name + '.vmat', vmat)], hulls, surface='metal', archetype='', entity='prop_dynamic', single_lod=True)
    vp = vmdl_path or '%s/%s.vmdl' % (rel_dir, name)
    open(os.path.join(OUT, vp.replace('/', os.sep)), 'w', newline='\n').write(txt)
    return vp


def box(sx, sy, sz, c):
    return geo.rbox(sx, sy, sz, r=1.5, seg=1, mat='m', center=c)


def merge(ms):
    return fx_models.merge(ms)


def tube(p0, p1, r0, r1, sides=8):
    return geo.tube([p0, p1], [r0, r1], sides=sides, mat='m')


def sphere(r, n=24):
    th = np.linspace(0, math.pi, n // 2 + 1)
    prof = [(max(0.01, r * math.sin(t)), -r * math.cos(t)) for t in th]
    return geo.lathe(prof, sides=n, mat='m')


def missile():
    """Dogfight's R-73 copied with its FBX meshes (the FBX names its materials materials/jets/msl_r73_*, so those keep their path)"""
    src_m = os.path.join(DOGFIGHT, 'models', 'jets'); src_t = os.path.join(DOGFIGHT, 'materials', 'jets')
    if os.path.exists(os.path.join(src_m, 'msl_r73.fbx')) and os.path.exists(os.path.join(src_t, 'msl_r73_body.vmat')):
        d = os.path.join(OUT, 'models', 'ifr', 'fx', 'missile'); os.makedirs(d, exist_ok=True)
        for f in ('msl_r73.fbx', 'msl_r73_phys.fbx'): shutil.copy2(os.path.join(src_m, f), os.path.join(d, f))
        td = os.path.join(OUT, 'materials', 'jets'); os.makedirs(td, exist_ok=True)
        for f in os.listdir(src_t):
            if f.startswith('msl_r73'): shutil.copy2(os.path.join(src_t, f), os.path.join(td, f))
        vm = open(os.path.join(src_m, 'msl_r73.vmdl')).read().replace('models/jets/', 'models/ifr/fx/missile/')
        vm = vm.replace('// Dogfight:', '// IRONFRAME missile = Dogfight\'s R-73 (CC BY 4.0, see docs/CREDITS.md). Dogfight:')
        open(os.path.join(d, 'missile.vmdl'), 'w', newline='\n').write(vm)
        for f in ('msl_r73_body.vmat', 'msl_r73_dome.vmat'):          # paint tint for the team colour
            p = os.path.join(td, f); t = open(p).read()
            if 'g_flModelTintAmount' not in t: t = t.replace('\tF_SPECULAR 1', '\tF_SPECULAR 1\n\tg_flModelTintAmount "1.000"', 1)
            open(p, 'w', newline='\n').write(t)
        return 'models/ifr/fx/missile/missile.vmdl', 'dogfight R-73 (CC BY 4.0)'
    prof = [(0.01, -40), (3.5, -36), (4.0, -10), (4.0, 20), (2.5, 34), (0.01, 40)]
    body = geo.lathe(prof, sides=14, mat='m')
    body.V = np.stack([body.V[:, 2], body.V[:, 1], -body.V[:, 0]], 1); body.N = np.stack([body.N[:, 2], body.N[:, 1], -body.N[:, 0]], 1)
    fins = []
    for k in range(4):
        f = geo.rbox(12, 0.6, 7, r=0.2, mat='m'); R = geo.rot('x', 90.0 * k)
        f.V = (f.V + np.array([-32, 0, 6.5])) @ R.T; f.N = f.N @ R.T; fins.append(f)
    return write_model(REL_M + '/missile', 'missile', merge([body] + fins), flat_vmat('missile', (200, 200, 205), 0.45, 0.6), hull=True), 'procedural'


def crate_tex(name):
    """64x64 pixel-art supply crate face: olive steel panel, hazard-stripe border, rivets, white cross"""
    d = os.path.join(OUT, REL_T); os.makedirs(d, exist_ok=True)
    im = Image.new('RGB', (64, 64), (86, 98, 62)); px = im.load()
    for y in range(64):
        for x in range(64):
            edge = min(x, y, 63 - x, 63 - y)
            if edge < 7:
                px[x, y] = (240, 190, 30) if ((x + y) // 6) % 2 == 0 else (28, 28, 26)
            elif edge < 9: px[x, y] = (40, 46, 30)
            elif (x + y) % 16 == 0 or (x - y) % 16 == 0: px[x, y] = (76, 88, 54)
            elif (x * 7 + y * 13) % 11 == 0: px[x, y] = (96, 108, 70)
    for cx, cy in ((12, 12), (51, 12), (12, 51), (51, 51)):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1): px[cx + dx, cy + dy] = (170, 172, 160) if dx or dy else (230, 230, 220)
    for i in range(24, 40):
        for t in range(-2, 3): px[i, 32 + t] = (235, 235, 225); px[32 + t, i] = (235, 235, 225)
    im.save(os.path.join(d, name + '_color.png'))
    Image.new('L', (4, 4), 170).save(os.path.join(d, name + '_rough.png'))
    T = chr(9)
    lines = ['// IRONFRAME supply crate (generated)', 'Layer0', '{', T + 'shader "csgo_complex.vfx"', T + 'F_SPECULAR 1', T + 'TextureColor "%s/%s_color.png"' % (REL_T, name),
             T + 'g_flModelTintAmount "1.000"', T + 'TextureNormal "materials/default/default_normal.tga"', T + 'TextureRoughness "%s/%s_rough.png"' % (REL_T, name), T + 'g_flMetalness "0.200"', '}']
    open(os.path.join(d, name + '.vmat'), 'w', newline=chr(10)).write(chr(10).join(lines) + chr(10))
    return '%s/%s.vmat' % (REL_T, name)


def crate_model():
    """chunky 96 x 96 x 80 crate, feet at z 0, box-projected UVs (one 64 px tile per face)"""
    m = geo.rbox(96, 96, 80, r=4, seg=1, mat='m', center=(0, 0, 40))
    uv = np.zeros((len(m.V), 2))
    for i, (v, n) in enumerate(zip(m.V, m.N)):
        a = int(np.argmax(np.abs(n)))
        u, w = [(v[1], v[2]), (v[0], v[2]), (v[0], v[1])][a]
        uv[i] = ((u + 48) / 96.0, 1.0 - (w + (0 if a < 2 else 48)) / (80.0 if a < 2 else 96.0))
    return write_model(REL_M + '/crate', 'crate', m, crate_tex('crate'), uv=uv, hull=True)


# ---------------------------------------------------------------- models.json under a lock (several tools and agents write it)
MPATH = os.path.join(OUT, '_gen', 'models.json')


def models_json_update(fn, wait=300):
    """load models.json, fn(data) changes it in place, save; holds models.json.lock (made exclusively; one older than 15 min is stale)"""
    os.makedirs(os.path.dirname(MPATH), exist_ok=True)
    lock = MPATH + '.lock'; t0 = time.time()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ('fx.py pid %d at %s' % (os.getpid(), time.strftime('%H:%M:%S'))).encode()); os.close(fd); break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > 900: os.remove(lock); continue
            except OSError: continue
            if time.time() - t0 > wait: raise SystemExit('models.json.lock held for over %d s' % wait)
            time.sleep(1.0)
    try:
        data = json.load(open(MPATH, encoding='utf-8')) if os.path.exists(MPATH) else {}
        fn(data)
        tmp = MPATH + '.fxtmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=1)
        os.replace(tmp, MPATH)
        return data
    finally:
        try: os.remove(lock)
        except OSError: pass


# ---------------------------------------------------------------- the beam ladder
BEAM_LENGTHS = [int(round(64 * 2 ** (k / 2.0))) for k in range(16)]            # 64, 91, 128 ... 8192, 11585
BEAM_CORE_R, BEAM_GLOW_R = 2.6, 13.0
BEAM_SHELLS = ((0.30, 0.50), (0.42, 0.34), (0.56, 0.22), (0.70, 0.14), (0.85, 0.09), (1.00, 0.05))   # (radius / BEAM_GLOW_R, additive brightness), inside out
BEAM_COLS = 8                                                                    # brightness columns in the glow texture (a power of two; one per shell)
BEAM_COLORS = {'c': dict(name='cyan', core=(215, 250, 255), glow=(40, 185, 255)), 'r': dict(name='red', core=(255, 228, 205), glow=(255, 58, 28))}


def beam_profile(L, kind):
    """[(x, radius factor)] along the beam: a quick swell out of the muzzle, a slow taper down the range, a point at the hit"""
    tin = min(18.0 if kind == 'core' else 30.0, 0.22 * L); tout = min(90.0 if kind == 'core' else 130.0, 0.32 * L)
    far = 0.72 if kind == 'core' else 0.6
    pts = [(0.0, 0.0), (tin * 0.35, 0.62), (tin * 0.7, 0.93), (tin, 1.0)]
    n = max(1, min(6, int((L - tin - tout) / 160.0)))
    for i in range(1, n + 1): pts.append((tin + (L - tin - tout) * i / n, 1.0 + (far - 1.0) * i / n))
    pts += [(L - tout * 0.55, far * 0.62), (L - tout * 0.2, far * 0.26), (L, 0.0)]
    return pts


def beam_surface(prof, radius, sides, mat, u, L, phase=0.0):
    """surface of revolution about +x -> [(P 3x3, UV 3x2, mat)], outward winding; u picks the brightness column, v runs down the beam"""
    th = np.linspace(0, 2 * math.pi, sides + 1) + phase
    ring = lambda x, f: np.stack([np.full(sides + 1, x), np.cos(th) * radius * f, np.sin(th) * radius * f], 1)
    R = [ring(x, f) for x, f in prof]; tris = []
    for i in range(len(prof) - 1):
        v0, v1 = prof[i][0] / L, prof[i + 1][0] / L
        for k in range(sides):
            a, b, c, d = R[i][k], R[i + 1][k], R[i + 1][k + 1], R[i][k + 1]
            for P, V in (((a, c, b), (v0, v1, v1)), ((a, d, c), (v0, v0, v1))):
                P = np.array(P)
                if np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) < 1e-6: continue          # the pointed ends
                tris.append((P, np.array([(u, v) for v in V]), mat))
    return tris


def beam_tris(L):
    """one beam of length L: the core (material 'core') + the glow shells (material 'glow')"""
    tris = beam_surface(beam_profile(L, 'core'), BEAM_CORE_R, 6, 'core', 0.5, L)
    for j, (rf, b) in enumerate(BEAM_SHELLS):
        tris += beam_surface(beam_profile(L, 'glow'), BEAM_GLOW_R * rf, 10, 'glow', (j + 0.5) / BEAM_COLS, L, phase=j * 0.31)
    return tris


def beam_glow_vmat(name, rgb):
    """additive unlit glow (the aura recipe: csgo_unlitgeneric, F_BLEND_MODE 4): a brightness ramp, one 4 px column per shell"""
    d = os.path.join(OUT, REL_T); os.makedirs(d, exist_ok=True)
    im = Image.new('RGB', (4 * BEAM_COLS, 4))
    for j, (rf, b) in enumerate(BEAM_SHELLS):
        im.paste(tuple(int(min(255, c * b)) for c in rgb), (4 * j, 0, 4 * j + 4, 4))
    im.save(os.path.join(d, name + '_color.png'))
    T = '\t'
    lines = ['// IRONFRAME beam glow (tools/fx.py, generated): additive, one brightness column per shell', 'Layer0', '{', T + 'shader "csgo_unlitgeneric.vfx"', T + 'F_BLEND_MODE 4',
             T + 'F_RENDER_BACKFACES 1', T + 'TextureColor "%s/%s_color.png"' % (REL_T, name), T + 'g_vColorTint "[1.600000 1.600000 1.600000 0.000000]"', T + 'g_flModelTintAmount "1.000"', '}']
    open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return '%s/%s.vmat' % (REL_T, name)


def write_tris_model(rel_dir, name, tris, matpaths):
    """multi-material model from [(P, UV, mat)] (SMD turned like modelio.write_smd: (y, -x, z))"""
    d = os.path.join(OUT, rel_dir); os.makedirs(d, exist_ok=True)
    L = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.3f %.3f %.3f %.4f %.4f %.4f %.5f %.5f"
    for P, UV, mat in tris:
        n = np.cross(P[1] - P[0], P[2] - P[0]); n = n / max(1e-9, np.linalg.norm(n))
        L.append(mat + '.vmat')
        for (x, y, z), (u, v) in zip(P, UV): L.append(fmt % (y, -x, z, n[1], -n[0], n[2], u, 1 - v))
    L.append("end")
    open(os.path.join(d, name + '.smd'), 'w', newline='\n').write('\n'.join(L) + '\n')
    used = sorted({t[2] for t in tris})
    txt = modelio.vmdl_text(name, rel_dir, [name], [(u + '.vmat', matpaths[u]) for u in used], [], surface='default', archetype='', entity='prop_dynamic', single_lod=True)
    vp = '%s/%s.vmdl' % (rel_dir, name)
    open(os.path.join(OUT, vp.replace('/', os.sep)), 'w', newline='\n').write(txt)
    return vp


def beam_models():
    """the ladder -> {fx key: vmdl}; keys beam_c_<L> / beam_r_<L> (the script reads the length from the key)"""
    made = {}
    for c, col in BEAM_COLORS.items():
        mats = {'core': fx_models.emissive(OUT, REL_T, 'fx_beam_%s_core' % c, col['core'], 40.0, 'IRONFRAME beam core, %s (tools/fx.py, generated): self-lit' % col['name']),
                'glow': beam_glow_vmat('fx_beam_%s_glow' % c, col['glow'])}
        for L in BEAM_LENGTHS:
            name = 'beam_%s_%05d' % (c, L)
            made[name] = write_tris_model(REL_M + '/beams', name, beam_tris(float(L)), mats)
    return made


def bubble_model():
    """pulse-shield bubble: the translucent shield sphere at r 150 (30_render.js scales effects by radius / 150)"""
    return write_model(REL_M + '/bubble', 'bubble', sphere(150.0), flat_vmat('shield', (90, 200, 255), 0.2, 0.0, translucent=0.3, backfaces=True))


def compile_batch(vmdls, extra_files, log_name):
    """copies the vmdls' folders + extra files into the scratch addon (FR.CONTENT) and compiles the vmdls in batched resourcecompiler
    runs (materials and textures compile with them) -> {vmdl: ok}. Waits while another resourcecompiler runs (one compile at a time)."""
    import subprocess
    sys.path.insert(0, os.path.join(os.path.dirname(CREATE), 'tools'))
    import rcompile
    FR.ensure_addon()
    for rel in sorted({os.path.dirname(v) for v in vmdls}):
        src = os.path.join(OUT, rel.replace('/', os.sep)); dst = os.path.join(FR.CONTENT, rel.replace('/', os.sep))
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if os.path.isfile(os.path.join(src, f)): shutil.copyfile(os.path.join(src, f), os.path.join(dst, f))
    for rel in extra_files:
        dst = os.path.join(FR.CONTENT, rel.replace('/', os.sep)); os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(OUT, rel.replace('/', os.sep)), dst)
    t0 = time.time()
    while 'resourcecompiler.exe' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq resourcecompiler.exe'], capture_output=True, text=True).stdout.lower():
        if time.time() - t0 > 900: raise SystemExit('another resourcecompiler has been running for 15 min: not compiling')
        time.sleep(3)
    work = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work']
    log = os.path.join(work, 'logs', log_name); os.makedirs(os.path.dirname(log), exist_ok=True)
    t_start = time.time()
    for i in range(0, len(vmdls), 24):          # the command line has a length limit
        r = rcompile.compile_assets([os.path.join(FR.CONTENT_REAL, v.replace('/', os.sep)) for v in vmdls[i:i + 24]], force=True, log='%s.%d' % (log, i // 24), timeout=900)
        print('  batch %d: %s' % (i // 24, r.get('summary')), flush=True)
        for k in ('compile_errors', 'errors'):
            for x in (r.get(k) or [])[:6]: print('  %s: %s' % (k, x))
    out = {}
    for v in vmdls:
        c = os.path.join(FR.GAME, v.replace('/', os.sep) + '_c')
        out[v] = os.path.exists(c) and os.path.getmtime(c) >= t_start - 2
    print('compiled %d / %d in %.0f s (logs %s.*)' % (sum(out.values()), len(vmdls), time.time() - t_start, log))
    return out


def beams_only(compile_):
    made = beam_models(); made['bubble'] = bubble_model()
    ok = {k: True for k in made}
    if compile_:
        mats = [REL_T + '/' + f for f in os.listdir(os.path.join(OUT, REL_T)) if f.startswith(('fx_beam_c_', 'fx_beam_r_', 'fx_mask', 'shield'))]
        res = compile_batch(list(made.values()), mats, 'rc_fx_beams.log'); ok = {k: res[v] for k, v in made.items()}

    def upd(data):
        fx = data.setdefault('fx', {})
        for k in [k for k in fx if k.startswith(('beam_c_', 'beam_r_'))]: del fx[k]          # a changed ladder leaves no old rungs behind
        fx.update({k: v for k, v in made.items() if ok[k]})
    data = models_json_update(upd)
    bad = [k for k in made if not ok[k]]
    print('models.json#fx: %d entries (%d beam rungs + bubble written)%s' % (len(data['fx']), len(made) - 1, ('; FAILED: ' + ', '.join(bad)) if bad else ''))
    return 1 if bad else 0


def main():
    compile_ = '--no-compile' not in sys.argv
    if '--crate-only' in sys.argv:   # add just the supply crate to models.json#fx (does not touch the other effect models)
        v = crate_model(); ok = True
        if compile_:
            cres = FR.compile_models(OUT, ['models/ifr/fx/crate', 'materials/ifr/fx'], [v], os.path.join(FR.json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work'], 'logs', 'rc_fx_crate.log'))
            ok, sec, pr = cres[v]; print('compile crate', 'OK' if ok else 'FAIL', '; '.join(pr)[:200])
        def upd_crate(data):
            if ok: data.setdefault('fx', {})['crate'] = v
        data = models_json_update(upd_crate); print('models.json#fx.crate =', data['fx'].get('crate')); return 0 if ok else 1
    if '--beams-only' in sys.argv: return beams_only(compile_)   # the beam ladder + the shield bubble; the other effect models are not touched
    made = {}
    em = lambda name, rgb, bright: fx_models.emissive(OUT, REL_T, 'fx_' + name, rgb, bright, 'IRONFRAME self-lit effect material (generated)')
    # null: one tiny triangle (pool idle model / template source prop)
    m = geo.Mesh(); m.V = np.array([[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0.0]]); m.N = np.tile([0, 0, 1.0], (3, 1)); m.F = np.array([[0, 1, 2]])
    made['null'] = write_model(REL_M + '/null', 'null', m, flat_vmat('null', (40, 40, 40)), vmdl_path='models/ifr/null.vmdl')
    # placeholder box mech, 288 u, feet at z 0, faces +x
    ph = merge([box(44, 40, 165, (0, -32, 82.5)), box(44, 40, 165, (0, 32, 82.5)), box(90, 120, 120, (4, 0, 210)), box(40, 44, 26, (14, 0, 275)),
                box(30, 24, 90, (-10, -72, 215)), box(30, 24, 90, (-10, 72, 215)), box(20, 16, 10, (30, 0, 272))])
    made['placeholder'] = write_model(REL_M + '/placeholder', 'placeholder', ph, flat_vmat('placeholder', (128, 130, 134), 0.65, 0.4), uv=ph.V[:, [1, 2]] / 64.0, hull=True)
    made['tracer'] = write_model(REL_M + '/tracer', 'tracer', tube((-110, 0, 0), (0, 0, 0), 0.5, 1.4, 6), em('tracer', (255, 196, 90), 40.0))
    made['tracer_heavy'] = write_model(REL_M + '/tracer_heavy', 'tracer_heavy', tube((-160, 0, 0), (0, 0, 0), 1.0, 2.8, 8), em('tracer_heavy', (255, 150, 60), 40.0))
    made['beam'] = write_model(REL_M + '/beam', 'beam', tube((0, 0, 0), (100, 0, 0), 2.5, 2.5, 8), em('beam', (90, 225, 255), 30.0))
    made['beam_red'] = write_model(REL_M + '/beam_red', 'beam_red', tube((0, 0, 0), (100, 0, 0), 3.0, 3.0, 8), em('beam_red', (255, 70, 60), 30.0))
    ring = merge([fx_models.ring(34, 38, axis='x'), fx_models.ring(0.0, 3, n=12, axis='x')] +
                 [fx_models.bar(*b, axis='x') for b in ((44, -1.5, 66, 1.5), (-66, -1.5, -44, 1.5), (-1.5, 44, 1.5, 66), (-1.5, -66, 1.5, -44))])
    made['ring'] = write_model(REL_M + '/ring', 'ring', ring, em('ring', (255, 220, 120), 12.0))
    land = merge([fx_models.ring(108, 118), fx_models.ring(14, 20)] + [fx_models.bar(*b) for b in ((126, -3, 168, 3), (-168, -3, -126, 3), (-3, 126, 3, 168), (-3, -168, 3, -126))])
    made['landing'] = write_model(REL_M + '/landing', 'landing', land, em('landing', (255, 70, 40), 12.0))
    made['missile'], msl_src = missile()
    sph = sphere(100.0)
    made['shield'] = write_model(REL_M + '/shield', 'shield', sph, flat_vmat('shield', (90, 200, 255), 0.2, 0.0, translucent=0.3, backfaces=True))
    # IFF marker: a tall emissive diamond (bipyramid, ~60 u), white so SetColor tints it fully
    iffgeo = lambda: merge([geo.lathe([(0.01, -30), (16, -4), (0.01, 30)], sides=4, mat='m'), geo.lathe([(0.01, -30), (16, -4), (0.01, 30)], sides=4, mat='m')])
    # the self-lit material ignores SetColor, so each team colour is its own pre-coloured model
    # team colours must survive the self-illum: at brightness 12-40 every channel clips and the marker reads white (10 Nov 2026 playtest:
    # "the diamonds above player heads are ALL white"); saturated colours at brightness 1.6 keep the hue
    for nm, rgb in (('iff', (255, 255, 255)), ('iff_t', (255, 110, 10)), ('iff_ct', (20, 150, 255)), ('iff_red', (255, 30, 30))):
        made[nm] = write_model(REL_M + '/' + nm, nm, iffgeo(), em(nm, rgb, 1.6))
    # drone: small emissive disc ~40 u with a dome
    made['drone'] = write_model(REL_M + '/drone', 'drone', geo.lathe([(0.01, -4), (20, -4), (20, 3), (10, 8), (0.01, 9)], sides=16, mat='m'), em('drone', (120, 230, 255), 14.0))
    # mine: flat red-lit puck ~50 u
    made['mine'] = write_model(REL_M + '/mine', 'mine', geo.lathe([(0.01, 0), (25, 0), (25, 6), (14, 9), (0.01, 9)], sides=16, mat='m'), em('mine', (255, 50, 40), 16.0))
    made.update(beam_models()); made['bubble'] = bubble_model()
    for k, v in made.items(): print('%-12s %s' % (k, v))
    print('missile:', msl_src)
    results = {}
    if compile_:
        cres = FR.compile_models(OUT, ['models/ifr/fx', 'models/ifr/null.vmdl', 'materials/ifr/fx', 'materials/jets'], list(made.values()),
                                 os.path.join(FR.json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work'], 'logs', 'rc_fx.log'))
        for k, v in made.items():
            ok, s, pr = cres[v]; results[k] = ok
            print('compile %-12s %s %5.1fs %s' % (k, 'OK ' if ok else 'FAIL', s, '; '.join(pr)[:160]))
    def upd_all(data):
        data.setdefault('frames', {}); data.setdefault('weapons', {})
        keep = {k: v for k, v in (data.get('fx') or {}).items() if k.startswith('gib_') or k == 'crate'}   # tools/gibs.py and --crate-only entries survive
        data['fx'] = {k: v for k, v in made.items() if results.get(k, True)}
        for k, v in keep.items(): data['fx'].setdefault(k, v)
    data = models_json_update(upd_all)
    bad = [k for k, ok in results.items() if not ok]
    print('models.json#fx: %d entries%s' % (len(data['fx']), ('; FAILED: ' + ', '.join(bad)) if bad else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
