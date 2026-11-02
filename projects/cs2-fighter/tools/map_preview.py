"""Flat-shaded preview of a generated vmap's meshes and props from a few cameras.
Usage: python3 map_preview.py <map.vmap> <out.png>"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import dmx9

dm = dmx9.DMX.load(sys.argv[1])
world = dm.root["world"]
COL = {"concrete_slabs": (70, 72, 80), "inferno_wood": (150, 100, 60), "paint_red": (170, 40, 35), "brick_clean": (130, 70, 55), "brick_ext": (115, 80, 70),
       "floor_001_dark": (45, 45, 52), "floor_05": (95, 95, 100), "corrugated": (60, 90, 140), "selfillum": (255, 230, 160), "toolsskybox": None,
       "toolsplayerclip": None, "glassblock": (120, 255, 200)}
def color(mat):
    for k, c in COL.items():
        if k in mat: return c
    return (200, 0, 200)

polys = []
def walk(e):
    for c in e.get("children", []) or []:
        if c.type == "CMapMesh":
            md = c["meshData"]; o = np.array(c["origin"])
            pos = {s.name: s["data"] for s in md["vertexData"]["streams"]}["position:0"]
            fd = {s.name: s["data"] for s in md["faceData"]["streams"]}
            ev, eo, en = md["edgeVertexIndices"], md["edgeOppositeIndices"], md["edgeNextIndices"]
            for f, e0 in enumerate(md["faceEdgeIndices"]):
                mat = md["materials"][fd["materialindex:0"][f]]
                col = color(mat)
                if col is None: continue
                loop, h = [], e0
                while True:
                    loop.append(np.array(pos[ev[h]]) + o); h = en[h]
                    if h == e0: break
                polys.append((loop, col))
        if c.type == "CMapEntity":
            cls = c["entity_properties"]["classname"]
            o = np.array(c["origin"])
            if cls == "prop_static":
                m = c["entity_properties"]["model"]; sc = np.array(c["scales"])
                if "pb_neon" in m:
                    half = sc / 2; col = (255, 80, 200) if "pink" in m else (60, 230, 255) if "cyan" in m else (180, 90, 255) if "purple" in m else (255, 220, 60)
                    x0, y0, z0 = o - half; x1, y1, z1 = o + half
                    polys.append(([np.array(p) for p in [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)]], col))
                elif "pb_sign" in m:
                    size = {"marquee": (420, 96), "kakutou": (40, 120), "ningyou": (36, 140), "ramen": (34, 150), "yoichi": (44, 110), "ryu": (70, 70), "eigyou": (90, 34), "sake": (30, 60)}
                    k = m.split("pb_sign_")[1].split(".")[0]; w, h = size[k]
                    yaw = math.radians(c["angles"][1]); ux, uy = math.cos(yaw), math.sin(yaw)
                    q = [o + np.array([-w / 2 * ux, -w / 2 * uy, h]), o + np.array([w / 2 * ux, w / 2 * uy, h]), o + np.array([w / 2 * ux, w / 2 * uy, 0]), o + np.array([-w / 2 * ux, -w / 2 * uy, 0])]
                    polys.append((q, (255, 60, 170)))
                elif "lantern" in m:
                    polys.append(([o + np.array(d) for d in [(-9, 0, -3), (9, 0, -3), (9, 0, -27), (-9, 0, -27)]], (255, 70, 40)))
                elif "padring" in m:
                    polys.append(([o + np.array(d) for d in [(-44, -44, 1), (44, -44, 1), (44, 44, 1), (-44, 44, 1)]], (255, 90, 200)))
        walk(c)
walk(world)

def render(cam, look, fov=90, W=640, H=360, title=""):
    img = Image.new("RGB", (W, H), (12, 10, 24)); d = ImageDraw.Draw(img)
    cam, look = np.array(cam, float), np.array(look, float)
    f = look - cam; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1]); r /= np.linalg.norm(r); u = np.cross(r, f)
    k = (W / 2) / math.tan(math.radians(fov) / 2)
    items = []
    for loop, col in polys:
        P = []
        ok = True
        for p in loop:
            v = p - cam; z = v @ f
            if z < 1: ok = False; break
            P.append((W / 2 + (v @ r) * k / z, H / 2 - (v @ u) * k / z))
        if not ok: continue
        cen = sum(loop) / len(loop)
        n = np.cross(loop[1] - loop[0], loop[2] - loop[0]); nl = np.linalg.norm(n)
        shade = 0.55 + 0.45 * abs((n / nl) @ np.array([0.3, -0.5, 0.8])) if nl > 0 else 1
        items.append((np.linalg.norm(cen - cam), P, tuple(int(c * shade) for c in col)))
    for _, P, c in sorted(items, key=lambda t: -t[0]): d.polygon(P, fill=c, outline=(0, 0, 0))
    d.text((6, 6), title, fill=(255, 255, 255))
    return img

views = [
    render((0, -300, 80), (0, 0, 64), 106, title="fight camera (far)"),
    render((0, -170, 76), (0, 0, 60), 106, title="fight camera (near)"),
    render((-150, -700, 150), (0, 0, 60), 90, title="spectator on the bleachers"),
    render((0, -300, 2200), (0, -299, 0), 70, title="top down"),
]
sheet = Image.new("RGB", (1280, 720))
for i, v in enumerate(views): sheet.paste(v, ((i % 2) * 640, (i // 2) * 360))
sheet.save(sys.argv[2]); print("saved", sys.argv[2], len(polys), "polys")
