"""Hat placement data in a GMod item's lua, read as text (nothing is run).

Pointshop 1 items (lua/pointshop/items/<cat>/<file>.lua):
    ITEM.Model = 'models/foo/hat.mdl'   ITEM.Attachment = 'eyes'  (or ITEM.Bone = 'ValveBiped.Bip01_Head1')
    function ITEM:ModifyClientsideModel(ply, model, pos, ang)
        model:SetModelScale(1.6, 0)                       -- or: local mat = Matrix(); mat:Scale(Vector(..)); EnableMatrix
        local MPos = Vector(-2.6, 0, 0)                  -- PS1 editor style: offsets and angles in locals
        pos = pos + (ang:Forward() * -3) + (ang:Up() * MPos.z) + (ang:Right() * 0.5)
        ang:RotateAroundAxis(ang:Right(), 90)
        return model, pos, ang
    end
The function body is replayed in order (luahats.ops): ('move', axis, units) and ('rot', axis, degrees), axis one of forward /
right / up of the current angle, plus the model scale (x, y, z). hat2cs2.py applies them to the attachment's frame.
Returns {mdl path (lower, models/..): {'kind', 'name', 'attach', 'scale' [x,y,z], 'ops', 'file'}}.
"""
import glob, os, re

NUM = r'-?\d*\.?\d+(?:e-?\d+)?'
AXES = ('forward', 'right', 'up')


def _num(s, d=0.0):
    try: return float(s)
    except (TypeError, ValueError): return d


def _value(expr, env):
    """a number, a -number, or NAME.x/.y/.z/.p/.r (Vector / Angle locals), or a product of those"""
    expr = expr.strip().strip('()').strip()
    if '*' in expr:
        v = 1.0
        for part in expr.split('*'):
            x = _value(part, env)
            if x is None: return None
            v *= x
        return v
    neg = expr.startswith('-')
    if neg: expr = expr[1:].strip()
    if re.fullmatch(NUM, expr): v = float(expr)
    else:
        m = re.fullmatch(r'(\w+)\.(\w)', expr)
        if not m or m[1] not in env: return None
        vec = env[m[1]]; k = {'x': 0, 'y': 1, 'z': 2, 'p': 0, 'r': 2}.get(m[2], 1)   # Angle(p, y, r): .y is the yaw (index 1)
        v = vec[k]
    return -v if neg else v


def ops(body):
    """replay a ModifyClientsideModel body: (ops, scale xyz)"""
    env, out, scale = {}, [], [1.0, 1.0, 1.0]
    for raw in body.split('\n'):
        line = raw.split('--')[0].strip()
        if not line: continue
        m = re.match(r'(?:local\s+)?(\w+)\s*=\s*(?:Vector|Angle)\s*\(\s*(' + NUM + r')\s*,\s*(' + NUM + r')\s*,\s*(' + NUM + r')\s*\)', line)
        if m: env[m[1]] = [float(m[2]), float(m[3]), float(m[4])]; continue
        m = re.search(r'SetModelScale\s*\(\s*Vector\s*\(\s*(' + NUM + r')\s*,\s*(' + NUM + r')\s*,\s*(' + NUM + r')', line)
        if m: scale = [scale[i] * float(m[i + 1]) for i in range(3)]; continue
        m = re.search(r'SetModelScale\s*\(\s*([^,)]+)', line)
        if m and (v := _value(m[1], env)) is not None: scale = [s * v for s in scale]; continue
        m = re.search(r'\w+\s*:\s*Scale\s*\(\s*(?:Vector\s*\(\s*(' + NUM + r')\s*,\s*(' + NUM + r')\s*,\s*(' + NUM + r')\s*\)|(\w+))\s*\)', line)
        if m:
            vec = [float(m[1]), float(m[2]), float(m[3])] if m[1] else env.get(m[4], [1, 1, 1])
            scale = [scale[i] * vec[i] for i in range(3)]; continue
        m = re.search(r'RotateAroundAxis\s*\(\s*ang\s*:\s*(Forward|Right|Up)\s*\(\s*\)\s*,\s*([^)]+)\)', line, re.I)
        if m:
            v = _value(m[2], env)
            if v: out.append(('rot', m[1].lower(), v))
            continue
        m = re.match(r'pos\s*=\s*pos\s*(.*)', line)
        if m:
            rest = m[1]
            for sign, axis, val in re.findall(r'([+-])\s*\(?\s*ang\s*:\s*(Forward|Right|Up)\s*\(\s*\)\s*\*\s*([-\w.]+)', rest, re.I):
                v = _value(val, env)
                if v: out.append(('move', axis.lower(), -v if sign == '-' else v))
            for sign, val, axis in re.findall(r'([+-])\s*\(?\s*(' + NUM + r'|\w+\.\w)\s*\*\s*ang\s*:\s*(Forward|Right|Up)\s*\(\s*\)', rest, re.I):
                v = _value(val, env)
                if v: out.append(('move', axis.lower(), -v if sign == '-' else v))
    return out, scale


def parse_ps1(txt):
    m = re.search(r'ITEM\.Model\s*=\s*["\']([^"\']+\.mdl)["\']', txt, re.I)
    if not m: return None
    rec = {'kind': 'pointshop1', 'model': m[1].replace('\\', '/').lower()}
    n = re.search(r'ITEM\.Name\s*=\s*["\']([^"\']+)["\']', txt); rec['name'] = n[1] if n else ''
    a = re.search(r'ITEM\.Attachment\s*=\s*["\']([^"\']+)["\']', txt, re.I)
    b = re.search(r'ITEM\.Bone\s*=\s*["\']([^"\']+)["\']', txt, re.I)
    if not a and not b: return None                 # not a worn item (trails, weapons, player models)
    rec['attach'] = a[1] if a else b[1]
    rec['attach_kind'] = 'attachment' if a else 'bone'
    body = re.search(r'ModifyClientsideModel\s*\((.*?)\n\s*end\b', txt, re.S | re.I)
    rec['ops'], rec['scale'] = ops(body[1] if body else '')
    return rec


def parse_dir(root):
    out = {}
    for f in sorted(glob.glob(os.path.join(root, 'lua', '**', '*.lua'), recursive=True)):
        try: txt = open(f, encoding='latin-1').read()
        except OSError: continue
        rec = parse_ps1(txt)
        if rec:
            rec['file'] = os.path.relpath(f, root).replace('\\', '/')
            out.setdefault(rec['model'], rec)
    return out


if __name__ == '__main__':
    import json, sys
    print(json.dumps(parse_dir(sys.argv[1]), indent=1))
