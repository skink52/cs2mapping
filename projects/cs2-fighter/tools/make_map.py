"""Builds maps/mg_cs2_fighter.vmap: the Puppet Brawl neon night-market stage.

Starts from the addon's template map (keeps its sky, lighting, light probes, post
processing, team intro/select and nav), removes the template's sample geometry and labels,
and adds the arena, props, lights and every entity the script needs.

Layout (units, +Z up). The fight line runs along X at y = 0 on a stage 24 units high; the
audience side (where the fight camera floats) is -Y.
  y  560 ... 200   shop buildings behind the stage, neon signs, torii gate, lanterns
  y  150 ... -90   the stage (fighters only; the duel queue waits at its back)
  y  -90 ... -430  open air for the fight camera (players are kept out by a barrier)
  y -440 ... -760  four bleacher rows and the pad platform (pads 1-4 at z 80)
  y -760 ...-1160  back street; spawns in the side lanes and back street
Usage: python3 make_map.py <template.vmap> <out.vmap>
"""
import copy, math, random, sys, uuid
import dmx9
from dmx9 import Element, T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_UINT64, ARRAY

SRC, OUT = sys.argv[1], sys.argv[2]
random.seed(20261014)
dm = dmx9.DMX.load(SRC)
root = dm.root
world = root["world"]
children = world["children"]

# ------------------------------------------------------------------ ids
def all_nodes(e, out):
    for c in e.get("children", []) or []:
        out.append(c); all_nodes(c, out)
    return out
nodes = all_nodes(world, [])
next_node = [max([n.get("nodeID", 0) for n in nodes] + [world["nodeID"]]) + 1]
def nid():
    next_node[0] += 1; return next_node[0]
def rid(): return random.getrandbits(63)

# ------------------------------------------------------------------ remove template samples
DROP = {"func_bomb_target", "func_buyzone", "point_worldtext"}
keep = []
probe_kept = False
for c in children:
    if c.type == "CMapMesh": continue                       # template sample geometry
    if c.type == "CMapEntity":
        cls = c["entity_properties"]["classname"]
        if cls in DROP: continue
        if cls in ("info_player_terrorist", "info_player_counterterrorist"): continue   # re-placed below
        if cls == "env_combined_light_probe_volume":
            if probe_kept: continue
            probe_kept = True
    keep.append(c)
children[:] = keep
root["visbility"]["nodes"] = []
root["visbility"]["hiddenFlags"] = []
root["nodeInstanceData"] = []

def find(cls):
    return [c for c in children if c.type == "CMapEntity" and c["entity_properties"]["classname"] == cls]

def setp(ent, **kv):
    ep = ent["entity_properties"]
    for k, v in kv.items():
        k = k.replace("__", ".")
        if k in ep: ep[k] = str(v)
        else: ep.set(k, T_STRING, str(v))

# ------------------------------------------------------------------ element builders
PROTO_ENT = find("info_map_parameters")[0]
def entity(cls, origin, angles=(0, 0, 0), props=None, scales=(1, 1, 1), kids=(), conns=()):
    e = Element("CMapEntity", "")
    e.set("nodeID", T_INT, nid()); e.set("referenceID", T_UINT64, rid())
    e.set("children", T_ELEMENT | ARRAY, list(kids))
    e.set("variableTargetKeys", T_STRING | ARRAY, []); e.set("variableNames", T_STRING | ARRAY, [])
    plug = Element("DmePlugList", "")
    plug.set("names", T_STRING | ARRAY, []); plug.set("dataTypes", T_INT | ARRAY, []); plug.set("plugTypes", T_INT | ARRAY, []); plug.set("descriptions", T_STRING | ARRAY, [])
    e.set("relayPlugData", T_ELEMENT, plug)
    cl = []
    for (out, target, inp, param, delay) in conns:
        c = Element("DmeConnectionData", "")
        c.set("outputName", T_STRING, out); c.set("targetType", T_INT, 7); c.set("targetName", T_STRING, target)
        c.set("inputName", T_STRING, inp); c.set("overrideParam", T_STRING, param); c.set("delay", T_FLOAT, float(delay)); c.set("timesToFire", T_INT, -1)
        cl.append(c)
    e.set("connectionsData", T_ELEMENT | ARRAY, cl)
    ep = Element("EditGameClassProps", "")
    ep.set("classname", T_STRING, cls)
    for k, v in (props or {}).items(): ep.set(k.replace("__", "."), T_STRING, str(v))
    e.set("entity_properties", T_ELEMENT, ep)
    e.set("hitNormal", T_VEC3, (0.0, 0.0, 1.0)); e.set("isProceduralEntity", T_BOOL, 0)
    e.set("origin", T_VEC3, tuple(float(v) for v in origin)); e.set("angles", T_QANGLE, tuple(float(v) for v in angles))
    e.set("scales", T_VEC3, tuple(float(v) for v in scales))
    e.set("transformLocked", T_BOOL, 0); e.set("force_hidden", T_BOOL, 0); e.set("editorOnly", T_BOOL, 0)
    return e

