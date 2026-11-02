"""Render exported rig animations from the SMD files (side, front and 3/4 views) for checking.

The SMDs are parsed back with the Source convention R = Rz*Ry*Rx, so this also checks the
export round trip. The 2D game skeleton (hit boxes) is drawn over the side view in red.
Usage: python3 rig_preview.py <rig_dir> <preview.json> <out.png> clip:frame [clip:frame ...]
"""
import json, math, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

rig_dir, pv_path, out_path = sys.argv[1:4]
picks = sys.argv[4:]
pv = json.load(open(pv_path))


def rot(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def read_smd(path):
    nodes, frames, cur, mode = [], {}, None, None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] in ("nodes", "skeleton", "triangles"): mode = t[0]; continue
        if t[0] == "end": mode = None; continue
        if mode == "nodes": nodes.append((t[1].strip('"'), int(t[2])))
        elif mode == "skeleton":
            if t[0] == "time": cur = int(t[1]); frames[cur] = {}
            else: frames[cur][int(t[0])] = [float(v) for v in t[1:7]]
    return nodes, frames


def fk(nodes, fr):
    W = []
    for i, (n, p) in enumerate(nodes):
        x, y, z, rx, ry, rz = fr[i]
        R = rot(rx, ry, rz); t = np.array([x, y, z])
        if p < 0: W.append((R, t))
        else:
            PR, PP = W[p]; W.append((PR @ R, PP + PR @ t))
    return W


CELL = 300
font = ImageFont.load_default()
img = Image.new("RGB", (CELL * 3, CELL * len(picks)), (24, 20, 28))
d = ImageDraw.Draw(img)
U = 0.72
names2d = [("P", "N"), ("N", "H"), ("S", "fE"), ("fE", "fW"), ("fW", "fF"), ("S", "bE"), ("bE", "bW"), ("bW", "bF"),
           ("P", "fK"), ("fK", "fA"), ("fA", "fT"), ("P", "bK"), ("bK", "bA"), ("bA", "bT")]
for row, pick in enumerate(picks):
    clip, frame = pick.split(":"); frame = int(frame)
    nodes, frames = read_smd(os.path.join(rig_dir, "anims", clip + ".smd"))
    frame = min(frame, max(frames))
    W = fk(nodes, frames[frame])
    pos = np.array([p for _, p in W])
    J = pv["clips"][clip][frame]["J"]
    # round-trip check vs the exporter's own world positions
    ref = np.array(pv["clips"][clip][frame]["W"])
    err = float(np.abs(ref - pos).max())
    views = [("side", lambda p: (p[0], p[2])), ("front", lambda p: (-p[1], p[2])),
             ("3/4", lambda p: (p[0] * 0.7 - p[1] * 0.7, p[2] + (p[0] * 0.7 + p[1] * 0.7) * 0.25))]
    for col, (vn, proj) in enumerate(views):
        ox, oy = col * CELL + CELL / 2, row * CELL + CELL - 30
        s = 3.0
        P = lambda p: (ox + proj(p)[0] * s, oy - proj(p)[1] * s)
        d.line([(col * CELL + 10, oy), (col * CELL + CELL - 10, oy)], fill=(80, 70, 60))
        for i, (n, par) in enumerate(nodes):
            if par < 0 or n.startswith("root"): continue
            left = n.endswith("_L") or "_L_" in n
            right = n.endswith("_R") or "_R_" in n
            colr = (90, 200, 255) if left else (255, 170, 70) if right else (235, 235, 235)
            d.line([P(pos[par]), P(pos[i])], fill=colr, width=2)
        if vn == "side":
            for a, b in names2d:
                pa = (J[a]["x"] * U, 0, J[a]["y"] * U); pb = (J[b]["x"] * U, 0, J[b]["y"] * U)
                d.line([P(pa), P(pb)], fill=(255, 60, 60), width=1)
            for k in ("fF", "bF", "fT", "bT"):
                c = P((J[k]["x"] * U, 0, J[k]["y"] * U)); d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], outline=(255, 60, 60))
        d.text((col * CELL + 8, row * CELL + 6), f"{clip}:{frame} {vn}" + (f"  rt err {err:.3f}" if col == 0 else ""), fill=(255, 220, 120), font=font)
img.save(out_path)
print("saved", out_path)
