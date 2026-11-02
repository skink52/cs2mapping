"""Applies the second-round fixes to a Hammer-saved mg_cs2_fighter.vmap, keeping the user's edits.
Usage: python3 patch_map.py <in.vmap> <out.vmap>

- neon signs: the sign models are now built facing the right way with the art the right way up,
  so signs the user turned to fix them (yaw -90, roll 180) are turned back to an upright pose
  that puts them in the same place, facing the same way.
- side-wing shutters and windows were sunk into the wing walls (z-fighting): moved out flush.
- coloured spot lights and neon glows dimmed.
- cubemap fog reads the night sky material directly.
"""
import math, sys
import dmx9

SRC, OUT = sys.argv[1], sys.argv[2]
SIGN_H = {"kakutou": 120, "ningyou": 140, "ramen": 150, "yoichi": 110, "ryu": 70, "eigyou": 34, "marquee": 96, "sake": 60}
# lumens -> dimming factor, by the light's role in make_map.py
DIM = {14000: 0.7, 6000: 0.45, 4500: 0.45, 1400: 0.6, 1600: 0.75}

dm = dmx9.DMX.load(SRC)
report = []


def wrap(a):
    a = math.fmod(a, 360.0)
    return a + 360.0 if a < 0 else a


for e in dm.elements:
    if e.type == "CMapEntity":
        p = e["entity_properties"]
        cls = p.get("classname")
        model = p.get("model") or ""
        if cls == "prop_static" and "pb_sign_" in model:
            key = model.split("pb_sign_")[1].split(".")[0]
            pitch, yaw, roll = e["angles"]
            if abs(abs(roll) - 180) < 1 and abs(pitch) < 1:
                ox, oy, oz = e["origin"]
                e["angles"] = (0.0, wrap(yaw + 90), 0.0)
                e["origin"] = (ox, oy, oz - SIGN_H[key])
                report.append(f"sign {key}: turned upright at ({ox:.0f}, {oy:.0f}, {oz - SIGN_H[key]:.0f}) yaw {wrap(yaw + 90):.0f}")
            elif abs(roll) > 1 or abs(pitch) > 1:
                report.append(f"sign {key}: left alone (angles {pitch:.0f} {yaw:.0f} {roll:.0f})")
        elif cls == "light_omni2":
            lum = int(float(p.get("brightness_lumens") or 0))
            f = DIM.get(lum)
            if f:
                p["brightness_lumens"] = str(int(lum * f))
                for k in ("brightness", "brightness_legacy"):
                    if p.get(k): p[k] = "%.4f" % (float(p[k]) * f)
                report.append(f"light {lum} lm -> {int(lum * f)} lm")
        elif cls == "env_cubemap_fog":
            p["cubemapfogsource"] = "2"
            p["cubemapfogskymaterial"] = "materials/skybox/sky_rain_night_01.vmat"
            report.append("fog: reads materials/skybox/sky_rain_night_01.vmat")
    elif e.type == "CMapMesh":
        md = e["meshData"]; o = e["origin"]
        pos = {s.name: s["data"] for s in md["vertexData"]["streams"]}["position:0"]
        xs = [v[0] + o[0] for v in pos]
        x0, x1 = min(xs), max(xs)
        if x1 - x0 < 3.5 and 558 < abs((x0 + x1) / 2) < 565:
            # thin panel sunk into a wing wall at x = +-560: move it out so it sits on the wall face
            wall = 560.0 if x0 > 0 else -560.0
            shift = (wall - x1) if x0 > 0 else (wall - x0)
            e["origin"] = (o[0] + shift, o[1], o[2])
            report.append(f"wing panel at x {x0:.1f}..{x1:.1f} moved {shift:+.1f}")

dm.save(OUT)
print("\n".join(report))
print("saved", OUT)
