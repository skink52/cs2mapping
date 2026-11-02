"""Generates the Puppet Brawl model + material sources for a CS2 addon.

Meshes are written as SMD (Z up, Source units), wound counter-clockwise from outside,
which is what the Apache SMDs in the mapgames addon use. The .vmdl files follow the
same modeldoc41 layout as mapgames/models/vehicles/apache/apache.vmdl.
"""
import math, os, struct, sys, zlib

OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/addon"
MAT = "pb_paint"


def norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)


def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def dot(a, b): return sum(x * y for x, y in zip(a, b))


def axis_closest(p, x0, x1):
    x = min(max(p[0], x0), x1)
    return (x, 0.0, 0.0)


class Mesh:
    def __init__(self):
        self.tris = []  # list of 3 (pos, normal, uv)

    def add(self, a, b, c, outward):
        n = cross(sub(b[0], a[0]), sub(c[0], a[0]))
        cen = tuple((a[0][i] + b[0][i] + c[0][i]) / 3 for i in range(3))
        if dot(n, outward(cen)) < 0:
            b, c = c, b
        self.tris.append((a, b, c))

    def smd(self):
        lines = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0",
                 "0 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000", "end", "triangles"]
        for tri in self.tris:
            lines.append(MAT)
            for (p, n, uv) in tri:
                lines.append("0 %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (p[0], p[1], p[2], n[0], n[1], n[2], uv[0], uv[1]))
        lines.append("end")
        return "\n".join(lines) + "\n"


def grid(mesh, rings, outward, normal_fn):
    """rings: list of rings (each a list of points, same count). Closes around."""
    nseg = len(rings[0])
    for r in range(len(rings) - 1):
        for i in range(nseg):
            j = (i + 1) % nseg
            pts = [rings[r][i], rings[r][j], rings[r + 1][j], rings[r + 1][i]]
            v = [(p, normal_fn(p), (k / nseg, r / (len(rings) - 1))) for p, k in zip(pts, [i, j, j, i])]
            mesh.add(v[0], v[1], v[2], outward)
            mesh.add(v[0], v[2], v[3], outward)


def fan(mesh, ring, apex, outward, normal_fn):
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        a, b, c = apex, ring[i], ring[j]
        mesh.add((a, normal_fn(a), (0.5, 0.5)), (b, normal_fn(b), (0, 0)), (c, normal_fn(c), (1, 0)), outward)


def capsule(length=16.0, radius=2.6, seg=14, cap_rings=5):
    m = Mesh()
    out = lambda p: sub(p, axis_closest(p, 0.0, length))
    nrm = lambda p: norm(sub(p, axis_closest(p, 0.0, length)))
    rings = []
    # back cap: from near the pole to the equator at x=0
    for k in range(1, cap_rings + 1):
        phi = (math.pi / 2) * k / cap_rings          # 0 at pole
        x = -radius * math.cos(phi)
        r = radius * math.sin(phi)
        rings.append([(x, r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg)) for i in range(seg)])
    for k in range(0, cap_rings):
        phi = (math.pi / 2) * (cap_rings - k) / cap_rings
        x = length + radius * math.cos(phi) if k > 0 else length
        r = radius * math.sin(phi)
        rings.append([(x, r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg)) for i in range(seg)])
    grid(m, rings, out, nrm)
    fan(m, rings[0], (-radius, 0.0, 0.0), out, nrm)
    fan(m, rings[-1], (length + radius, 0.0, 0.0), out, nrm)
    return m


def octagon(hy, hz, ch):
    """chamfered rectangle in the YZ plane, counter-clockwise"""
    cy, cz = ch * min(hy, hz), ch * min(hy, hz)
    return [(hy, -hz + cz), (hy, hz - cz), (hy - cy, hz), (-hy + cy, hz), (-hy, hz - cz), (-hy, -hz + cz), (-hy + cy, -hz), (hy - cy, -hz)]