def stream(name, attr, sem, data, t, loc=0, flags=1):
    s = Element("CDmePolygonMeshDataStream", name)
    s.set("standardAttributeName", T_STRING, attr); s.set("semanticName", T_STRING, sem); s.set("semanticIndex", T_INT, 0)
    s.set("vertexBufferLocation", T_INT, loc); s.set("dataStateFlags", T_INT, flags); s.set("subdivisionBinding", T_ELEMENT, None)
    s.set("data", t | ARRAY, data)
    return s
def data_array(size, streams):
    a = Element("CDmePolygonMeshDataArray", "")
    a.set("size", T_INT, size); a.set("streams", T_ELEMENT | ARRAY, streams)
    return a

TEX = 512.0   # texture size assumed for UVs (Hammer re-derives them from the face axes when edited)
def axes_for(n):
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 2: return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
    if ax == 0: return (0.0, 1.0 if n[0] < 0 else -1.0, 0.0), (0.0, 0.0, -1.0)
    return (1.0 if n[1] > 0 else -1.0, 0.0, 0.0), (0.0, 0.0, -1.0)

def polymesh(verts, faces, mats, origin, scale=0.25):
    """verts: local positions; faces: [(vertex loop CCW from outside, material)]"""
    matlist = []
    for _, m in faces:
        if m not in matlist: matlist.append(m)
    he = {}            # (a,b) -> half-edge index
    ev, eo, en, ef, ed, evd = [], [], [], [], [], []
    def half(a, b):
        if (a, b) in he: return he[(a, b)]
        i = len(ev)
        ev.extend([b, a]); eo.extend([i + 1, i]); en.extend([-1, -1]); ef.extend([-1, -1]); ed.extend([i // 2, i // 2]); evd.extend([i, i + 1])
        he[(a, b)] = i; he[(b, a)] = i + 1
        return i
    face_edges = []
    for f, (loop, m) in enumerate(faces):
        hs = [half(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]
        for i, h in enumerate(hs):
            en[h] = hs[(i + 1) % len(hs)]; ef[h] = f
        face_edges.append(hs[0])
    assert all(x >= 0 for x in ef), "open mesh"
    vedge = [0] * len(verts)
    for (a, b), h in he.items():
        if ef[h] >= 0: vedge[a] = h
    # per half-edge corner data (at the edge's destination vertex)
    nh = len(ev)
    tex = [(0.0, 0.0)] * nh; nor = [(0.0, 0.0, 0.0)] * nh; tan = [(0.0, 0.0, 0.0, 0.0)] * nh
    fscale, fu, fv, fmat = [], [], [], []
    for f, (loop, m) in enumerate(faces):
        P = [verts[i] for i in loop]
        n = [0.0, 0.0, 0.0]
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            n[0] += a[1] * b[2] - a[2] * b[1]; n[1] += a[2] * b[0] - a[0] * b[2]; n[2] += a[0] * b[1] - a[1] * b[0]
        l = math.sqrt(sum(c * c for c in n)) or 1; n = tuple(c / l for c in n)
        U, V = axes_for(n)
        fscale.append((scale, scale)); fu.append(U + (0.0,)); fv.append(V + (0.0,)); fmat.append(matlist.index(m))
        h = face_edges[f]
        while True:
            p = verts[ev[h]]
            pw = (p[0] + origin[0], p[1] + origin[1], p[2] + origin[2])
            tex[h] = (sum(pw[i] * U[i] for i in range(3)) / scale / TEX, sum(pw[i] * V[i] for i in range(3)) / scale / TEX)
            nor[h] = n; tan[h] = U + (-1.0,)
            h = en[h]
            if h == face_edges[f]: break
    md = Element("CDmePolygonMesh", "meshData")
    md.set("vertexEdgeIndices", T_INT | ARRAY, vedge); md.set("vertexDataIndices", T_INT | ARRAY, list(range(len(verts))))
    md.set("edgeVertexIndices", T_INT | ARRAY, ev); md.set("edgeOppositeIndices", T_INT | ARRAY, eo); md.set("edgeNextIndices", T_INT | ARRAY, en)
    md.set("edgeFaceIndices", T_INT | ARRAY, ef); md.set("edgeDataIndices", T_INT | ARRAY, ed); md.set("edgeVertexDataIndices", T_INT | ARRAY, evd)
    md.set("faceEdgeIndices", T_INT | ARRAY, face_edges); md.set("faceDataIndices", T_INT | ARRAY, list(range(len(faces))))
    md.set("materials", T_STRING | ARRAY, matlist)
    md.set("vertexData", T_ELEMENT, data_array(len(verts), [stream("position:0", "position", "position", [tuple(map(float, v)) for v in verts], T_VEC3, flags=3)]))
    md.set("faceVertexData", T_ELEMENT, data_array(nh, [
        stream("texcoord:0", "texcoord", "texcoord", tex, T_VEC2), stream("normal:0", "normal", "normal", nor, T_VEC3),
        stream("tangent:0", "tangent", "tangent", tan, T_VEC4), stream("PerVertexLighting:0", "", "PerVertexLighting", [(1.0, 1.0, 1.0, 0.0)] * nh, T_VEC4, loc=1)]))
    md.set("edgeData", T_ELEMENT, data_array(nh // 2, [stream("flags:0", "flags", "flags", [0] * (nh // 2), T_INT, flags=3)]))
    md.set("faceData", T_ELEMENT, data_array(len(faces), [
        stream("textureScale:0", "textureScale", "textureScale", fscale, T_VEC2, flags=0),
        stream("textureAxisU:0", "textureAxisU", "textureAxisU", fu, T_VEC4, flags=0),
        stream("textureAxisV:0", "textureAxisV", "textureAxisV", fv, T_VEC4, flags=0),
        stream("materialindex:0", "materialindex", "materialindex", fmat, T_INT, flags=8),
        stream("flags:0", "flags", "flags", [0] * len(faces), T_INT, flags=3),
        stream("lightmapScaleBias:0", "lightmapScaleBias", "lightmapScaleBias", [0] * len(faces), T_INT)]))
    sub = Element("CDmePolygonMeshSubdivisionData", "")
    sub.set("subdivisionLevels", T_INT | ARRAY, [0] * nh); sub.set("streams", T_ELEMENT | ARRAY, [])
    md.set("subdivisionData", T_ELEMENT, sub)
    return md

def mapmesh(md, origin, physics="default"):
    m = Element("CMapMesh", "")
    for k, t, v in [("nodeID", T_INT, nid()), ("referenceID", T_UINT64, rid()), ("children", T_ELEMENT | ARRAY, []),
                    ("variableTargetKeys", T_STRING | ARRAY, []), ("variableNames", T_STRING | ARRAY, []),
                    ("cubeMapName", T_STRING, ""), ("lightGroup", T_STRING, ""), ("visexclude", T_BOOL, 0), ("disablemerging", T_BOOL, 0),
                    ("renderwithdynamic", T_BOOL, 0), ("disableHeightDisplacement", T_BOOL, 0), ("fademindist", T_FLOAT, -1.0), ("fademaxdist", T_FLOAT, 0.0),
                    ("bakelighting", T_BOOL, 1), ("precomputelightprobes", T_BOOL, 1), ("renderToCubemaps", T_BOOL, 1), ("emissiveLightingEnabled", T_BOOL, 1),
                    ("emissiveLightingBoost", T_FLOAT, 1.0), ("disableShadows", T_INT, 0), ("lightingDummy", T_BOOL, 0), ("smoothingAngle", T_FLOAT, 40.0),
                    ("tintColor", T_COLOR, (255, 255, 255, 255)), ("renderAmt", T_INT, 255), ("physicsType", T_STRING, physics), ("physicsGroup", T_STRING, ""),
                    ("physicsInteractsAs", T_STRING, ""), ("physicsInteractsWith", T_STRING, ""), ("physicsInteractsExclude", T_STRING, ""),
                    ("meshData", T_ELEMENT, md), ("physicsSimplificationOverride", T_BOOL, 0), ("physicsSimplificationError", T_FLOAT, 0.0),
                    ("origin", T_VEC3, tuple(map(float, origin))), ("angles", T_QANGLE, (0.0, 0.0, 0.0)), ("scales", T_VEC3, (1.0, 1.0, 1.0)),
                    ("transformLocked", T_BOOL, 0), ("force_hidden", T_BOOL, 0), ("editorOnly", T_BOOL, 0)]:
        m.set(k, t, v)
    return m

def box_mesh(x0, x1, y0, y1, z0, z1, mat, side=None, top=None, bottom=None, front=None, back=None, physics="default"):
    """Axis box as a map mesh. mat for all faces unless overridden: top/bottom/side, front = -Y face, back = +Y face."""
    o = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
    V = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    s = side or mat
    F = [((4, 5, 6, 7), top or mat), ((0, 3, 2, 1), bottom or mat),
         ((0, 1, 5, 4), front or s), ((2, 3, 7, 6), back or s), ((1, 2, 6, 5), s), ((3, 0, 4, 7), s)]
    return mapmesh(polymesh(V, F, None, o), o, physics)

def add(*items):
    for it in items: children.append(it)

# ------------------------------------------------------------------ materials
M = {
    "ground": "materials/ar_baggage/concrete_slabs_wet_1.vmat",
    "stage": "materials/de_inferno/wood/inferno_wood_floor_01_varnished.vmat",
    "lacquer": "materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_01_paint_red.vmat",
    "brick": "materials/brick/01/brick_clean_02.vmat",
    "brick2": "materials/brick/brick_ext_04.vmat",
    "dark": "materials/concrete/hr_c/hr_concrete_floor_001_dark.vmat",
    "concrete": "materials/concrete/hr_c/hr_concrete_floor_05.vmat",
    "shutter": "materials/metal/hr_metal/hr_metal_corrugated_001_blue.vmat",
    "window": "materials/de_cache/glass/ch2_sheet_glass_01_selfillum.vmat",
    "sky": "materials/tools/toolsskybox.vmat",
    "clip": "materials/tools/toolsplayerclip.vmat",
    "button": "materials/de_cache/glass/ch2_glassblock_02_selfillum.vmat",
}

# ------------------------------------------------------------------ sky shell and ground
SX0, SX1, SY0, SY1, SZ0, SZ1 = -860, 860, -1260, 620, -48, 760
T = 16
add(box_mesh(SX0 - T, SX1 + T, SY0 - T, SY0, SZ0, SZ1, M["sky"]), box_mesh(SX0 - T, SX1 + T, SY1, SY1 + T, SZ0, SZ1, M["sky"]),
    box_mesh(SX0 - T, SX0, SY0, SY1, SZ0, SZ1, M["sky"]), box_mesh(SX1, SX1 + T, SY0, SY1, SZ0, SZ1, M["sky"]),
    box_mesh(SX0 - T, SX1 + T, SY0 - T, SY1 + T, SZ1, SZ1 + T, M["sky"]), box_mesh(SX0 - T, SX1 + T, SY0 - T, SY1 + T, SZ0 - T, SZ0, M["sky"]))
add(box_mesh(-840, 840, -1240, 600, -16, 0, M["concrete"], top=M["ground"]))

# ------------------------------------------------------------------ the stage and gate
add(box_mesh(-480, 480, -90, 150, 0, 24, M["lacquer"], top=M["stage"]))
for sx in (-430, 430):
    add(box_mesh(sx - 9, sx + 9, 151, 169, 24, 330, M["lacquer"]))                 # gate pillars
    add(box_mesh(sx - 14, sx + 14, 146, 174, 24, 40, M["dark"]))                   # pillar feet
add(box_mesh(-505, 505, 144, 176, 330, 346, M["dark"], bottom=M["lacquer"]))        # kasagi (top beam)
add(box_mesh(-505, 505, 147, 173, 318, 330, M["lacquer"]))
add(box_mesh(-450, 450, 153, 167, 272, 286, M["lacquer"]))                          # nuki (tie beam)
add(box_mesh(-8, 8, 154, 166, 286, 318, M["dark"]))                                 # gakuzuka

# ------------------------------------------------------------------ buildings behind the stage
def building(x0, x1, y0, y1, h, wall, shutter_z=110, windows=((170, 230),), roof="pink"):
    add(box_mesh(x0, x1, y0, y1, 0, h, wall))
    add(box_mesh(x0 + 40, x1 - 40, y0 - 4, y0, 0, shutter_z, M["shutter"]))
    add(box_mesh(x0 + 20, x1 - 20, y0 - 40, y0, shutter_z + 8, shutter_z + 16, M["lacquer"]))   # awning
    for wz0, wz1 in windows:
        add(box_mesh(x0 + 60, x1 - 60, y0 - 3, y0, wz0, wz1, M["window"]))
    return (x0, x1, y0, h)
building(-840, -260, 200, 420, 400, M["brick"], windows=((175, 225), (275, 325)))
add(box_mesh(-260, 260, 260, 440, 0, 480, M["dark"]))
add(box_mesh(-220, 220, 256, 260, 0, 120, M["shutter"]))
add(box_mesh(-220, 220, 256, 260, 410, 450, M["window"]))
building(260, 840, 200, 420, 380, M["brick2"], windows=((170, 220), (260, 310)))
# wings: the street's side buildings
add(box_mesh(-840, -560, -430, 200, 0, 340, M["brick2"]), box_mesh(560, 840, -430, 200, 0, 340, M["brick"]))
add(box_mesh(-563, -560, -380, -120, 0, 110, M["shutter"]), box_mesh(560, 563, -380, -120, 0, 110, M["shutter"]))
add(box_mesh(-563, -560, -360, 140, 200, 250, M["window"]), box_mesh(560, 563, -360, 140, 190, 240, M["window"]))

# ------------------------------------------------------------------ audience side
add(box_mesh(-840, 840, -440, -430, 0, 30, M["dark"]))                              # barrier wall
add(box_mesh(-840, 840, -432, -428, 30, 600, M["clip"], physics="default"))         # keeps players out of the camera's air
ROW = 52
for k in range(4):
    add(box_mesh(-520, 520, -440 - ROW * (k + 1), -440 - ROW * k, 0, 16 * (k + 1), M["concrete"], top=M["dark"]))
PLAT_Z = 80
add(box_mesh(-520, 520, -800, -648, 0, PLAT_Z, M["concrete"], top=M["dark"]))      # pad platform
add(box_mesh(-840, 840, -1240, -1160, 0, 360, M["brick"]))                          # back street facade
add(box_mesh(-700, 700, -1160, -1156, 0, 110, M["shutter"]))
add(box_mesh(-640, 640, -1160, -1157, 170, 220, M["window"]))

# ------------------------------------------------------------------ props
def prop(model, origin, angles=(0, 0, 0), scales=(1, 1, 1), solid="0", props=None):
    p = {"model": model, "solid": solid, "rendercolor": "255 255 255", "skin": "default", "disableshadows": "1", "emissive": "1",
         "emissive_lighting_boost": "1.0", "bakelighting": "-1", "rendertocubemaps": "1"}
    p.update(props or {})
    return entity("prop_static", origin, angles, p, scales)
SIGN = "models/puppet_brawl/props/pb_sign_%s.vmdl"
NEON = "models/puppet_brawl/props/pb_neon_%s.vmdl"
add(prop(SIGN % "marquee", (0, 255, 364)))
add(prop(SIGN % "ryu", (-170, 255, 140)), prop(SIGN % "eigyou", (160, 255, 150)), prop(SIGN % "sake", (-60, 255, 150)))
add(prop(SIGN % "kakutou", (-300, 186, 150)), prop(SIGN % "ningyou", (300, 186, 150)))
add(prop(SIGN % "ramen", (-640, 194, 135)), prop(SIGN % "yoichi", (640, 194, 140)))
add(prop(SIGN % "ryu", (-556, -80, 180), (0, 90, 0)), prop(SIGN % "sake", (-556, 80, 140), (0, 90, 0)))
add(prop(SIGN % "eigyou", (556, -220, 130), (0, -90, 0)), prop(SIGN % "kakutou", (556, 60, 150), (0, -90, 0)))
add(prop(SIGN % "kakutou", (-420, -1154, 140), (0, 180, 0)), prop(SIGN % "ramen", (0, -1154, 150), (0, 180, 0)), prop(SIGN % "yoichi", (420, -1154, 140), (0, 180, 0)))
add(prop(SIGN % "eigyou", (-200, -1154, 125), (0, 180, 0)), prop(SIGN % "ningyou", (220, -1154, 145), (0, 180, 0)))
neon = [
    ("cyan", (0, -91, 21), (960, 2, 2)), ("pink", (0, -91, 3), (960, 2, 2)),
    ("pink", (0, 143, 328), (1010, 2, 2)), ("purple", (0, 258, 474), (520, 2, 2)),
    ("cyan", (-550, 198, 396), (580, 2, 2)), ("pink", (550, 198, 376), (580, 2, 2)),
    ("pink", (0, -445, 30), (1680, 2, 2)), ("yellow", (-550, 158, 126), (540, 2, 2)), ("yellow", (550, 158, 126), (540, 2, 2)),
    ("cyan", (-558, -135, 336), (2, 630, 2)), ("pink", (558, -135, 336), (2, 630, 2)),
    ("purple", (0, -1155, 356), (1680, 2, 2)),
    ("cyan", (-258, 258, 240), (2, 2, 480)), ("cyan", (258, 258, 240), (2, 2, 480)), ("pink", (0, 257, 126), (440, 2, 2)),
    ("purple", (0, 257, 352), (440, 2, 2)), ("yellow", (0, 257, 300), (300, 2, 2)),
]
for k in range(4):
    neon.append(("cyan" if k % 2 else "purple", (0, -441 - ROW * k, 16 * (k + 1) - 1), (1040, 2, 2)))
neon.append(("pink", (0, -649, PLAT_Z - 1), (1040, 2, 2)))
for c, o, s in neon: add(prop(NEON % c, o, scales=s))
# lanterns: one string under the gate, two over the street, with dark wires
def lantern_row(y, z, x0, x1, step):
    add(box_mesh(x0 - 10, x1 + 10, y - 0.5, y + 0.5, z, z + 1, M["dark"]))
    x = x0
    while x <= x1 + 0.1:
        add(prop("models/puppet_brawl/props/pb_lantern.vmdl", (x, y, z - 2 - 8 * math.cos((x - x0) / (x1 - x0 + 1) * math.pi * 2) ** 2)))
        x += step
lantern_row(150, 300, -340, 340, 85)
lantern_row(-560, 300, -760, 760, 95)
lantern_row(-900, 290, -760, 760, 95)

# ------------------------------------------------------------------ lights
LIGHT_BASE = {"vscripts": "", "targetname": "", "parentname": "", "parentAttachmentName": "", "useLocalOffset": "0", "local__origin": "", "local__angles": "",
              "local__scales": "1 1 1", "clientSideEntity": "1", "brightness_units": "1", "enabled": "1", "directlight": "1", "colormode": "0",
              "colortemperature": "6600", "skirt": "0.1", "bouncelight": "-1", "bouncescale": "1.0", "shape": "0", "size_params": "2.0 24.0 0.15",
              "lightcookie": "", "bakespeculartocubemaps": "0", "bakespeculartocubemaps_scale": "1.0", "minroughness": "0", "shadowmapsize": "-1",
              "shadowpriority": "-1", "pvs_modify_entity": "0", "shadowfade_size_start": ".10", "shadowfade_size_end": ".05", "brightnessscale": "1.0",
              "rendertocubemaps": "1", "showlight": "0", "fade_size_start": ".05", "fade_size_end": ".025", "transmit_always": "0", "light_style": ""}
def light(origin, color, lumens, rng, angles=(90, 0, 0), cone=180, shadows=0):
    p = dict(LIGHT_BASE)
    p.update({"color": "%d %d %d 255" % color, "brightness_lumens": str(lumens), "brightness": "%.4f" % (lumens / 2560), "brightness_legacy": "%.3f" % (lumens / 1000),
              "range": str(rng), "outer_angle": "%.1f" % cone, "inner_angle": "%.1f" % (cone * 0.75 if cone < 180 else 180), "castshadows": str(shadows)})
    return entity("light_omni2", origin, angles, p)
# key and fill on the stage (spots from the audience side), coloured rim lights from behind
add(light((0, -470, 330), (255, 236, 214), 14000, 1400, (32, 90, 0), 42, 1))
add(light((-420, -380, 280), (255, 120, 210), 6000, 1100, (28, 62, 0), 38, 1), light((420, -380, 280), (110, 210, 255), 6000, 1100, (28, 118, 0), 38, 1))
add(light((-380, 120, 300), (255, 60, 180), 4500, 700, (55, -60, 0), 60, 0), light((380, 120, 300), (60, 200, 255), 4500, 700, (55, -120, 0), 60, 0))
# neon and lantern glow
for o, c in [((0, 230, 340), (255, 70, 180)), ((-300, 170, 210), (255, 60, 130)), ((300, 170, 210), (60, 220, 255)), ((-640, 170, 200), (255, 210, 60)),
             ((640, 170, 200), (180, 90, 255)), ((-520, -80, 210), (255, 70, 40)), ((520, -220, 150), (90, 255, 140)), ((0, 150, 270), (255, 120, 60)),
             ((-420, -1120, 180), (255, 60, 140)), ((0, -1120, 190), (255, 200, 60)), ((420, -1120, 180), (170, 90, 255))]:
    add(light(o, c, 1400, 420))
for x in (-600, -200, 200, 600):
    add(light((x, -560, 270), (255, 130, 70), 1600, 520), light((x, -900, 260), (255, 130, 70), 1600, 520))
add(light((0, -700, 220), (150, 110, 255), 3000, 900))
le = find("light_environment")[0]
setp(le, color="120 140 230", brightness="0.18", skycolor="40 50 110 255", skyintensity="0.35", castshadows="1")
le["angles"] = (55.0, 130.0, 0.0); le["origin"] = (0.0, -300.0, 600.0)
sky = find("env_sky")[0]
setp(sky, skyname="materials/skybox/sky_rain_night_01.vmat", brightnessscale="0.6"); sky["origin"] = (0.0, -320.0, 620.0)
for f in find("env_cubemap_fog"):
    setp(f, cubemapfogstartdistance="300", cubemapfogenddistance="4500", cubemapfogmaxopacity="0.45", cubemapheightfog="0"); f["origin"] = (0.0, -320.0, 640.0)
for pv in find("env_combined_light_probe_volume"):
    pv["origin"] = (0.0, -320.0, 300.0)
    setp(pv, box_mins="-840 -920 -340", box_maxs="840 920 440", voxel_size="32.0")
for pp in find("post_processing_volume"):
    setp(pp, minexposure="1.4", maxexposure="2.2")
for mb, o in zip(find("cs_minimap_boundary"), [(-860, 620, 760), (860, -1260, -48)]): mb["origin"] = tuple(map(float, o))
for ps in find("info_player_start"): ps["origin"] = (-700.0, -800.0, 0.0); ps["angles"] = (0.0, 90.0, 0.0)
for nw in find("point_nav_walkable"): nw["origin"] = (0.0, -900.0, 16.0)

# ------------------------------------------------------------------ spawns (12 per team: left lane CT, right lane T)
for team, sign in (("info_player_counterterrorist", -1), ("info_player_terrorist", 1)):
    n = 0
    for ry in (-500, -580, -660, -740, -980, -1060):
        for rx in (700, 620):
            add(entity(team, (sign * rx, ry, 16), (0, 90, 0), {"targetname": "", "vscripts": "", "priority": "0", "enabled": "1"})); n += 1

# ------------------------------------------------------------------ game entities
add(entity("point_script", (0, -1000, 40), props={"targetname": "pb_script", "cs_script": "scripts/puppet_brawl.vjs"}))
add(entity("info_target", (-400, 0, 24), props={"targetname": "pb_stage_left", "spawnflags": "0"}),
    entity("info_target", (400, 0, 24), props={"targetname": "pb_stage_right", "spawnflags": "0"}))
PADS = [(-225, -720), (-75, -720), (75, -720), (225, -720)]
for i, (x, y) in enumerate(PADS):
    add(entity("info_target", (x, y, PLAT_Z), (0, 90, 0), {"targetname": "pb_pad_%d" % (i + 1), "spawnflags": "0"}))
    add(prop("models/puppet_brawl/props/pb_padring_%s.vmdl" % ("pink" if i < 2 else "cyan"), (x, y, PLAT_Z + 0.2)))
WATCH = [(-380, -470), (-130, -470), (130, -470), (380, -470)]
for i, (x, y) in enumerate(WATCH):
    add(entity("info_target", (x, y, 16), (0, 90, 0), {"targetname": "pb_watch_%d" % (i + 1), "spawnflags": "0"}))
add(entity("info_target", (-470, -760, PLAT_Z), (0, 90, 0), {"targetname": "pb_exit", "spawnflags": "0"}))
add(entity("custom_hud_layout", (0, -1000, 64), props={"targetname": "pb_hud", "layout": "panorama/layout/custom_game/puppet_brawl.vxml", "observable": "0"}))
for i, sid in enumerate(["hit", "heavy", "block", "whiff", "kd", "special", "ko", "bell", "tick", "select", "win"]):
    add(entity("point_soundevent", (-200 + 40 * i, 40, 70), props={"targetname": "pb_snd_" + sid, "soundName": "pb." + sid, "sourceEntityName": "",
        "startOnSpawn": "0", "toLocalPlayer": "0", "stopOnNew": "0", "saveAndRestore": "0", "sourceEntityAttachment": "", "entityIndexSelection": "0"}))
# templates: projectile/spark ball, and one body per fighter (rig + bone-merged agent)
DYN = {"skin": "default", "solid": "0", "spawnflags": "256", "disableshadows": "0", "rendercolor": "255 255 255", "renderamt": "255",
       "rendermode": "kRenderNormal", "renderfx": "kRenderFxNone", "use_animgraph": "0", "animgraph2_identifier": "", "StartDisabled": "0",
       "AnimateOnServer": "0", "randomizecycle": "0", "fademindist": "-1", "fademaxdist": "0", "glowstate": "0"}
def dyn(name, model, origin, extra=None):
    p = dict(DYN); p.update({"targetname": name, "model": model}); p.update(extra or {})
    return entity("prop_dynamic", origin, (0, 0, 0), p)
def template(name, members, origin):
    p = {"targetname": name, "spawnflags": "0", "asynchronous": "0", "spawnGroupType": "INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP"}
    for i, m in enumerate(members): p["Template%02d" % (i + 1)] = m
    return entity("point_template", origin, (0, 0, 0), p)
TZ = -30
add(dyn("pb_src_ball", "models/puppet_brawl/pb_ball.vmdl", (-600, -1000, TZ)), template("pb_tpl_ball", ["pb_src_ball"], (-600, -1000, TZ + 8)))
AGENTS = {"timber": "agents/models/tm_professional/tm_professional_varf.vmdl", "brass": "agents/models/ctm_swat/ctm_swat_varianth.vmdl",
          "pirouette": "agents/models/ctm_fbi/ctm_fbi_variantb.vmdl", "motley": "agents/models/tm_leet/tm_leet_variantf.vmdl"}
for i, (fid, model) in enumerate(AGENTS.items()):
    x = -500 + 120 * i
    rig = dyn("pb_src_rig_" + fid, "models/puppet_brawl/rig/pb_rig.vmdl", (x, -1000, TZ), {"StartingAnim": "idle", "StartingAnimationLoopMode": "ANIM_LOOP_MODE_LOOPING",
              "IdleAnim": "idle", "IdleAnimationLoopMode": "ANIM_LOOP_MODE_LOOPING"})
    agent = dyn("pb_src_agent_" + fid, model, (x, -1000, TZ), {"parentname": "pb_src_rig_" + fid, "parentAttachmentName": "!bonemerge", "useLocalOffset": "1",
                "local__origin": "0 0 0", "local__angles": "0 0 0", "local__scales": "1 1 1"})
    add(rig, agent, template("pb_tpl_" + fid, ["pb_src_rig_" + fid, "pb_src_agent_" + fid], (x, -1000, TZ + 8)))

# ------------------------------------------------------------------ labels and control buttons
def text(msg, origin, size=30, color=(255, 255, 255), units=0.25, face=(0, 90, 0)):
    p = {"message": msg, "enabled": "1", "fullbright": "1", "color": "%d %d %d 255" % color, "world_units_per_pixel": str(units), "font_size": str(size),
         "font_name": "Arial Black", "justify_horizontal": "1", "justify_vertical": "1", "reorient_mode": "1", "depth_render_offset": "0.125",
         "rendercolor": "255 255 255", "renderamt": "255", "rendermode": "kRenderNormal", "renderfx": "kRenderFxNone"}
    return entity("point_worldtext", origin, face, p)
for i, (x, y) in enumerate(PADS):
    add(text("PAD %d\n%s" % (i + 1, "RED" if i < 2 else "BLUE"), (x, y, PLAT_Z + 64), 34, (255, 90, 190) if i < 2 else (90, 210, 255)))
for i, (x, y) in enumerate(WATCH):
    add(text("WATCH\npress E", (x, y, 64), 26, (200, 170, 255)))
add(text("PUPPET BRAWL", (0, -800, 190), 80, (255, 70, 170)))
add(text("stand on a pad and press E to fight  ·  hold E to leave", (0, -800, 150), 30, (120, 230, 255)))
BUTTONS = [("MODE", "ModeNext"), ("ADD CPU", "AddCPU"), ("REMOVE CPU", "RemoveCPU"), ("START", "Start"),
           ("CPU EASY", "CpuEasy"), ("CPU NORMAL", "CpuNormal"), ("CPU HARD", "CpuHard"), ("RESET", "Reset")]
for i, (label, inp) in enumerate(BUTTONS):
    side = -1 if i < 4 else 1
    x = side * (380 + 40 * (i % 4)) if False else side * 470
    y = -660 - 34 * (i % 4)
    z = PLAT_Z + 40
    bm = box_mesh(x - 8, x + 8, y - 8, y + 8, z - 8, z + 8, M["button"])
    add(entity("func_button", (x, y, z), (0, 0, 0), {"targetname": "pb_btn_" + inp.lower(), "spawnflags": "1025", "speed": "5", "wait": "1", "lip": "0",
        "movedir": "0 0 0", "renderamt": "255", "rendercolor": "255 255 255", "rendermode": "kRenderNormal", "renderfx": "kRenderFxNone", "locked_sound": "",
        "unlocked_sound": "", "use_sound": "", "displaytext": "", "glow": "", "master": "", "forcenpcexclude": "0"},
        kids=[bm], conns=[("OnPressed", "pb_script", "RunScriptInput", inp, 0)]))
    add(box_mesh(x - 3, x + 3, y - 3, y + 3, PLAT_Z, z - 8, M["dark"]))
    add(text(label, (x, y, z + 20), 22, (255, 220, 120)))

# editor camera looking at the stage from the bleachers
cam = root["defaultcamera"]
cam["position"] = (0.0, -900.0, 260.0); cam["lookat"] = (0.0, 0.0, 80.0)
dm.save(OUT)
print("saved", OUT, "elements", len(dm.elements), "world nodes", len(children))
