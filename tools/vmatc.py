"""Compiled CS2 material (vmat_c) -> editable vmat, so stock materials can be copied and tuned (e.g. csgo_water_fancy water for a 3D skybox blend).

  python3 vmatc.py <pak01_dir.vpk> <material path, e.g. materials/liquids/nuke_water.vmat> <out.vmat>   (the needed pak01_NNN.vpk next to the dir file)

Reads the resource's DATA block: KV3 version 5 with LZ4 (method 1) or zstd (method 2, decoded with node's zlib). The layout (strings + aux
values in buffer 1; object counts, bytes, ints, doubles and types in buffer 2) was worked out from CS2's water materials (29 Oct 2026).
Textures are written as the compiled param (g_tFoo "...vtex"): the stock .vtex is used as is. Int/float/vector params keep their g_ names.
"""
import struct, sys, os, subprocess

def lz4_block(src, usz):
    out = bytearray(); i = 0; n = len(src)
    while i < n and len(out) < usz:
        tok = src[i]; i += 1
        ll = tok >> 4
        if ll == 15:
            while True:
                b = src[i]; i += 1; ll += b
                if b != 255: break
        out += src[i:i + ll]; i += ll
        if len(out) >= usz or i >= n: break
        off = src[i] | (src[i + 1] << 8); i += 2
        if off == 0: raise ValueError('bad offset')
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4
        st = len(out) - off
        if st < 0: raise ValueError('bad offset')
        for k in range(ml): out.append(out[st + k])
    return bytes(out[:usz])


def _zstd(data):
    js = "const z=require('zlib');const c=[];process.stdin.on('data',x=>c.push(x));process.stdin.on('end',()=>process.stdout.write(z.zstdDecompressSync(Buffer.concat(c))))"
    return subprocess.run(['node', '-e', js], input=data, capture_output=True, check=True).stdout


def data_block(d):
    fs, hv, ver, bo, bc = struct.unpack_from('<IHHII', d, 0); p = 8 + bo
    for i in range(bc):
        t = d[p:p + 4]; off, sz = struct.unpack_from('<II', d, p + 4)
        if t == b'DATA': return d[p + 4 + off:p + 4 + off + sz]
        p += 12

class R:
    def __init__(s, b, o): s.b = b; s.o = o
    def take(s, n): v = s.b[s.o:s.o + n]; s.o += n; return v

def parse(d):
    b = data_block(d)
    h = [struct.unpack_from('<I', b, o)[0] for o in range(20, 120, 4)]
    nstrbytes, n1bytes, n1ints, n1dbl = h[2], h[3], None, None
    # h: [comp, dict/frame, strbytes, b1bytes, b1ints?, types, ?, usz_total, csz_total, 0,0,0,0, usz1, csz1, usz2, csz2, b2bytes, 0, b2ints, b2dbl, ?, objects, ?, ?]
    usz1, csz1, usz2, csz2 = h[13], h[14], h[15], h[16]
    c1, c2 = b[120:120 + csz1], b[120 + csz1:120 + csz1 + csz2]
    if h[0] == 1: b1 = lz4_block(c1, usz1); b2 = lz4_block(c2, usz2)
    elif h[0] == 2: b1 = _zstd(c1); b2 = _zstd(c2)
    else: b1 = c1; b2 = c2
    strs = b1[:nstrbytes].split(b'\0')
    # b1 aux: bytes, ints (aligned 4), doubles (aligned 8) after the strings
    o = nstrbytes
    aux_bytes = R(b1, o); o = (o + 3) & ~3
    n1i = h[3]
    aux_ints = R(b1, o)
    o2 = o + 4 * n1i
    o2 = (o2 + 7) & ~7
    aux_dbl = R(b1, o2)
    nobj, nb2bytes, nb2ints, nb2dbl, ntypes = h[22], h[17], h[19], h[20], h[5]
    q = 0
    objs = R(b2, q); q += 4 * nobj
    bys = R(b2, q); q += nb2bytes; q = (q + 3) & ~3
    ints = R(b2, q); q += 4 * nb2ints; q = (q + 7) & ~7
    dbl = R(b2, q); q += 8 * nb2dbl
    types = R(b2, q)
    def rtype():
        t = types.take(1)[0]
        if t & 0x80: t &= 0x7f; types.take(1)
        return t
    def val(t, sub=None):
        if t == 1: return None
        if t == 2: return bool(bys.take(1)[0])
        if t in (3, 4): return struct.unpack('<q', dbl.take(8))[0]
        if t == 5: return struct.unpack('<d', dbl.take(8))[0]
        if t == 6:
            i = struct.unpack('<i', ints.take(4))[0]; return '' if i < 0 else strs[i].decode()
        if t == 7:
            n = struct.unpack('<i', ints.take(4))[0]; return bys.take(n)
        if t == 8:
            n = struct.unpack('<i', ints.take(4))[0]; return [val(rtype()) for _ in range(n)]
        if t == 9:
            n = struct.unpack('<i', objs.take(4))[0]; o = {}
            for _ in range(n):
                k = strs[struct.unpack('<i', ints.take(4))[0]].decode(); o[k] = val(rtype())
            return o
        if t == 10:
            n = struct.unpack('<i', ints.take(4))[0]; st = rtype(); return [val(st) for _ in range(n)]
        if t == 11: return struct.unpack('<i', ints.take(4))[0]
        if t == 12: return struct.unpack('<I', ints.take(4))[0]
        if t == 13: return True
        if t == 14: return False
        if t == 15: return 0
        if t == 16: return 1
        if t == 17: return 0.0
        if t == 18: return 1.0
        if t == 19: return struct.unpack('<f', ints.take(4))[0]
        if t == 23: return bys.take(1)[0]
        if t == 24:
            n = bys.take(1)[0]; st = rtype(); return [val(st) for _ in range(n)]
        if t == 25:
            n = bys.take(1)[0]; st = rtype()
            if st == 5: return [struct.unpack('<d', aux_dbl.take(8))[0] for _ in range(n)]
            if st == 19: return [struct.unpack('<f', aux_ints.take(4))[0] for _ in range(n)]
            return [val(st) for _ in range(n)]
        raise ValueError('type %d at %d' % (t, types.o))
    return val(rtype())


