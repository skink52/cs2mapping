"""Decoder for compiled Source 2 resources (*_c) and binary KV3 (v0 VKV3, v1-v5 KV3).

decode_resource(data) -> Python value of the DATA block (dicts/lists/str/int/float/bool/None/bytes).
read_resource(data)   -> {'version':..., 'blocks': {name: (offset, size)}}
decode_kv3(buf)       -> (format_uuid, value) for a raw binary KV3 blob.
to_kv3_text(value)    -> KV3 text (flags kept when decoded with keep_flags=True).
"""
import ctypes, ctypes.util, struct, uuid

FLAG_NAMES = {1: 'resource', 2: 'resource_name', 3: 'panorama', 4: 'soundevent', 5: 'subclass', 6: 'entity_name'}
KNOWN_FORMATS = {uuid.UUID('7412167c-06e9-4698-aff2-e63eb59037e7'): 'generic'}
TEXT_ENCODING = 'text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d}'


class FlaggedStr(str):
    flag = 0


class FlaggedDict(dict):
    flag = 0


def _flagged(v, flag):
    if not flag:
        return v
    if isinstance(v, str):
        v = FlaggedStr(v)
    elif isinstance(v, dict):
        v = FlaggedDict(v)
    else:
        return v
    v.flag = flag
    return v


# ---------------------------------------------------------------- compression

def _load(name):
    for cand in (ctypes.util.find_library(name), 'lib%s.so.1' % name, 'lib%s.so' % name):
        if not cand:
            continue
        try:
            return ctypes.CDLL(cand)
        except OSError:
            pass
    return None


_lz4 = _load('lz4')
_zstd = _load('zstd')


def lz4_block_py(src, out_size, history=b''):
    """Pure-Python LZ4 block decoder; `history` is a prefix dictionary that matches may reach into."""
    dst = bytearray(history)
    base = len(dst)
    end = base + out_size
    i, n = 0, len(src)
    while i < n:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]; i += lit
        if i >= n or len(dst) >= end:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        if off == 0 or off > len(dst):
            raise ValueError('lz4: bad offset')
        s = len(dst) - off
        if off >= ml:
            dst += dst[s:s + ml]
        else:
            for k in range(ml):
                dst.append(dst[s + k])
    out = bytes(dst[base:])
    if len(out) != out_size:
        raise ValueError('lz4: expected %d bytes, got %d' % (out_size, len(out)))
    return out


def lz4_block(src, out_size, history=b''):
    if _lz4 is not None:
        dst = ctypes.create_string_buffer(max(out_size, 1))
        if history:
            hist = history[-65536:]
            r = _lz4.LZ4_decompress_safe_usingDict(src, dst, len(src), out_size, hist, len(hist))
        else:
            r = _lz4.LZ4_decompress_safe(src, dst, len(src), out_size)
        if r == out_size:
            return dst.raw[:out_size]
    return lz4_block_py(src, out_size, history)


def zstd_decompress(src, out_size):
    if _zstd is None:
        raise RuntimeError('zstd-compressed KV3 needs libzstd (not found)')
    _zstd.ZSTD_decompress.restype = ctypes.c_size_t
    _zstd.ZSTD_isError.argtypes = [ctypes.c_size_t]
    dst = ctypes.create_string_buffer(max(out_size, 1))
    r = _zstd.ZSTD_decompress(dst, ctypes.c_size_t(out_size), src, ctypes.c_size_t(len(src)))
    if _zstd.ZSTD_isError(r) or r != out_size:
        raise ValueError('zstd: expected %d bytes, got %d' % (out_size, r))
    return dst.raw[:out_size]


# ---------------------------------------------------------------- resource container

def read_resource(data):
    file_size, header_ver, ver, block_off, block_count = struct.unpack_from('<IHHII', data, 0)
    if header_ver != 12:
        raise ValueError('not a compiled Source 2 resource (header version %d)' % header_ver)
    blocks = {}
    p = 8 + block_off
    for _ in range(block_count):
        name = data[p:p + 4].decode('ascii', 'replace')
        rel, size = struct.unpack_from('<II', data, p + 4)
        blocks[name] = (p + 4 + rel, size)
        p += 12
    return {'version': ver, 'blocks': blocks}


