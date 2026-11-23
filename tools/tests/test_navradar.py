"""C3 navradar.py: a tiny synthetic nav (two floors joined by a connection, a ladder, an island) written in the test for
nav versions 30, 33, 35 and 36, parsed, rendered, and framed like radar.py. No game files.

  python -m unittest discover -s tools/tests -p "test_navradar.py" -v
"""
import os, shutil, struct, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import navradar as N

SQUARES = [  # (id, corners): a low floor, a high floor next to it (joined), and a far-off island
    (1, [(0, 0, 0), (512, 0, 0), (512, 512, 0), (0, 512, 0)]),
    (2, [(512, 0, 128), (1024, 0, 128), (1024, 512, 128), (512, 512, 128)]),
    (3, [(3000, 3000, 0), (3064, 3000, 0), (3064, 3064, 0), (3000, 3064, 0)]),
]
CONN = {1: {1: [(2, 3)]}, 2: {3: [(1, 1)]}}          # area -> edge -> [(other area, other edge)]


def kv3(buf1=b'\0' * 4, buf2=b'\x01\x00\xdd\xee\xff'):
    """A stored (uncompressed) binary KV3 v5 block shaped like the navs on the PC: 120-byte header + two buffers."""
    h = b'\x053VK' + b'\x11' * 16 + struct.pack('<IHH4I2H4I2I4I4I4I', 0, 0, 0, 0, 1, 0, 1, 0, 0, len(buf1) + len(buf2),
                                                len(buf1) + len(buf2), 0, 0, 0, 0, len(buf1), 0, len(buf2), 0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert len(h) == 120
    return h + buf1 + buf2


def build(ver):
    b = bytearray(struct.pack('<IIIB', N.MAGIC, ver, 1, 1))
    b += struct.pack('<H', 1) + struct.pack('<H', 5) + b'Yard\0' + b'\0'
    def align(): b.extend(b'\0' * (-len(b) % 8))
    if ver >= 36: align(); b += kv3()
    if ver >= 31:
        corners = [c for _, cs in SQUARES for c in cs]
        b += struct.pack('<I', len(corners)) + b''.join(struct.pack('<3f', *c) for c in corners)
        b += struct.pack('<I', len(SQUARES))
        for i, (_, cs) in enumerate(SQUARES):
            b += struct.pack('<B', 4) + struct.pack('<4I', *range(4 * i, 4 * i + 4))
            if ver >= 35: b += struct.pack('<I', N.NO_MOVABLE)
        if ver >= 32: b += struct.pack('<I', 0)              # no corner gravity
    if ver >= 35: b += struct.pack('<I', 1) + b'mover\0' + b'\0' * 48
    if ver >= 36: align(); b += kv3()
    b += struct.pack('<I', len(SQUARES))
    for i, (aid, cs) in enumerate(SQUARES):
        b += struct.pack('<IqB', aid, 0, 0)
        b += struct.pack('<I', i) if ver >= 31 else struct.pack('<I', 4) + b''.join(struct.pack('<3f', *c) for c in cs)
        b += struct.pack('<f', 0)
        for e in range(4):
            cs_ = CONN.get(aid, {}).get(e, [])
            b += struct.pack('<I', len(cs_)) + b''.join(struct.pack('<II', *c) for c in cs_)
        b += struct.pack('<B', 1) + struct.pack('<I3fB', 7, 10, 10, 0, 1) if aid == 1 else struct.pack('<B', 0)
        b += struct.pack('<I', 0)                            # encounter paths
        b += struct.pack('<I', 1 if aid == 1 else 0) + (struct.pack('<I', 1) if aid == 1 else b'')
        b += struct.pack('<I', 0)
    b += struct.pack('<I', 1)                                # one ladder from area 1 up to area 2
    b += struct.pack('<If3f3ffI', 1, 32, 500, 256, 128, 500, 256, 0, 128, 2) + struct.pack('<5I', 2, 0, 0, 0, 1)
    if ver >= 33: b += struct.pack('<2I', 0, 0)
    b += struct.pack('<i', 0)                                # transformed bounds (not read)
    return bytes(b)


class Parse(unittest.TestCase):
    def test_versions(self):
        for ver in (30, 31, 33, 35, 36):
            with self.subTest(ver=ver):
                n = N.read_nav(build(ver))
                self.assertEqual(n['version'], ver)
                self.assertEqual(n['places'], ['Yard'])
                self.assertEqual([a['id'] for a in n['areas']], [1, 2, 3])
                np.testing.assert_allclose(n['areas'][1]['corners'][0], (512, 0, 128))
                self.assertEqual(n['areas'][0]['connections'][1], [(2, 3)])
                self.assertEqual(n['areas'][0]['ladders_above'], [1])
                L = n['ladders'][0]
                self.assertEqual((L['id'], L['width'], L['top'], L['areas'][0]), (1, 32, (500, 256, 128), 2))
                self.assertEqual(n['end'], len(build(ver)) - 4)

    def test_rejects(self):
        with self.assertRaises(N.NavError): N.read_nav(b'\0' * 32)
        bad = bytearray(build(36)); bad[4] = 29
        with self.assertRaises(N.NavError): N.read_nav(bytes(bad))
        bad = bytearray(build(36)); i = bad.index(b'\x053VK'); bad[i] = 4
        with self.assertRaises(N.NavError): N.read_nav(bytes(bad))

    def test_islands(self):
        g = N.islands(N.read_nav(build(36))['areas'])
        self.assertEqual(sorted(map(len, g)), [1, 2])

    def test_expand(self):
        Q = N.expand(np.array(SQUARES[0][1], float), 16)
        np.testing.assert_allclose(Q[:, :2].min(0), (-16, -16)); np.testing.assert_allclose(Q[:, :2].max(0), (528, 528))
        Q = N.expand(np.array(SQUARES[0][1][::-1], float), 16)  # either winding grows outwards
        np.testing.assert_allclose(Q[:, :2].min(0), (-16, -16))


class Render(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_and_cli(self):
        nav = N.read_nav(build(36))
        img, (px, py, scale, span), st = N.render(nav, 256, min_island=2)
        self.assertEqual(img.size, (256, 256)); self.assertEqual(st['islands_dropped'], 1); self.assertEqual(st['areas'], 2)
        self.assertAlmostEqual(span, 1024 * 1.06 + 256, delta=12)      # radar.py framing on the two floors
        A = np.asarray(img)
        def at(x, y): return A[int((py - y) / scale), int((x - px) / scale)]
        lo, hi, out = at(256, 256), at(768, 256), at(256, 900)
        self.assertEqual(lo[3], 255); self.assertEqual(hi[3], 255); self.assertEqual(out[3], 0)
        self.assertGreater(int(hi[:3].sum()), int(lo[:3].sum()) + 100)  # the higher floor is lighter
        p = os.path.join(self.tmp, 'm.nav')
        with open(p, 'wb') as f: f.write(build(35))
        png, txt = os.path.join(self.tmp, 'r.png'), os.path.join(self.tmp, 'o.txt')
        self.assertEqual(N.main([p, png, '--overview', txt, '--ct', '0,0', '--min-island', '2']), 0)
        with open(txt) as f: t = f.read()
        for k in ('"m"', '"material"\t"overviews/m_radar"', '"pos_x"', '"scale"', '"CTSpawn_x"'): self.assertIn(k, t)
        from PIL import Image
        with Image.open(png) as im: self.assertEqual(im.size, (1024, 1024))


if __name__ == '__main__':
    unittest.main()
