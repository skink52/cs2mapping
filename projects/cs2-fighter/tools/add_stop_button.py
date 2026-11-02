"""Adds a STOP CPUs host button to a Hammer-saved mg_cs2_fighter.vmap (keeps everything else).
It copies the REMOVE CPU button, its post and its label, one slot further along the row.
Usage: python3 add_stop_button.py <in.vmap> <out.vmap>"""
import copy, random, sys, uuid
import dmx9

SRC, OUT = sys.argv[1], sys.argv[2]
dm = dmx9.DMX.load(SRC)
world = dm.root["world"]

if any(e.type == "CMapEntity" and e["entity_properties"].get("targetname") == "pb_btn_stopcpu" for e in dm.elements):
    print("already has pb_btn_stopcpu"); dm.save(OUT); sys.exit(0)

next_id = [max([e.get("nodeID", 0) for e in dm.elements if "nodeID" in e] + [0]) + 1]


def clone(e, memo):
    if not isinstance(e, dmx9.Element): return e
    if id(e) in memo: return memo[id(e)]
    c = dmx9.Element(e.type, e.name)
    memo[id(e)] = c
    for k, (t, v) in e.attrs.items():
        if (t & ~dmx9.ARRAY) == dmx9.T_ELEMENT:
            v = [clone(x, memo) for x in v] if t >= dmx9.ARRAY else clone(v, memo)
        else:
            v = copy.copy(v)
        c.attrs[k] = [t, v]
    if "nodeID" in c: c["nodeID"] = next_id[0]; next_id[0] += 1
    if "referenceID" in c: c["referenceID"] = random.getrandbits(63)
    return c


def parent_of(target):
    for e in dm.elements:
        kids = e.get("children")
        if isinstance(kids, list) and any(k is target for k in kids): return e
    return None


def near(e, x, y, tol=4):
    o = e.get("origin")
    return o is not None and abs(o[0] - x) < tol and abs(o[1] - y) < tol


btn = next(e for e in dm.elements if e.type == "CMapEntity" and e["entity_properties"].get("targetname") == "pb_btn_removecpu")
bx, by, bz = btn["origin"]
start = next(e for e in dm.elements if e.type == "CMapEntity" and e["entity_properties"].get("targetname") == "pb_btn_start")
step = start["origin"][1] - by            # next slot along the row, past START
dy = 2 * step
label = next((e for e in dm.elements if e.type == "CMapEntity" and e["entity_properties"].get("classname") == "point_worldtext"
              and (e["entity_properties"].get("message") or "") == "REMOVE CPU"), None)
# the post under the button: a world mesh standing at the same x, y
post = None
for e in dm.elements:
    if e.type != "CMapMesh" or e is btn["children"][0]: continue
    md = e["meshData"]; o = e["origin"]
    pos = {s.name: s["data"] for s in md["vertexData"]["streams"]}["position:0"]
    xs = [v[0] + o[0] for v in pos]; ys = [v[1] + o[1] for v in pos]
    if max(xs) - min(xs) < 8 and abs((max(xs) + min(xs)) / 2 - bx) < 1 and abs((max(ys) + min(ys)) / 2 - by) < 1:
        post = e; break

for src in [x for x in (btn, label, post) if x is not None]:
    memo = {}
    c = clone(src, memo)
    for el in memo.values():
        if "origin" in el and el.type in ("CMapEntity", "CMapMesh"):
            o = el["origin"]; el["origin"] = (o[0], o[1] + dy, o[2])
    if src is btn:
        c["entity_properties"]["targetname"] = "pb_btn_stopcpu"
        for conn in c["connectionsData"]: conn["overrideParam"] = "StopCPU"
    if src is label:
        c["entity_properties"]["message"] = "STOP CPUs"
    par = parent_of(src) or world
    par["children"].append(c)

dm.save(OUT)
print(f"STOP CPUs button added at ({bx:.0f}, {by + dy:.0f}, {bz:.0f}); label {'yes' if label else 'no'}, post {'yes' if post else 'no'}")