def decode_resource(data, block='DATA', keep_flags=False):
    off, size = read_resource(data)['blocks'][block]
    return decode_kv3(data[off:off + size], keep_flags)[1]


# ---------------------------------------------------------------- binary KV3

class _Lanes:
    def __init__(s, buf, b1, b2, b4, b8):
        s.buf = buf
        s.p1, s.e1 = b1
        s.p2, s.e2 = b2
        s.p4, s.e4 = b4
        s.p8, s.e8 = b8

    def take(s, fmt):
        size = struct.calcsize(fmt)
        attr = {1: 'p1', 2: 'p2', 4: 'p4', 8: 'p8'}[size]
        p = getattr(s, attr)
        setattr(s, attr, p + size)
        return struct.unpack_from('<' + fmt, s.buf, p)[0]


def _align(x, a):
    return (x + a - 1) & ~(a - 1)


class _Ctx:
    pass


def decode_kv3(buf, keep_flags=False):
    magic = struct.unpack_from('<I', buf, 0)[0]
    if magic == 0x03564B56:
        return _decode_v0(buf, keep_flags)
    if magic & 0xFFFFFF00 != 0x4B563300:
        raise ValueError('not binary KV3 (magic %08x)' % magic)
    version = magic & 0xFF
    if not 1 <= version <= 5:
        raise ValueError('unsupported KV3 version %d' % version)
    fmt = uuid.UUID(bytes_le=bytes(buf[4:20]))
    p = 20
    comp = struct.unpack_from('<I', buf, p)[0]; p += 4
    count_types = count_blocks = size_blobs = 0
    if version == 1:
        c1, c4, c8, size_unc_total = struct.unpack_from('<iiii', buf, p); p += 16
        size_comp_total = len(buf) - p
        frame_size = 0
    else:
        dict_id, frame_size = struct.unpack_from('<HH', buf, p); p += 4
        c1, c4, c8, count_types = struct.unpack_from('<iiii', buf, p); p += 16
        p += 4  # object / array count hints
        size_unc_total, size_comp_total, count_blocks, size_blobs = struct.unpack_from('<iiii', buf, p); p += 16
    c2 = size_block_sizes = 0
    if version >= 4:
        c2, size_block_sizes = struct.unpack_from('<ii', buf, p); p += 8
    if version >= 5:
        (unc1, comp1, unc2, comp2, c1b, c2b, c4b, c8b,
         _nodes, objs_b, _arrs_b, _elems) = struct.unpack_from('<12i', buf, p); p += 48
    else:
        unc1, comp1 = size_unc_total, size_comp_total

    def read_compressed(csize, usize):
        nonlocal p
        if comp == 0:
            out = bytes(buf[p:p + usize]); p += usize
            return out
        src = bytes(buf[p:p + csize]); p += csize
        if comp == 1:
            return lz4_block(src, usize)
        if comp == 2:
            return zstd_decompress(src, usize)
        raise ValueError('unknown KV3 compression %d' % comp)

    ctx = _Ctx()
    ctx.version = version
    ctx.keep_flags = keep_flags
    ctx.blobs = b''
    ctx.blob_lengths = []
    blob_sizes_view = None

    dec1_size = unc1 + size_blobs if (version < 5 and comp == 2) else unc1
    raw1 = read_compressed(comp1, dec1_size)
    b1 = raw1[:unc1]
    o = 0
    l1 = (o, o + c1); o += c1
    if c2:
        o = _align(o, 2)
    l2 = (o, o + c2 * 2); o += c2 * 2
    if c4:
        o = _align(o, 4)
    l4 = (o, o + c4 * 4); o += c4 * 4
    if c8:
        o = _align(o, 8)
    elif version < 5:
        o = _align(o, 8)
    if c8:
        l8 = (o, o + c8 * 8); o += c8 * 8
    else:
        l8 = (o, o)
    lanes1 = _Lanes(b1, l1, l2, l4, l8)
    n_strings = lanes1.take('i')
    strings = []
    if version >= 5:
        q = lanes1.p1
        for _ in range(n_strings):
            e = b1.index(b'\0', q)
            strings.append(b1[q:e].decode('utf-8', 'replace')); q = e + 1
        lanes1.p1 = q
        ctx.aux = lanes1
    else:
        q = o
        for _ in range(n_strings):
            e = b1.index(b'\0', q)
            strings.append(b1[q:e].decode('utf-8', 'replace')); q = e + 1
        types_len = (unc1 - q - 4) if version == 1 else (count_types - (q - o))
        ctx.types, ctx.tp = b1, q
        q += types_len
        if count_blocks == 0:
            if struct.unpack_from('<I', b1, q)[0] != 0xFFEEDD00:
                raise ValueError('KV3: bad trailer')
        else:
            blob_sizes_view = (b1, q)
        ctx.buf = lanes1
        ctx.aux = lanes1
        ctx.obj_lengths = None
    ctx.strings = strings

    if version >= 5:
        b2 = read_compressed(comp2, unc2)
        o = objs_b * 4
        ctx.obj_lengths = [b2, 0]
        lb1 = (o, o + c1b); o += c1b
        if c2b:
            o = _align(o, 2)
        lb2 = (o, o + c2b * 2); o += c2b * 2
        if c4b:
            o = _align(o, 4)
        lb4 = (o, o + c4b * 4); o += c4b * 4
        if c8b:
            o = _align(o, 8)
        lb8 = (o, o + c8b * 8); o += c8b * 8
        ctx.buf = _Lanes(b2, lb1, lb2, lb4, lb8)
        ctx.types, ctx.tp = b2, o
        o += count_types
        if count_blocks == 0:
            if struct.unpack_from('<I', b2, o)[0] != 0xFFEEDD00:
                raise ValueError('KV3: bad trailer')
        else:
            blob_sizes_view = (b2, o)

    if count_blocks > 0:
        vb, vo = blob_sizes_view
        ctx.blob_lengths = list(struct.unpack_from('<%di' % count_blocks, vb, vo)); vo += count_blocks * 4
        if struct.unpack_from('<I', vb, vo)[0] != 0xFFEEDD00:
            raise ValueError('KV3: bad blob trailer')
        vo += 4
        if comp == 0:
            ctx.blobs = bytes(buf[p:p + size_blobs]); p += size_blobs
        elif comp == 1:
            out = bytearray()
            for blen in ctx.blob_lengths:
                end = len(out) + blen
                while len(out) < end:
                    clen = struct.unpack_from('<H', vb, vo)[0]; vo += 2
                    src = bytes(buf[p:p + clen]); p += clen
                    want = min(frame_size or 16384, end - len(out))
                    out += lz4_block(src, want, bytes(out[-65536:]))
            ctx.blobs = bytes(out)
        elif version >= 5:
            ctx.blobs = zstd_decompress(bytes(buf[p:p + size_comp_total - comp1 - comp2]), size_blobs)
            p += size_comp_total - comp1 - comp2
        else:
            ctx.blobs = raw1[unc1:unc1 + size_blobs]
        ctx.blob_pos = 0
        if struct.unpack_from('<I', buf, p)[0] != 0xFFEEDD00:
            raise ValueError('KV3: bad final trailer')

    t, f = _read_type(ctx)
    value = _read_value(ctx, t, f, ctx.buf)
    _check_consumed(ctx, version, o if version >= 5 else None, objs_b * 4 if version >= 5 else None)
    return fmt, value