def block(length=16.0, y0=3.8, y1=5.2, z0=3.6, z1=4.6, ch=0.38):
    m = Mesh()
    out = lambda p: sub(p, axis_closest(p, 0.0, length))
    stations = [(-1.1, 0.62), (-0.55, 0.9), (0.0, 1.0), (length, 1.0), (length + 0.55, 0.9), (length + 1.1, 0.62)]
    rings = []
    for x, k in stations:
        t = min(max(x / length, 0.0), 1.0)
        hy, hz = (y0 + (y1 - y0) * t) * k, (z0 + (z1 - z0) * t) * k
        rings.append([(x, y, z) for (y, z) in octagon(hy, hz, ch)])
    # smooth normals: accumulate face normals per position
    acc = {}
    def key(p): return (round(p[0], 4), round(p[1], 4), round(p[2], 4))
    tmp = Mesh()
    grid(tmp, rings, out, lambda p: (0, 0, 1))
    fan(tmp, rings[0], (-1.25, 0.0, 0.0), out, lambda p: (0, 0, 1))
    fan(tmp, rings[-1], (length + 1.25, 0.0, 0.0), out, lambda p: (0, 0, 1))
    for (a, b, c) in tmp.tris:
        n = cross(sub(b[0], a[0]), sub(c[0], a[0]))
        for v in (a, b, c):
            k = key(v[0]); s = acc.get(k, (0, 0, 0)); acc[k] = (s[0] + n[0], s[1] + n[1], s[2] + n[2])
    for (a, b, c) in tmp.tris:
        m.tris.append(tuple((v[0], norm(acc[key(v[0])]), v[2]) for v in (a, b, c)))
    return m


def sphere(radius=8.0, seg=18, rings_n=12):
    m = Mesh()
    out = lambda p: p
    nrm = lambda p: norm(p)
    rings = []
    for k in range(1, rings_n):
        th = math.pi * k / rings_n
        z = radius * math.cos(th); r = radius * math.sin(th)
        rings.append([(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z) for i in range(seg)])
    grid(m, rings, out, nrm)
    fan(m, rings[0], (0, 0, radius), out, nrm)
    fan(m, rings[-1], (0, 0, -radius), out, nrm)
    return m


VMDL = """<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
{
	rootNode =
	{
		_class = "RootNode"
		children =
		[
			{
				_class = "MaterialGroupList"
				children =
				[
					{
						_class = "DefaultMaterialGroup"
						remaps =
						[
							{
								from = "pb_paint.vmat"
								to = "materials/puppet_brawl/pb_paint.vmat"
							},
						]
						use_global_default = false
						global_default_material = ""
					},
				]
			},
			{
				_class = "RenderMeshList"
				children =
				[
					{
						_class = "RenderMeshFile"
						name = "%(name)s"
						filename = "models/puppet_brawl/%(name)s.smd"
						import_scale = 1.0
						import_filter =
						{
							exclude_by_default = false
							exception_list = [  ]
						}
					},
				]
			},
		]
		model_archetype = ""
		primary_associated_entity = ""
		document_sub_type = "ModelDocSubType_None"
	}
}"""

VMAT = """// Puppet Brawl - tintable puppet paint. White base: the script tints every part with SetColor.

Layer0
{
	shader "csgo_complex.vfx"

	//---- Color ----
	g_flModelTintAmount "1.000"
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "materials/puppet_brawl/pb_paint_color.png"

	//---- Normal ----
	TextureNormal "materials/default/default_normal.tga"

	//---- Roughness ----
	TextureRoughness "materials/puppet_brawl/pb_paint_rough.png"
}
"""


def png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f: f.write(data)


def main():
    mdir = os.path.join(OUT, "models", "puppet_brawl"); os.makedirs(mdir, exist_ok=True)
    tdir = os.path.join(OUT, "materials", "puppet_brawl"); os.makedirs(tdir, exist_ok=True)
    meshes = {"pb_limb": capsule(), "pb_block": block(), "pb_ball": sphere()}
    for name, mesh in meshes.items():
        with open(os.path.join(mdir, name + ".smd"), "w", newline="\n") as f: f.write(mesh.smd())
        with open(os.path.join(mdir, name + ".vmdl"), "w", newline="\n") as f: f.write(VMDL % {"name": name})
        xs = [p[0] for t in mesh.tris for (p, n, uv) in t]; ys = [p[1] for t in mesh.tris for (p, n, uv) in t]; zs = [p[2] for t in mesh.tris for (p, n, uv) in t]
        print("%-9s %4d tris  x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f" % (name, len(mesh.tris), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    with open(os.path.join(tdir, "pb_paint.vmat"), "w", newline="\n") as f: f.write(VMAT)
    png(os.path.join(tdir, "pb_paint_color.png"), 16, 16, (255, 255, 255))
    png(os.path.join(tdir, "pb_paint_rough.png"), 16, 16, (122, 122, 122))


if __name__ == "__main__":
    main()
