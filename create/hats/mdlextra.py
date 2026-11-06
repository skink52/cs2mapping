"""Bits of a Source 1 MDL that playermodels/srcmdl.py doesn't read: attachments.

    attachments(m) -> {name: {'bone': index, 'local': 3x4 (attachment -> bone)}}
    attachment_world(m, name) -> 3x4 (attachment -> model space, reference pose)
"""
import struct
import numpy as np


def attachments(m):
    d = m.data
    n, off = struct.unpack_from('<ii', d, 240)            # studiohdr_t numlocalattachments, localattachmentindex
    out = {}
    for k in range(n):
        o = off + k * 92                                   # mstudioattachment_t: name, flags, localbone, matrix3x4, unused[8]
        ni, flags, bone = struct.unpack_from('<iIi', d, o)
        e = d.index(b'\0', o + ni)
        name = d[o + ni:e].decode('latin-1')
        mat = np.array(struct.unpack_from('<12f', d, o + 12)).reshape(3, 4)
        out[name.lower()] = {'bone': bone, 'local': mat}
    return out


def compose(a, b):
    """3x4 a after 3x4 b"""
    return np.hstack([a[:, :3] @ b[:, :3], (a[:, :3] @ b[:, 3] + a[:, 3])[:, None]])


def attachment_world(m, name):
    at = attachments(m).get(name.lower())
    if at is None: return None
    return compose(m.bones[at['bone']]['world'], at['local'])