def _check_consumed(ctx, version, types_end, obj_end):
    lanes = [ctx.buf] + ([ctx.aux] if version >= 5 else [])
    for ln in lanes:
        for p, e in ((ln.p1, ln.e1), (ln.p2, ln.e2), (ln.p4, ln.e4), (ln.p8, ln.e8)):
            if p != e:
                raise ValueError('KV3: lane not fully consumed (%d of %d)' % (p, e))
    if types_end is not None and ctx.tp != types_end:
        raise ValueError('KV3: type stream not fully consumed')
    if obj_end is not None and ctx.obj_lengths[1] != obj_end:
        raise ValueError('KV3: object lengths not fully consumed')
    if ctx.blob_lengths:
        raise ValueError('KV3: binary blobs not fully consumed')


def _read_type(ctx):
    b = ctx.types[ctx.tp]; ctx.tp += 1
    flag = 0
    if ctx.version >= 3:
        if b & 0x80:
            flag = ctx.types[ctx.tp]; ctx.tp += 1
        if b & 0x40:
            ctx.tp += 1
        b &= 0x3F
    else:
        if b & 0x80:
            flag = _legacy_flag(ctx.types[ctx.tp]); ctx.tp += 1
        b &= 0x7F
    return b, flag


def _legacy_flag(f):
    for bit, val in ((1, 1), (2, 2), (8, 3), (16, 4), (32, 5)):
        if f & bit:
            return val
    return 0


