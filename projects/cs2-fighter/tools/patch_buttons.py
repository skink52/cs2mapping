"""Makes the host buttons in a Hammer-saved mg_cs2_fighter.vmap bigger and quicker to re-press.
Usage: python3 patch_buttons.py <in.vmap> <out.vmap> [scale] [wait]"""
import sys
import dmx9

SRC, OUT = sys.argv[1], sys.argv[2]
SCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 1.6
WAIT = sys.argv[4] if len(sys.argv) > 4 else "0.4"
dm = dmx9.DMX.load(SRC)
n = 0
for e in dm.elements:
    if e.type != "CMapEntity": continue
    p = e["entity_properties"]
    if p.get("classname") != "func_button" or not (p.get("targetname") or "").startswith("pb_btn_"): continue
    p["wait"] = WAIT
    for mesh in e.get("children") or []:
        if mesh.type != "CMapMesh": continue
        for st in mesh["meshData"]["vertexData"]["streams"]:
            if st.name == "position:0":
                st["data"] = [tuple(c * SCALE for c in v) for v in st["data"]]
    n += 1
dm.save(OUT)
print(f"{n} buttons: {SCALE}x bigger, wait {WAIT}s")
