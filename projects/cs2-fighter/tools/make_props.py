"""Original props and materials for the Puppet Brawl neon street stage.

Writes SMD meshes, ModelDoc .vmdl files, .vmat materials and PNG textures:
  models/puppet_brawl/pb_ball.vmdl            glowing sphere (projectiles, hit sparks)
  models/puppet_brawl/props/pb_sign_*.vmdl    neon signs (box panel, sign art on the front)
  models/puppet_brawl/props/pb_neon_*.vmdl    1x1x1 neon tube, scaled per placement in the map
  models/puppet_brawl/props/pb_lantern.vmdl   red paper lantern
  models/puppet_brawl/props/pb_padring.vmdl   glowing control-pad ring
Sign lettering is rendered with Noto Sans CJK (SIL Open Font License).
Usage: python3 make_props.py <addon_dir>
"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/addon"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_JP = 0  # face index: JP


def norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)


class Mesh:
    """Triangle soup with per-triangle material, written as a one-bone SMD."""
    def __init__(self):
        self.tris = []

    def tri(self, mat, a, b, c):
        self.tris.append((mat, a, b, c))

    def quad(self, mat, p, n, uvs):
        # p: 4 corners counter-clockwise seen from outside, n: normal, uvs: 4 uv pairs
        v = [(p[i], n, uvs[i]) for i in range(4)]
        self.tri(mat, v[0], v[1], v[2]); self.tri(mat, v[0], v[2], v[3])

    def smd(self):
        out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
        # ModelDoc turns SMDs 90 degrees about Z and reads v from the bottom of the texture, so
        # positions are written turned -90 degrees and v flipped, to come out as built here.
        fix = lambda v: (v[1], -v[0], v[2])
        for mat, *vs in self.tris:
            out.append(mat)
            for (p, n, uv) in vs:
                out.append("0 %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (*fix(p), *fix(n), uv[0], 1 - uv[1]))
        out.append("end")
        return "\n".join(out) + "\n"


def box(m, x0, x1, y0, y1, z0, z1, mats):
    """Axis box. mats: dict face->material for 'px','nx','py','ny','pz','nz' (missing = 'default').
    UVs map each face 0..1 (the front sign face reads correctly from outside)."""
    g = lambda k: mats.get(k, mats.get("default"))
    # -Y face (the "front": faces the audience when the sign looks down -Y)
    m.quad(g("ny"), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0), [(0, 1), (1, 1), (1, 0), (0, 0)])
    m.quad(g("py"), [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (0, 1, 0), [(0, 1), (1, 1), (1, 0), (0, 0)])
    m.quad(g("px"), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0), [(0, 1), (1, 1), (1, 0), (0, 0)])
    m.quad(g("nx"), [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (-1, 0, 0), [(0, 1), (1, 1), (1, 0), (0, 0)])
    m.quad(g("pz"), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1), [(0, 1), (1, 1), (1, 0), (0, 0)])
    m.quad(g("nz"), [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], (0, 0, -1), [(0, 1), (1, 1), (1, 0), (0, 0)])


def lathe(m, mat, profile, seg=20, v0=0.0, v1=1.0):
    """profile: list of (radius, z) bottom to top. Surface of revolution around Z."""
    for k in range(len(profile) - 1):
        (r0, z0), (r1, z1) = profile[k], profile[k + 1]
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            p = [(r0 * math.cos(a0), r0 * math.sin(a0), z0), (r0 * math.cos(a1), r0 * math.sin(a1), z0),
                 (r1 * math.cos(a1), r1 * math.sin(a1), z1), (r1 * math.cos(a0), r1 * math.sin(a0), z1)]
            dz, dr = z1 - z0, r1 - r0
            ns = [norm((math.cos(a) * dz, math.sin(a) * dz, -dr)) for a in (a0, a1, a1, a0)]
            vv0 = v0 + (v1 - v0) * k / (len(profile) - 1); vv1 = v0 + (v1 - v0) * (k + 1) / (len(profile) - 1)
            uv = [(i / seg, 1 - vv0), ((i + 1) / seg, 1 - vv0), ((i + 1) / seg, 1 - vv1), (i / seg, 1 - vv1)]
            if r0 < 1e-6:
                m.tri(mat, (p[0], ns[0], uv[0]), (p[2], ns[2], uv[2]), (p[3], ns[3], uv[3]))
            elif r1 < 1e-6:
                m.tri(mat, (p[0], ns[0], uv[0]), (p[1], ns[1], uv[1]), (p[2], ns[2], uv[2]))
            else:
                m.tri(mat, (p[0], ns[0], uv[0]), (p[1], ns[1], uv[1]), (p[2], ns[2], uv[2]))
                m.tri(mat, (p[0], ns[0], uv[0]), (p[2], ns[2], uv[2]), (p[3], ns[3], uv[3]))


def sphere(m, mat, r, seg=18, rings=12):
    prof = [(r * math.sin(math.pi * k / rings), -r * math.cos(math.pi * k / rings)) for k in range(rings + 1)]
    lathe(m, mat, prof, seg)


# ------------------------------------------------------------------ materials
def vmat_emissive(color_png, illum_png, brightness=3.0, tint=(1, 1, 1), note=""):
    return f"""// Puppet Brawl {note}