def _string(ctx, i):
    return ctx.strings[i] if 0 <= i < len(ctx.strings) else ''


def _read_value(ctx, t, flag, lane):
    v = _read_raw(ctx, t, lane)
    return _flagged(v, flag) if ctx.keep_flags else v


def _read_raw(ctx, t, lane):
    buf = ctx.buf
    if t == 1: return None
    if t == 13: return True
    if t == 14: return False
    if t in (15, 26): return 0
    if t in (16, 27): return 1
    if t == 17: return 0.0
    if t == 18: return 1.0
    if t == 2: return lane.take('B') != 0
    if t == 22: return lane.take('b')
    if t == 23: return lane.take('B')
    if t == 20: return lane.take('h')
    if t == 21: return lane.take('H')
    if t == 11: return lane.take('i')
    if t == 12: return lane.take('I')
    if t == 19: return lane.take('f')
    if t == 3: return lane.take('q')
    if t == 4: return lane.take('Q')
    if t == 5: return lane.take('d')
    if t == 6: return _string(ctx, buf.take('i'))
    if t == 7:
        if ctx.version < 2:
            n = buf.take('i')
            out = buf.buf[buf.p1:buf.p1 + n]; buf.p1 += n
            return bytes(out)
        n = ctx.blob_lengths.pop(0)
        out = ctx.blobs[ctx.blob_pos:ctx.blob_pos + n]; ctx.blob_pos += n
        return bytes(out)
    if t == 8:
        n = buf.take('i')
        out = []
        for _ in range(n):
            st, sf = _read_type(ctx)
            out.append(_read_value(ctx, st, sf, ctx.buf))
        return out
    if t in (10, 24, 25):
        n = buf.take('i') if t == 10 else buf.take('B')
        st, sf = _read_type(ctx)
        el = ctx.aux if t == 25 else buf
        return [_read_value(ctx, st, sf, el) for _ in range(n)]
    if t == 9:
        if ctx.version >= 5:
            ob, op = ctx.obj_lengths
            n = struct.unpack_from('<i', ob, op)[0]; ctx.obj_lengths[1] = op + 4
        else:
            n = buf.take('i')
        out = {}
        for _ in range(n):
            st, sf = _read_type(ctx)
            name = _string(ctx, ctx.buf.take('i'))
            out[name] = _read_value(ctx, st, sf, ctx.buf)
        return out
    raise ValueError('KV3: unknown node type %d' % t)


def _decode_v0(buf, keep_flags):
    encoding = uuid.UUID(bytes_le=bytes(buf[4:20]))
    fmt = uuid.UUID(bytes_le=bytes(buf[20:36]))
    p = 36
    enc_lz4 = uuid.UUID('6847348a-63a1-4f5c-a197-53806fd9b119')
    enc_bc = uuid.UUID('95791a46-95bc-4f6c-a70b-05bca1b7dfd2')
    if encoding == enc_lz4:
        size = struct.unpack_from('<i', buf, p)[0]; p += 4
        data = lz4_block(bytes(buf[p:]), size)
    elif encoding == enc_bc:
        raise NotImplementedError('VKV3 block-compressed encoding not supported')
    else:
        data = bytes(buf[p:])
    r = _Reader(data)
    ctx = _Ctx()
    ctx.keep_flags = keep_flags
    n = r.u('I')
    ctx.strings = [r.cstr() for _ in range(n)]
    t, f = _v0_type(r)
    return fmt, _v0_value(ctx, r, t, f)


