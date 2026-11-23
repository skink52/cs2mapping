"""Post-processing from CS:GO: color_correction entities -> .vpost colour layers, and an underwater .vpost per water fog colour.

  python postfx.py <file.raw> [weight] [--curves]   print the .vpost a CS:GO colour-correction table becomes

CS:GO's color_correction drew the screen through a 32x32x32 RGB lookup table (`.raw`, red fastest, 98,304 bytes) with weight
maxweight, everywhere (minfalloff / maxfalloff -1) or fading out between minfalloff and maxfalloff of the entity. Valve's importer
drops the entity (cs2-gotchas). CS2's post_processing_volume points at a .vpost whose colour layers resourcecompiler bakes into
one 32^3 RGBA8 table inside the .vpost_c (m_colorCorrectionVolumeData, 131,072 bytes).

Compile test, 23 Nov 2026 (addon zz_borrowed_test, the .vpost_c decoded): a CColorLookupColorCorrectionLayer with `m_nDim = 32` and
`m_lut = [ r, g, b, r, g, b, ... ]` (98,304 floats 0..1, red fastest: the .raw's own order) bakes the table exactly (every entry
within 1/255). `m_lut` as a file path is ignored (identity, m_bHasColorCorrection false), and as a list of [r, g, b] triples it
bakes all black. So the CS:GO table goes in whole, inline (`lut_layer`, the default). CS2-Porter's route (a Curves layer per
channel for the greys + one Saturation value, `cc_layers`) is kept as `mode='curves'` for a table that must stay small.

From CS2-Porter postfx.py (MIT, copyright bcanusar), adapted: the exact lookup-table layer (ours, from the compile test above), our .vpost text layout, the underwater vpost
built on our own filmic underwater template (tools/postprocess_filmic_underwater.vpost, from ba_jail_seaside) with a fog-tint
Curves layer in front, the fog colour read from the CS:GO water VMT ($fogcolor), entities from the VMF, and post_processing_volumes
built like watervol's.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LUT_SIZE = 32
RAW_BYTES = LUT_SIZE ** 3 * 3
CC_NAME = 'Color Correction (CS:GO)'
CURVE_STEPS = (0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 31)
SAT_MIN = 3
VPOST_DIR = 'lighting/postprocessing'
HEAD = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} '
        'format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n')
TEMPLATE_UNDERWATER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'postprocess_filmic_underwater.vpost')
UNDERWATER_VPOST = 'lighting/postprocessing/postprocess_filmic_underwater.vpost'   # what watervol points the volumes at
UNDERWATER_TINT = 0.45          # how far the picture is pulled to the fog colour
UNDERWATER_SATURATION = -25


# ------------------------------------------------------------------ CS:GO table -> layers
def read_lut(data):
    """.raw bytes -> float array [b][g][r][rgb] 0..1, None when it is not a 32^3 table"""
    import numpy as np
    if not data or len(data) != RAW_BYTES: return None
    return np.frombuffer(data, dtype=np.uint8).reshape(LUT_SIZE, LUT_SIZE, LUT_SIZE, 3).astype(np.float32) / 255.0


def identity_lut():
    import numpy as np
    i = np.arange(LUT_SIZE) / (LUT_SIZE - 1.0)
    b, g, r = np.meshgrid(i, i, i, indexing='ij')
    return np.stack([r, g, b], axis=-1).astype(np.float32)


def layer(cls, name, body):
    return ('\t\t{\n\t\t\t_class = "%s"\n\t\t\tm_name = "%s"\n\t\t\tm_nOpacityPercent = 100\n\t\t\tm_bVisible = true\n'
            '\t\t\tm_pLayerMask = null\n%s\n\t\t},' % (cls, name, body))


def curves_body(curves):
    """curves: {'R': [(x, y)], ...} 0..255 ints"""
    return '\n'.join('\t\t\tm_curvePoints%s = [ %s ]' % (ch, ', '.join('[ %d, %d ]' % p for p in curves[ch])) for ch in ('R', 'G', 'B') if curves.get(ch))


def cc_layers(lut, weight=1.0):
    """Layer texts that give about the same look as a CS:GO colour-correction table at `weight` (maxweight)."""
    import numpy as np
    weight = min(max(float(weight), 0.0), 1.0)
    idx = np.arange(LUT_SIZE); gin = idx / (LUT_SIZE - 1.0)
    gout = gin[:, None] + (lut[idx, idx, idx] - gin[:, None]) * weight      # (32, 3): the table on the grey diagonal
    curves = {}
    for ci, ch in enumerate('RGB'):
        pts = [(int(round(gin[i] * 255)), int(round(min(max(gout[i, ci], 0.0), 1.0) * 255))) for i in CURVE_STEPS]
        if any(abs(x - y) > 1 for x, y in pts): curves[ch] = pts
    out = [layer('CCurvesColorCorrectionLayer', CC_NAME, curves_body(curves))] if curves else []
    rgb_in = identity_lut()
    curved = np.stack([np.interp(rgb_in[..., k], gin, gout[:, k]) for k in range(3)], axis=-1)
    want = rgb_in + (lut - rgb_in) * weight
    cc, cw = curved.max(-1) - curved.min(-1), want.max(-1) - want.min(-1)
    sel = cc > 0.15
    if sel.any():
        ratio = float(np.median(cw[sel] / cc[sel]))
        sat = (ratio - 1.0) / 0.01 if ratio < 1.0 else (ratio - 1.0) / 0.0064    # -50 halves colour, +50 ~1/3 stronger (CS2-Porter's measurement)
        sat = int(round(max(-100.0, min(100.0, sat))))
        if abs(sat) >= SAT_MIN:
            out.append(layer('CVibranceColorCorrectionLayer', CC_NAME + ' 2', '\t\t\tm_nVibrance = 0\n\t\t\tm_nSaturation = %d' % sat))
    return out


def lut_layer(lut, weight=1.0, filename=''):
    """CColorLookupColorCorrectionLayer holding the whole table (blended towards identity by weight), inline as 98,304 floats.
    Same layout as CS2's Post Processing editor writes when it loads a .raw (m_fileName = the .raw, m_lut = the floats; the
    hand-made mg_bombardment.vpost of 10 Oct 2026); the compiler reads m_lut only."""
    import numpy as np
    weight = min(max(float(weight), 0.0), 1.0)
    t = identity_lut() + (lut - identity_lut()) * weight
    vals = np.clip(t, 0.0, 1.0).reshape(-1, 3)
    rows = ',\n'.join('\t\t\t\t' + ', '.join('%.3f' % x for x in v) for v in vals.reshape(-1, 96))   # 32 entries a line
    fn = '\t\t\tm_fileName = "%s"\n' % filename if filename else ''
    return layer('CColorLookupColorCorrectionLayer', CC_NAME, '%s\t\t\tm_nDim = %d\n\t\t\tm_lut = \n\t\t\t[\n%s\n\t\t\t]' % (fn, LUT_SIZE, rows))


def is_identity(lut, weight=1.0, tol=1.0 / 255.0):
    import numpy as np
    return float(np.abs((lut - identity_lut()) * min(max(weight, 0.0), 1.0)).max()) <= tol


def vpost(layers):
    return HEAD + '{\n\t_class = "CPostProcessData"\n\tm_layers = \n\t[\n' + '\n'.join(layers) + '\n\t]\n}\n'


def add_layers(text, layers, first=True):
    """layers put into a .vpost text (in front: they act first); returns the new text, unchanged when it already has ours"""
    if not layers or CC_NAME in text: return text
    mm = re.search(r'm_layers\s*=\s*\[', text)
    if not mm: return text
    depth, i = 1, mm.end()
    while i < len(text) and depth:
        depth += {'[': 1, ']': -1}.get(text[i], 0); i += 1
    if depth: return text
    start, end = mm.end(), i - 1
    inner = text[start:end]; add = '\n' + '\n'.join(layers)
    new_inner = (add + inner) if first and inner.strip() else (inner.rstrip() + add + '\n\t') if inner.strip() else add + '\n\t'
    return text[:start] + new_inner + text[end:]


# ------------------------------------------------------------------ underwater
def fog_colour(kv):
    """CS:GO water VMT keys -> fog colour (r, g, b) 0..1, None when it has none. $fogcolor is "{r g b}" (0-255) or "[r g b]" (0-1)."""
    v = (kv or {}).get('$fogcolor')
    if not v: return None
    nums = [float(x) for x in re.findall(r'[-+]?\d*\.?\d+', v)[:3]]
    if len(nums) != 3: return None
    if '{' in v or max(nums) > 1.0: nums = [x / 255.0 for x in nums]
    return tuple(min(max(x, 0.0), 1.0) for x in nums)


def vmt_fog_keys(c, vmt):
    """{'$fogcolor': value} from a CS:GO VMT (and the one a patch VMT includes). Read here, not with assets.parse_vmt, whose
    value pattern stops at the braces of "{r g b}"."""
    import texfix
    raw = texfix._read_src(c, vmt)
    if raw is None: return {}
    txt = raw.decode('utf-8', 'replace')
    mm = re.search(r'(?i)"?\$fogcolor"?\s+"([^"]*)"', txt)
    if mm: return {'$fogcolor': mm.group(1)}
    inc = re.search(r'(?i)"?include"?\s+"([^"]+)"', txt)
    return vmt_fog_keys(c, inc.group(1).replace('\\', '/').lower()) if inc and inc.group(1).lower() != vmt else {}


def underwater_layers(fog):
    peak = max(max(fog), 1e-6); curves = {}
    for ch, v in zip('RGB', fog):
        k = 1.0 - UNDERWATER_TINT + UNDERWATER_TINT * max(v, 0.0) / peak
        curves[ch] = [(0, 0), (128, int(round(128 * k))), (255, int(round(255 * k)))]
    return [layer('CCurvesColorCorrectionLayer', 'Water Colour', curves_body(curves)),
            layer('CVibranceColorCorrectionLayer', 'Water Saturation', '\t\t\tm_nVibrance = 0\n\t\t\tm_nSaturation = %d' % UNDERWATER_SATURATION)]


def underwater_vpost(fog, template=None):
    """our filmic underwater .vpost (tone mapping + blue-tinted blur bloom) with the fog-colour tint in front"""
    text = template if template is not None else open(TEMPLATE_UNDERWATER, encoding='utf-8').read()
    return add_layers(text.replace(CC_NAME, ''), underwater_layers(fog))


# ------------------------------------------------------------------ stage step
def _find_raw(c, rel):
    """bytes of a .raw: the addon's content folder, <root>/embedded/<addon>, then CS:GO's VPK (c.src, as texfix reads VMTs)"""
    rel = rel.replace('\\', '/').lower()
    for base in (c.content, os.path.join(c.root, 'embedded', c.addon)):
        p = os.path.join(base, rel)
        if os.path.isfile(p): return open(p, 'rb').read()
    src = getattr(c, 'src', None)
    if src is not None:
        try:
            if src.has(rel): return src.read(rel)
        except Exception: return None
    return None


def _vmf_entities(vmfpath, cls):
    import vmf as vmfmod
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    return [e for e in root.ch if e.name == 'entity' and (e.get('classname') or '').lower() == cls]


def color_correction(m, c, vmfpath, mode='lut'):
    """Stage step `colorcorrect`: each CS:GO color_correction -> lighting/postprocessing/<addon>_cc_<n>.vpost holding its whole table
    (mode 'lut', the default) or Curves + Saturation layers (mode 'curves').
    A global one (min/maxfalloff -1, no name) goes onto the master post_processing_volume, made if missing; one with a falloff gets
    a post_processing_volume box of +-maxfalloff round it; a named one (switched by I/O) is written but left for the mapper,
    since a post_processing_volume has no Enable input that fades like color_correction did. Returns the number of vposts written."""
    import numpy as np
    if not vmfpath or not os.path.exists(vmfpath): return 0
    ents = _vmf_entities(vmfpath, 'color_correction')
    if not ents: return 0
    import watervol, dmx, vmapedit as V
    made, todo, n = [], [], 0
    tm = tnode = None
    for e in ents:
        fn = (e.get('filename') or '').strip()
        data = _find_raw(c, fn) if fn else None
        lut = read_lut(data)
        if lut is None: todo.append('%s (table %s not found or not 32^3)' % (e.get('targetname') or e.get('origin'), fn or '-')); continue
        try: weight = float(e.get('maxweight') or 1)
        except ValueError: weight = 1.0
        if is_identity(lut, weight): made.append('%s: identity table, nothing to do' % fn); continue
        lay = [lut_layer(lut, weight, fn.replace(chr(92), '/').lower())] if mode == 'lut' else cc_layers(lut, weight)
        if not lay: made.append('%s: no curve or saturation change, nothing to do' % fn); continue
        n += 1
        rel = '%s/%s_cc_%d.vpost' % (VPOST_DIR, c.addon, n)
        c.write(rel, vpost(lay))
        try: lo_f, hi_f = float(e.get('minfalloff') or -1), float(e.get('maxfalloff') or -1)
        except ValueError: lo_f = hi_f = -1.0
        name = e.get('targetname') or ''
        disabled = (e.get('StartDisabled') or e.get('startdisabled') or '0') == '1'
        if name or disabled:
            made.append('%s -> %s (named / start-disabled: wire it by hand)' % (fn, rel)); todo.append('%s is switched by I/O in CS:GO: hook %s up by hand' % (name or fn, rel)); continue
        if lo_f < 0 or hi_f < 0 or hi_f <= lo_f:       # CS:GO: no falloff (either -1, or min == max) = full weight everywhere
            master = [x for x in m.by_class('post_processing_volume') if (m.P(x, 'master', '0') or '0') == '1']
            own = None
            if master:
                old = (m.P(master[0], 'postprocessing', '') or '').replace('\\', '/')
                ot = None
                if old and old.lower() != 'lighting/postprocessing/filmic_default.vpost':
                    if old in c.files: ot = c.files[old].decode('utf-8', 'replace')
                    elif os.path.isfile(os.path.join(c.content, old)): ot = open(os.path.join(c.content, old), encoding='utf-8', errors='replace').read()
                if ot is not None and 'CColorLookupColorCorrectionLayer' in ot:
                    del c.files[rel]; n -= 1; made.append('%s: the master volume vpost %s already has a lookup table: left' % (fn, old)); continue
                if ot is not None:          # the map's own vpost: the table goes in front of its layers (tone mapping, bloom kept)
                    c.write(old, add_layers(ot, lay)); del c.files[rel]; own = old
                elif old and old.lower() != 'lighting/postprocessing/filmic_default.vpost':
                    made.append('%s -> %s (global, but the master volume uses %s, not in the addon: left)' % (fn, rel, old))
                    todo.append('global colour correction %s not set: the master volume uses %s' % (rel, old)); continue
                else:
                    m.setp(master[0], 'postprocessing', rel)
                    todo.append('the master post_processing_volume now uses %s instead of filmic_default (its tone mapping is not carried): check exposure' % rel)
                for extra in master[1:]:
                    if (m.P(extra, 'postprocessing', '') or '').replace('\\', '/') == (own or old): continue
                    todo.append('the map has %d master post_processing_volumes: only the first got the colour correction' % len(master)); break
            else:
                if tm is None: tm = V.Map(watervol.TEMPLATE); tnode = tm.children(tm.world)[0]
                mv = m.new_entity('post_processing_volume', [0, 0, 0], {'StartDisabled': '0', 'spawnflags': '4097', 'master': '1', 'postprocessing': rel,
                                  'minexposure': '1.0', 'maxexposure': '1.0', 'enableexposure': '1', 'exposurespeedup': '1', 'exposurespeeddown': '1', 'fadetime': '1.0'})
                dmx.geta(m.E[mv], b'children')[2].append(watervol.box(m, tm, tnode, [-8, -8, -8], [8, 8, 8], b'materials/tools/toolsnodraw.vmat'))
            if own: made.append('%s -> added in front of the layers of the master volume vpost %s (global)' % (fn, own)); continue
            made.append('%s -> %s (global, master volume)' % (fn, rel))
        else:
            o = [float(x) for x in (e.get('origin') or '0 0 0').split()]
            if tm is None: tm = V.Map(watervol.TEMPLATE); tnode = tm.children(tm.world)[0]
            mn, mx = [o[k] - hi_f for k in range(3)], [o[k] + hi_f for k in range(3)]
            pv = m.new_entity('post_processing_volume', o, {'StartDisabled': '0', 'spawnflags': '4097', 'master': '0', 'postprocessing': rel,
                              'minexposure': '1.0', 'maxexposure': '1.0', 'enableexposure': '0', 'exposurespeedup': '1', 'exposurespeeddown': '1',
                              'fadetime': '%g' % max(0.1, min(2.0, (hi_f - lo_f) / 256.0))})
            dmx.geta(m.E[pv], b'children')[2].append(watervol.box(m, tm, tnode, mn, mx, b'materials/tools/toolsnodraw.vmat'))
            made.append('%s -> %s (box +-%g u round %s)' % (fn, rel, hi_f, e.get('origin')))
    if made: c.log.append('colorcorrect: %d color_correction -> .vpost %s: %s' % (len(ents), 'lookup-table layers (the CS:GO table, exact)' if mode == 'lut' else 'Curves + Saturation layers', '; '.join(made)[:1200]))
    if todo: c.todo.append('colorcorrect: %s' % '; '.join(todo)[:800])
    if n: c.todo.append('colorcorrect: %d colour-correction vposts (%s) compile to the CS:GO table but are not in-game verified: compare with CS:GO' % (n, 'whole table' if mode == 'lut' else 'curves + saturation, an approximation'))
    return n


def underwater(m, c):
    """Stage step `underwaterfog` (after `water`): each underwater post_processing_volume (watervol's, pointing at the shared filmic
    underwater vpost) gets a vpost tinted to the fog colour of the CS:GO water material of the func_water it sits under; one vpost
    per distinct colour (<addon>_underwater_<n>.vpost). Volumes whose water has no $fogcolor keep the shared one."""
    vols = [e for e in m.by_class('post_processing_volume') if (m.P(e, 'postprocessing', '') or '').replace('\\', '/').lower() == UNDERWATER_VPOST]
    if not vols: return 0
    waters = []
    for w in m.by_class('func_water'):
        mats = set()
        for n_, _ in m.walk(w):
            if m.type(n_) == b'CMapMesh':
                mats.update(x.decode().lower() for x in m.g(m.g(n_, b'meshData'), b'materials') or [])
        try: b = m.bounds(w)
        except Exception: b = None
        if b: waters.append((b, sorted(x for x in mats if 'water' in x)))
    by_col, n = {}, 0
    for v in vols:
        o = m.origin(v); fog = None
        for (lo, hi), mats in waters:
            if all(lo[k] - 1 <= o[k] <= hi[k] + 1 for k in range(2)):
                for mat in mats:
                    fog = fog_colour(vmt_fog_keys(c, mat[:-5] + '.vmt')) if mat.endswith('.vmat') else None
                    if fog: break
            if fog: break
        if not fog: continue
        key = tuple(round(x, 3) for x in fog)
        if key not in by_col:
            by_col[key] = '%s/%s_underwater_%d.vpost' % (VPOST_DIR, c.addon, len(by_col) + 1)
            c.write(by_col[key], underwater_vpost(fog))
        m.setp(v, 'postprocessing', by_col[key]); n += 1
    if n: c.log.append('underwaterfog: %d underwater post_processing_volumes -> %d vposts tinted to the CS:GO water fog colour' % (n, len(by_col)))
    return n


# ------------------------------------------------------------------ CLI
def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if not args: print(__doc__); return 2
    lut = read_lut(open(args[0], 'rb').read())
    if lut is None: print('not a 32^3 .raw table'); return 1
    w = float(args[1]) if len(args) > 1 else 1.0
    print(vpost(cc_layers(lut, w) if '--curves' in argv else [lut_layer(lut, w)])); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