Layer0
{{
	shader "csgo_vertexlitgeneric.vfx"
	F_SELF_ILLUM 1

	TextureColor "{color_png}"
	g_flModelTintAmount "1.000"
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"

	TextureSelfIllumMask "{illum_png}"
	g_flSelfIllumBrightness "{brightness:.3f}"
	g_flSelfIllumScale "1.000"
	g_flSelfIllumAlbedoFactor "1.000"
	g_vSelfIllumTint "[{tint[0]:.6f} {tint[1]:.6f} {tint[2]:.6f} 0.000000]"

	TextureNormal "materials/default/default_normal.tga"
	TextureRoughness "materials/default/default_rough.tga"
}}
"""


def vmat_plain(color_png, note=""):
	return f"""// Puppet Brawl {note}
Layer0
{{
	shader "csgo_vertexlitgeneric.vfx"
	TextureColor "{color_png}"
	g_flModelTintAmount "1.000"
	TextureNormal "materials/default/default_normal.tga"
	TextureRoughness "materials/default/default_rough.tga"
}}
"""


def vmdl(name, smd, remaps):
    rm = "".join(f"""
								{{
									from = "{a}.vmat"
									to = "{b}"
								}},""" for a, b in remaps)
    return f"""<!-- kv3 encoding:text:version{{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d}} format:modeldoc41:version{{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0}} -->
{{
	rootNode =
	{{
		_class = "RootNode"
		children =
		[
			{{
				_class = "MaterialGroupList"
				children =
				[
					{{
						_class = "DefaultMaterialGroup"
						remaps =
						[{rm}
						]
						use_global_default = false
						global_default_material = ""
					}},
				]
			}},
			{{
				_class = "RenderMeshList"
				children =
				[
					{{
						_class = "RenderMeshFile"
						name = "{name}"
						filename = "{smd}"
						import_scale = 1.0
						import_filter =
						{{
							exclude_by_default = false
							exception_list = [  ]
						}}
					}},
				]
			}},
		]
		model_archetype = ""
		primary_associated_entity = ""
		document_sub_type = "ModelDocSubType_None"
	}}
}}
"""


# ------------------------------------------------------------------ textures
def solid(path, size, rgb):
    Image.new("RGB", size, rgb).save(path)


def neon_text_image(lines, w, h, color, vertical=False, frame=True, sub=None, sub_color=None, bg=(10, 6, 16)):
    """Glowing neon lettering on a dark board. Returns (color image, illum mask)."""
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    core = Image.new("RGB", (w, h), (0, 0, 0))
    dg, dc = ImageDraw.Draw(glow), ImageDraw.Draw(core)
    pad = int(min(w, h) * 0.08)
    if frame:
        for d, img, width in ((dg, glow, max(6, w // 40)), (dc, core, max(3, w // 90))):
            d.rounded_rectangle([pad // 2, pad // 2, w - pad // 2, h - pad // 2], radius=pad, outline=color, width=width)
    if vertical:
        chars = list(lines[0])
        n = len(chars)
        cell = min((h - 2 * pad) / n, w - 2 * pad)
        font = ImageFont.truetype(FONT, int(cell * 0.86), index=FONT_JP)
        for i, ch in enumerate(chars):
            cy = pad + cell * (i + 0.5) + ((h - 2 * pad) - cell * n) / 2
            for d in (dg, dc):
                d.text((w / 2, cy), ch, font=font, fill=color, anchor="mm")
    else:
        rows = len(lines) + (1 if sub else 0)
        size = int((h - 2 * pad) / rows * 0.8)
        font = ImageFont.truetype(FONT, size, index=FONT_JP)
        # shrink to fit the width
        while max(font.getlength(t) for t in lines) > w - 2.5 * pad and size > 10:
            size -= 4; font = ImageFont.truetype(FONT, size, index=FONT_JP)
        y = pad + (h - 2 * pad) / rows * 0.5
        for t in lines:
            for d in (dg, dc): d.text((w / 2, y), t, font=font, fill=color, anchor="mm")
            y += (h - 2 * pad) / rows
        if sub:
            sf = ImageFont.truetype(FONT, int(size * 0.55), index=FONT_JP)
            for d in (dg, dc): d.text((w / 2, y), sub, font=sf, fill=sub_color or color, anchor="mm")
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(4, w // 60)))
    # white-hot core lines over the coloured glow
    hot = core.point(lambda v: min(255, int(v * 0.55 + 140)) if v > 40 else 0)
    color_img = Image.new("RGB", (w, h), bg)
    color_img = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), color_img, Image.new("L", (w, h), 0))
    from PIL import ImageChops
    color_img = ImageChops.add(color_img, glow)
    color_img = ImageChops.lighter(color_img, ImageChops.multiply(core, Image.new("RGB", (w, h), (255, 255, 255))))
    color_img = ImageChops.lighter(color_img, Image.merge("RGB", [hot.convert("L")] * 3).point(lambda v: v // 3))
    mask = ImageChops.lighter(glow.convert("L"), core.convert("L")).point(lambda v: min(255, int(v * 1.6)))
    return color_img, mask


SIGNS = [
    # name, lines, size (w x h units), texture px, colour, vertical, sub
    ("kakutou", ["格闘"], (40, 120), (256, 768), (255, 50, 120), True, None),
    ("ningyou", ["人形劇"], (36, 140), (256, 1024), (60, 230, 255), True, None),
    ("ramen", ["ラーメン"], (34, 150), (256, 1024), (255, 210, 40), True, None),
    ("yoichi", ["夜市"], (44, 110), (256, 640), (190, 90, 255), True, None),
    ("ryu", ["龍"], (70, 70), (512, 512), (255, 70, 40), False, None),
    ("eigyou", ["営業中"], (90, 34), (768, 288), (90, 255, 140), False, None),
    ("marquee", ["PUPPET BRAWL"], (420, 96), (2048, 468), (255, 60, 170), False, "パペット・ブロール  ·  人形格闘"),
    ("sake", ["酒"], (30, 60), (256, 512), (255, 140, 60), True, None),
]
NEON = {"pink": (255, 60, 170), "cyan": (40, 230, 255), "purple": (170, 80, 255), "yellow": (255, 210, 60), "red": (255, 50, 50), "green": (80, 255, 140)}


def main():
    mdir = os.path.join(OUT, "models", "puppet_brawl"); pdir = os.path.join(mdir, "props")
    mat = os.path.join(OUT, "materials", "puppet_brawl"); pmat = os.path.join(mat, "props")
    for d in (mdir, pdir, mat, pmat): os.makedirs(d, exist_ok=True)
    rel = lambda *p: "/".join(p)
    made = []

    # dark trim + gold used by several props
    solid(os.path.join(pmat, "pb_dark_color.png"), (16, 16), (24, 20, 28))
    open(os.path.join(pmat, "pb_dark.vmat"), "w").write(vmat_plain("materials/puppet_brawl/props/pb_dark_color.png", "dark sign casing"))
    solid(os.path.join(pmat, "pb_gold_color.png"), (16, 16), (196, 150, 60))
    open(os.path.join(pmat, "pb_gold.vmat"), "w").write(vmat_plain("materials/puppet_brawl/props/pb_gold_color.png", "lantern caps"))

    # glowing ball (white, tinted by the script with SetColor)
    solid(os.path.join(mat, "pb_glow_color.png"), (16, 16), (255, 255, 255))
    solid(os.path.join(mat, "pb_glow_illum.png"), (16, 16), (255, 255, 255))
    open(os.path.join(mat, "pb_glow.vmat"), "w").write(vmat_emissive("materials/puppet_brawl/pb_glow_color.png", "materials/puppet_brawl/pb_glow_illum.png", 2.0, note="glowing ball, tinted per use"))
    m = Mesh(); sphere(m, "pb_glow", 8.0)
    open(os.path.join(mdir, "pb_ball.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_ball.vmdl"), "w").write(vmdl("pb_ball", "models/puppet_brawl/pb_ball.smd", [("pb_glow", "materials/puppet_brawl/pb_glow.vmat")]))
    made.append("pb_ball")

    # neon signs
    for name, lines, (w, h), (tw, th), color, vertical, sub in SIGNS:
        img, mask = neon_text_image(lines, tw, th, color, vertical=vertical, sub=sub, sub_color=(60, 230, 255))
        img.save(os.path.join(pmat, f"sign_{name}_color.png")); mask.save(os.path.join(pmat, f"sign_{name}_illum.png"))
        mname = f"pb_sign_{name}"
        open(os.path.join(pmat, mname + ".vmat"), "w").write(vmat_emissive(f"materials/puppet_brawl/props/sign_{name}_color.png", f"materials/puppet_brawl/props/sign_{name}_illum.png", 2.5, note=f"neon sign '{lines[0]}'"))
        m = Mesh()
        d = 5.0
        # panel centred on x, bottom at z=0, front face on -Y (y = -d/2)
        box(m, -w / 2, w / 2, -d / 2, d / 2, 0, h, {"ny": mname, "default": "pb_dark"})
        open(os.path.join(pdir, mname + ".smd"), "w").write(m.smd())
        open(os.path.join(pdir, mname + ".vmdl"), "w").write(vmdl(mname, f"models/puppet_brawl/props/{mname}.smd",
             [(mname, f"materials/puppet_brawl/props/{mname}.vmat"), ("pb_dark", "materials/puppet_brawl/props/pb_dark.vmat")]))
        made.append(mname)

    # neon tubes: unit box centred on the origin, scaled in the map
    for cname, rgb in NEON.items():
        mname = f"pb_neon_{cname}"
        hot = tuple(min(255, int(c * 0.6 + 110)) for c in rgb)
        solid(os.path.join(pmat, mname + "_color.png"), (16, 16), hot)
        solid(os.path.join(pmat, mname + "_illum.png"), (16, 16), (255, 255, 255))
        open(os.path.join(pmat, mname + ".vmat"), "w").write(vmat_emissive(f"materials/puppet_brawl/props/{mname}_color.png", f"materials/puppet_brawl/props/{mname}_illum.png", 3.0, tuple(c / 255 for c in rgb), note=f"{cname} neon tube"))
        m = Mesh(); box(m, -0.5, 0.5, -0.5, 0.5, -0.5, 0.5, {"default": mname})
        open(os.path.join(pdir, mname + ".smd"), "w").write(m.smd())
        open(os.path.join(pdir, mname + ".vmdl"), "w").write(vmdl(mname, f"models/puppet_brawl/props/{mname}.smd", [(mname, f"materials/puppet_brawl/props/{mname}.vmat")]))
        made.append(mname)

    # paper lantern: ribbed red glow with gold caps, hangs from z=0 downwards
    lt = Image.new("RGB", (128, 256), (230, 40, 30)); dl = ImageDraw.Draw(lt)
    for i in range(1, 12): dl.line([(0, i * 256 // 12), (128, i * 256 // 12)], fill=(120, 10, 10), width=3)
    font = ImageFont.truetype(FONT, 90, index=FONT_JP)
    dl.text((64, 128), "祭", font=font, fill=(30, 6, 6), anchor="mm")
    lt.save(os.path.join(pmat, "pb_lantern_color.png"))
    lm = lt.convert("L").point(lambda v: 255 if v > 60 else 90); lm.save(os.path.join(pmat, "pb_lantern_illum.png"))
    open(os.path.join(pmat, "pb_lantern.vmat"), "w").write(vmat_emissive("materials/puppet_brawl/props/pb_lantern_color.png", "materials/puppet_brawl/props/pb_lantern_illum.png", 2.5, (1, 0.55, 0.4), note="paper lantern"))
    m = Mesh()
    body = [(0.0, -27.0)] + [(9.5 * math.sin(math.pi * (0.12 + 0.76 * k / 10)), -25.0 + 20.0 * k / 10) for k in range(11)] + [(0.0, -3.0)]
    lathe(m, "pb_lantern", body[1:-1], seg=18)
    lathe(m, "pb_gold", [(0.0, -29.0), (4.2, -29.0), (4.2, -24.5), (3.0, -24.0)], seg=14)
    lathe(m, "pb_gold", [(3.0, -4.0), (4.2, -3.5), (4.2, 0.0), (0.0, 0.0)], seg=14)
    open(os.path.join(pdir, "pb_lantern.smd"), "w").write(m.smd())
    open(os.path.join(pdir, "pb_lantern.vmdl"), "w").write(vmdl("pb_lantern", "models/puppet_brawl/props/pb_lantern.smd",
         [("pb_lantern", "materials/puppet_brawl/props/pb_lantern.vmat"), ("pb_gold", "materials/puppet_brawl/props/pb_gold.vmat")]))
    made.append("pb_lantern")

    # control pad ring (flat annulus 1 unit tall)
    for cname in ("pink", "cyan"):
        mname = f"pb_padring_{cname}"
        m = Mesh(); seg = 32; r0, r1 = 34.0, 44.0
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            top = [(r0 * c0, r0 * s0, 1), (r1 * c0, r1 * s0, 1), (r1 * c1, r1 * s1, 1), (r0 * c1, r0 * s1, 1)]
            m.quad(f"pb_neon_{cname}", top, (0, 0, 1), [(0, 0), (1, 0), (1, 1), (0, 1)])
            out = [(r1 * c0, r1 * s0, 0), (r1 * c1, r1 * s1, 0), (r1 * c1, r1 * s1, 1), (r1 * c0, r1 * s0, 1)]
            m.quad(f"pb_neon_{cname}", out, norm((c0 + c1, s0 + s1, 0)), [(0, 0), (1, 0), (1, 1), (0, 1)])
        open(os.path.join(pdir, mname + ".smd"), "w").write(m.smd())
        open(os.path.join(pdir, mname + ".vmdl"), "w").write(vmdl(mname, f"models/puppet_brawl/props/{mname}.smd", [(f"pb_neon_{cname}", f"materials/puppet_brawl/props/pb_neon_{cname}.vmat")]))
        made.append(mname)
    # ---------------------------------------------------------------- effects and projectiles
    # effects use an additive, unlit material: they glow over the scene and fade as the script darkens them
    ring_tex = Image.new("RGB", (64, 8))
    for x in range(64):
        k = max(0.0, 1 - abs(x - 31.5) / 32) ** 1.6; v = int(255 * k)
        for y in range(8): ring_tex.putpixel((x, y), (v, v, v))
    ring_tex.save(os.path.join(mat, "pb_fx_ring_color.png"))
    star_tex = Image.new("RGB", (64, 64))
    for x in range(64):
        for y in range(64):
            k = max(0.0, 1 - math.hypot(x - 31.5, y - 31.5) / 40) ** 1.3; v = int(255 * min(1, 0.25 + k))
            star_tex.putpixel((x, y), (v, v, v))
    star_tex.save(os.path.join(mat, "pb_fx_star_color.png"))
    for name, tex in (("pb_fx_ring", "pb_fx_ring_color.png"), ("pb_fx_star", "pb_fx_star_color.png")):
        open(os.path.join(mat, name + ".vmat"), "w").write(f"""// Puppet Brawl effect: additive glow, tinted by the script
