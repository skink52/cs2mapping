import os, struct, re
import numpy as np
from PIL import Image
FD = os.environ.get('FREEDOOM_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'freedoom'))

def palette():
    d = open(FD + '/lumps/playpal/playpal-base.lmp', 'rb').read()
    return np.frombuffer(d, np.uint8).reshape(256, 3).copy()
PAL = palette()

def grab(path):
    d = open(path, 'rb').read(); i = 8
    while i < len(d):
        ln, = struct.unpack('>I', d[i:i+4]); t = d[i+4:i+8]
        if t == b'grAb':
            return struct.unpack('>ii', d[i+8:i+16])
        i += 12 + ln
    return (0, 0)

def load_rgba(path):
    im = Image.open(path)
    if im.mode == 'P':
        trans = im.info.get('transparency')
        a = np.array(im)
        p = np.array(im.getpalette()[:768] + [0] * (768 - len(im.getpalette()[:768])), np.uint8).reshape(256, 3)
        rgba = np.zeros(a.shape + (4,), np.uint8)
        rgba[..., :3] = p[a]
        rgba[..., 3] = 255
        if isinstance(trans, int):
            rgba[a == trans, 3] = 0
        elif isinstance(trans, bytes):
            ta = np.frombuffer(trans + b'\xff' * (256 - len(trans)), np.uint8)
            rgba[..., 3] = ta[a]
    else:
        rgba = np.array(im.convert('RGBA'))
    # deutex treats pure cyan as transparent
    cy = (rgba[..., 0] == 0) & (rgba[..., 1] == 255) & (rgba[..., 2] == 255)
    rgba[cy, 3] = 0
    rgba[rgba[..., 3] < 128, 3] = 0
    rgba[rgba[..., 3] >= 128, 3] = 255
    return rgba

def find_file(d, name):
    p = os.path.join(FD, d, name.lower() + '.png')
    return p if os.path.exists(p) else None

def parse_textures():
    defs = {}; cur = None; stack = []; on = True
    defined = {'FREEDM'}
    for raw in open(FD + '/lumps/textures/textures.cfg'):
        line = raw.split(';')[0].rstrip()
        s = line.strip()
        if s.startswith('#ifdef'):
            stack.append(on); on = on and (s.split()[1] in defined); continue
        if s.startswith('#ifndef'):
            stack.append(on); on = on and (s.split()[1] not in defined); continue
        if s.startswith('#else'):
            parent = stack[-1]; on = parent and not on; continue
        if s.startswith('#endif'):
            on = stack.pop(); continue
        if not on or not s: continue
        parts = s.split()
        if parts[0] == '*':
            if cur: defs[cur]['patches'].append((parts[1].upper(), int(parts[2]), int(parts[3])))
        else:
            cur = parts[0].upper()
            defs[cur] = dict(w=int(parts[1]), h=int(parts[2]), patches=[])
    return defs
TEXDEFS = parse_textures()

_tc = {}
def texture(name):
    name = name.upper()
    if name in _tc: return _tc[name]
    td = TEXDEFS.get(name)
    if td is None:
        _tc[name] = None; return None
    out = np.zeros((td['h'], td['w'], 4), np.uint8)
    for pn, ox, oy in td['patches']:
        f = find_file('patches', pn) or find_file('graphics', pn) or find_file('sprites', pn) or find_file('flats', pn)
        if not f:
            print('missing patch', pn, 'for', name); continue
        p = load_rgba(f)
        ph, pw = p.shape[:2]
        x0, y0 = max(ox, 0), max(oy, 0)
        x1, y1 = min(ox + pw, td['w']), min(oy + ph, td['h'])
        if x1 <= x0 or y1 <= y0: continue
        src = p[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        m = src[..., 3] > 0
        reg = out[y0:y1, x0:x1]
        reg[m] = src[m]
    _tc[name] = out
    return out

def flat(name):
    f = find_file('flats', name)
    if not f: return None
    return load_rgba(f)

def parse_buildcfg():
    """offsets declared in buildcfg.txt (deutex wadinfo), per section"""
    defined = {'FREEDM', 'PHASE2'}
    sec = None; stack = []; on = True; out = {}
    for raw in open(FD + '/buildcfg.txt'):
        line = raw.split(';')[0].strip()
        if not line: continue
        if line.startswith('#ifdef'): stack.append(on); on = on and line.split()[1] in defined; continue
        if line.startswith('#ifndef'): stack.append(on); on = on and line.split()[1] not in defined; continue
        if line.startswith('#else'): on = stack[-1] and not on; continue
        if line.startswith('#endif'): on = stack.pop(); continue
        if line.startswith('#'): continue
        if not on: continue
        if line.startswith('['): sec = line.strip('[]').lower(); out.setdefault(sec, {}); continue
        parts = line.split()
        if len(parts) >= 3 and sec:
            try: out[sec][parts[0].upper()] = (int(parts[1]), int(parts[2]))
            except ValueError: pass
    return out
BUILDCFG = parse_buildcfg()

def offsets(section, name, path):
    o = BUILDCFG.get(section, {}).get(name.upper())
    if o is not None: return o
    return grab(path)

def sprite(name):
    f = find_file('sprites', name)
    if not f: return None
    return load_rgba(f), offsets('sprites', name, f)

def graphic(name):
    f = find_file('graphics', name)
    if not f: return None
    return load_rgba(f), offsets('graphics', name, f)