def to_vmat(kv, src=''):
    L = ['// %s, decompiled by vmatc.py' % (src or kv.get('m_materialName', '')), 'Layer0', '{', '\tshader "%s"' % kv['m_shaderName'], '']
    for p in kv.get('m_intParams') or []: L.append('\t%s %d' % (p['m_name'], p['m_nValue']))
    for p in kv.get('m_floatParams') or []: L.append('\t%s "%.6f"' % (p['m_name'], p['m_flValue']))
    for p in kv.get('m_vectorParams') or []:
        if p['m_name'].startswith('Texture'): continue          # default colours of unset texture inputs
        L.append('\t%s "[%s]"' % (p['m_name'], ' '.join('%.6f' % x for x in p['m_value'])))
    for p in kv.get('m_textureParams') or []: L.append('\t%s "%s"' % (p['m_name'], p['m_pValue']))
    attrs = [(a['m_name'], a['m_nValue']) for a in kv.get('m_intAttributes') or [] if not a['m_name'].startswith('Representative')]
    if attrs: L += ['', '\tAttributes', '\t{'] + ['\t\t%s "%d"' % a for a in attrs] + ['\t}']
    sattrs = [(a['m_name'], a['m_value']) for a in kv.get('m_stringAttributes') or []]
    if sattrs: L += ['', '\tSystemAttributes', '\t{'] + ['\t\t%s "%s"' % a for a in sattrs] + ['\t}']
    return '\n'.join(L + ['}', ''])


def set_param(text, name, value):
    """replace (or add) one param line in a vmat written by to_vmat"""
    import re
    line = '\t%s %s' % (name, value)
    if re.search(r'^\t%s ' % re.escape(name), text, re.M):
        return re.sub(r'^\t%s .*$' % re.escape(name), lambda _: line, text, flags=re.M)
    i = text.index('\tshader ')
    j = text.index('\n', i) + 1
    return text[:j] + line + '\n' + text[j:]


def read_vpk_file(dir_vpk, path):
    import vpk
    v = vpk.VPK(dir_vpk); f = path.lower().replace('\\', '/')
    arc = v.archive_of(f)
    d = os.path.dirname(dir_vpk); base = os.path.basename(dir_vpk).replace('_dir.vpk', '')
    return v.read(f, {arc: os.path.join(d, '%s_%03d.vpk' % (base, arc))} if arc is not None and arc != 0x7fff else {})


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    a = sys.argv[1:]
    mat = a[1] if a[1].endswith('_c') else a[1] + '_c'
    kv = parse(read_vpk_file(a[0], mat))
    open(a[2], 'w', encoding='utf-8').write(to_vmat(kv, mat))
    print('wrote', a[2])