Layer0
{{
	shader "csgo_unlitgeneric.vfx"
	F_BLEND_MODE 4
	F_RENDER_BACKFACES 1
	F_UNLIT 1
	g_bFogEnabled 0

	TextureColor "materials/puppet_brawl/{tex}"
	g_flModelTintAmount "1.000"
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
}}
""")
    two = lambda m, mat, p, n, uv: (m.quad(mat, p, n, uv), m.quad(mat, p[::-1], tuple(-c for c in n), uv[::-1]))
    # shockwave ring: flat annulus on the floor (radius 8, tinted by the script)
    m = Mesh(); seg = 40
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        q = [(6.4 * math.cos(a0), 6.4 * math.sin(a0), 0.2), (8 * math.cos(a0), 8 * math.sin(a0), 0.2), (8 * math.cos(a1), 8 * math.sin(a1), 0.2), (6.4 * math.cos(a1), 6.4 * math.sin(a1), 0.2)]
        two(m, "pb_glow", q, (0, 0, 1), [(0, 0), (1, 0), (1, 1), (0, 1)])
    open(os.path.join(mdir, "pb_fx_ring.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_fx_ring.vmdl"), "w").write(vmdl("pb_fx_ring", "models/puppet_brawl/pb_fx_ring.smd", [("pb_glow", "materials/puppet_brawl/pb_fx_ring.vmat")]))
    # hit flash: an 8-point star facing the audience (radius 8)
    m = Mesh()
    pts = 16
    for i in range(pts):
        a0, a1 = 2 * math.pi * i / pts, 2 * math.pi * (i + 1) / pts
        r0 = 8 if i % 2 == 0 else 2.6; r1 = 2.6 if i % 2 == 0 else 8
        p0 = (r0 * math.cos(a0), 0, r0 * math.sin(a0)); p1 = (r1 * math.cos(a1), 0, r1 * math.sin(a1))
        m.tri("pb_glow", ((0, 0, 0), (0, -1, 0), (0.5, 0.5)), (p0, (0, -1, 0), (0, 0)), (p1, (0, -1, 0), (0.5, 0)))
        m.tri("pb_glow", ((0, 0, 0), (0, 1, 0), (0.5, 0.5)), (p1, (0, 1, 0), (0.5, 0)), (p0, (0, 1, 0), (0, 0)))
    open(os.path.join(mdir, "pb_fx_burst.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_fx_burst.vmdl"), "w").write(vmdl("pb_fx_burst", "models/puppet_brawl/pb_fx_burst.smd", [("pb_glow", "materials/puppet_brawl/pb_fx_star.vmat")]))
    # trail orb: a soft glowing sphere (radius 8) for projectile trails
    m = Mesh(); sphere(m, "pb_glow", 8.0, seg=12, rings=8)
    open(os.path.join(mdir, "pb_fx_orb.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_fx_orb.vmdl"), "w").write(vmdl("pb_fx_orb", "models/puppet_brawl/pb_fx_orb.smd", [("pb_glow", "materials/puppet_brawl/pb_fx_star.vmat")]))
    made += ["pb_fx_ring", "pb_fx_burst", "pb_fx_orb"]

    # TIMBER's Knot Shot: a gnarled glowing wooden knot
    img = Image.new("RGB", (256, 128), (92, 54, 26)); d = ImageDraw.Draw(img)
    for k in range(18): d.line([(0, k * 7 + 3), (256, k * 7 + (k % 3) * 2)], fill=(64, 34, 14), width=3)
    msk = Image.new("L", (256, 128), 40); dm = ImageDraw.Draw(msk)
    for k in range(9):
        x = 14 + k * 28; d.line([(x, 0), (x + 10, 64), (x - 6, 128)], fill=(255, 150, 40), width=4); dm.line([(x, 0), (x + 10, 64), (x - 6, 128)], fill=255, width=5)
    img.save(os.path.join(pmat, "pb_proj_knot_color.png")); msk.save(os.path.join(pmat, "pb_proj_knot_illum.png"))
    open(os.path.join(pmat, "pb_proj_knot.vmat"), "w").write(vmat_emissive("materials/puppet_brawl/props/pb_proj_knot_color.png", "materials/puppet_brawl/props/pb_proj_knot_illum.png", 3.0, (1, 0.7, 0.4), note="Knot Shot"))
    m = Mesh(); rng = __import__("random").Random(7)
    rings, segs = 6, 8
    bump = [[1 + rng.uniform(-0.18, 0.22) for _ in range(segs)] for _ in range(rings + 1)]
    for ri in range(rings):
        for si in range(segs):
            def P(r_, s_):
                th = math.pi * r_ / rings; ph = 2 * math.pi * s_ / segs; k = 8 * bump[r_][s_ % segs]
                return (k * math.sin(th) * math.cos(ph), k * math.sin(th) * math.sin(ph), -k * math.cos(th))
            q = [P(ri, si), P(ri, si + 1), P(ri + 1, si + 1), P(ri + 1, si)]
            nrm = norm(tuple(sum(c) for c in zip(*q)))
            uv = [(si / segs, ri / rings), ((si + 1) / segs, ri / rings), ((si + 1) / segs, (ri + 1) / rings), (si / segs, (ri + 1) / rings)]
            m.quad("pb_proj_knot", q, nrm, uv)
    open(os.path.join(mdir, "pb_proj_knot.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_proj_knot.vmdl"), "w").write(vmdl("pb_proj_knot", "models/puppet_brawl/pb_proj_knot.smd", [("pb_proj_knot", "materials/puppet_brawl/props/pb_proj_knot.vmat")]))

    # BRASS's Cog Toss: a spinning brass gear, face to the audience (radius 8, thickness 3)
    solid(os.path.join(pmat, "pb_proj_cog_color.png"), (16, 16), (205, 150, 62))
    cm = Image.new("L", (16, 16), 70); cm.save(os.path.join(pmat, "pb_proj_cog_illum.png"))
    open(os.path.join(pmat, "pb_proj_cog.vmat"), "w").write(vmat_emissive("materials/puppet_brawl/props/pb_proj_cog_color.png", "materials/puppet_brawl/props/pb_proj_cog_illum.png", 2.0, (1, 0.8, 0.45), note="Cog Toss"))
    m = Mesh(); teeth = 10; n = teeth * 4; hole = 2.2; t = 1.5
    def rim(i):
        a = 2 * math.pi * i / n; r = 8 if (i % 4) in (1, 2) else 6.3
        return r * math.cos(a), r * math.sin(a)
    for i in range(n):
        (x0, z0), (x1, z1) = rim(i), rim(i + 1)
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        h0 = (hole * math.cos(a0), hole * math.sin(a0)); h1 = (hole * math.cos(a1), hole * math.sin(a1))
        for y, nn in ((-t, -1), (t, 1)):
            q = [(h0[0], y, h0[1]), (x0, y, z0), (x1, y, z1), (h1[0], y, h1[1])]
            if nn > 0: q = q[::-1]
            m.quad("pb_proj_cog", q, (0, nn, 0), [(0, 0), (1, 0), (1, 1), (0, 1)])
        side = [(x0, -t, z0), (x0, t, z0), (x1, t, z1), (x1, -t, z1)]
        m.quad("pb_proj_cog", side, norm((x0 + x1, 0, z0 + z1)), [(0, 0), (1, 0), (1, 1), (0, 1)])
    open(os.path.join(mdir, "pb_proj_cog.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_proj_cog.vmdl"), "w").write(vmdl("pb_proj_cog", "models/puppet_brawl/pb_proj_cog.smd", [("pb_proj_cog", "materials/puppet_brawl/props/pb_proj_cog.vmat")]))

    # MOTLEY's Juggle Ball: a harlequin-striped juggling ball
    img = Image.new("RGB", (256, 128)); d = ImageDraw.Draw(img)
    cols = [(255, 60, 90), (255, 220, 60), (60, 230, 255), (170, 90, 255)]
    for k in range(8): d.rectangle([k * 32, 0, k * 32 + 32, 128], fill=cols[k % 4])
    d.rectangle([0, 58, 256, 70], fill=(20, 16, 24))
    img.save(os.path.join(pmat, "pb_proj_jball_color.png"))
    Image.new("L", (16, 16), 150).save(os.path.join(pmat, "pb_proj_jball_illum.png"))
    open(os.path.join(pmat, "pb_proj_jball.vmat"), "w").write(vmat_emissive("materials/puppet_brawl/props/pb_proj_jball_color.png", "materials/puppet_brawl/props/pb_proj_jball_illum.png", 2.5, note="Juggle Ball"))
    m = Mesh(); sphere(m, "pb_proj_jball", 8.0, seg=16, rings=10)
    open(os.path.join(mdir, "pb_proj_jball.smd"), "w").write(m.smd())
    open(os.path.join(mdir, "pb_proj_jball.vmdl"), "w").write(vmdl("pb_proj_jball", "models/puppet_brawl/pb_proj_jball.smd", [("pb_proj_jball", "materials/puppet_brawl/props/pb_proj_jball.vmat")]))
    made += ["pb_proj_knot", "pb_proj_cog", "pb_proj_jball"]
    print(len(made), "models:", " ".join(made))


if __name__ == "__main__":
    main()