class _Reader:
    def __init__(s, d):
        s.d, s.p = d, 0

    def u(s, fmt):
        v = struct.unpack_from('<' + fmt, s.d, s.p)[0]; s.p += struct.calcsize(fmt); return v

    def cstr(s):
        e = s.d.index(b'\0', s.p); v = s.d[s.p:e].decode('utf-8', 'replace'); s.p = e + 1; return v


def _v0_type(r):
    b = r.u('B')
    f = _legacy_flag(r.u('B')) if b & 0x80 else 0
    return b & 0x7F, f


def _v0_value(ctx, r, t, f):
    v = _v0_raw(ctx, r, t)
    return _flagged(v, f) if ctx.keep_flags else v


def _v0_raw(ctx, r, t):
    if t == 1: return None
    if t == 2: return r.u('B') != 0
    if t == 13: return True
    if t == 14: return False
    if t == 15: return 0
    if t == 16: return 1
    if t == 17: return 0.0
    if t == 18: return 1.0
    if t == 3: return r.u('q')
    if t == 4: return r.u('Q')
    if t == 11: return r.u('i')
    if t == 12: return r.u('I')
    if t == 5: return r.u('d')
    if t == 6: return _string(ctx, r.u('i'))
    if t == 7:
        n = r.u('i'); v = r.d[r.p:r.p + n]; r.p += n; return bytes(v)
    if t == 8:
        out = []
        for _ in range(r.u('i')):
            st, sf = _v0_type(r); out.append(_v0_value(ctx, r, st, sf))
        return out
    if t == 10:
        n = r.u('i'); st, sf = _v0_type(r)
        return [_v0_value(ctx, r, st, sf) for _ in range(n)]
    if t == 9:
        out = {}
        for _ in range(r.u('i')):
            name = _string(ctx, r.u('i'))
            st, sf = _v0_type(r)
            out[name] = _v0_value(ctx, r, st, sf)
        return out
    raise ValueError('VKV3: unknown node type %d' % t)


# ---------------------------------------------------------------- KV3 text output

def _fmt_num(v):
    if isinstance(v, float):
        s = '%.6f' % v
        return s
    return str(v)


def _quote(s):
    if '\n' in s:
        return '"""\n' + s + '\n"""'
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _key(k):
    import re
    return k if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k) else _quote(k)


def _text(v, ind, out):
    pre = FLAG_NAMES.get(getattr(v, 'flag', 0), '')
    pre = pre + ':' if pre else ''
    tab = '\t' * ind
    if v is None:
        out.append('null')
    elif isinstance(v, bool):
        out.append('true' if v else 'false')
    elif isinstance(v, (int, float)):
        out.append(_fmt_num(v))
    elif isinstance(v, str):
        out.append(pre + _quote(v))
    elif isinstance(v, bytes):
        out.append('#[' + ' '.join('%02X' % b for b in v) + ']')
    elif isinstance(v, dict):
        if not v:
            out.append(pre + '{}'); return
        out.append(pre + '\n' + tab + '{\n')
        for k, x in v.items():
            out.append(tab + '\t' + _key(k) + ' = ')
            _text(x, ind + 1, out)
            out.append('\n')
        out.append(tab + '}')
    elif isinstance(v, list):
        simple = all(isinstance(x, (int, float, bool)) or x is None for x in v)
        if simple and len(v) <= 16:
            parts = []
            for x in v:
                o = []; _text(x, 0, o); parts.append(''.join(o))
            out.append('[ ' + ', '.join(parts) + ' ]' if v else '[]')
            return
        out.append('\n' + tab + '[\n')
        for x in v:
            out.append(tab + '\t')
            _text(x, ind + 1, out)
            out.append(',\n')
        out.append(tab + ']')
    else:
        raise TypeError(type(v))


def to_kv3_text(value, fmt=uuid.UUID('7412167c-06e9-4698-aff2-e63eb59037e7'), header=True):
    out = []
    if header:
        out.append('<!-- kv3 encoding:%s format:%s:version{%s} -->\n'
                   % (TEXT_ENCODING, KNOWN_FORMATS.get(fmt, 'generic'), fmt))
    _text(value, 0, out)
    s = ''.join(out)
    return s.lstrip('\n') + '\n'
