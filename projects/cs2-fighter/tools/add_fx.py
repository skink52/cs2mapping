"""Adds the effect templates and the stage announcer text to a Hammer-saved mg_cs2_fighter.vmap,
keeping everything else as it is.
Usage: python3 add_fx.py <in.vmap> <out.vmap>"""
import copy, random, sys
import dmx9
from dmx9 import Element, T_STRING

SRC, OUT = sys.argv[1], sys.argv[2]
dm = dmx9.DMX.load(SRC)
world = dm.root["world"]

ents = [e for e in dm.elements if e.type == "CMapEntity"]
names = {e["entity_properties"].get("targetname") for e in ents}
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


def named(n):
    return next(e for e in ents if e["entity_properties"].get("targetname") == n)


def setprops(e, props, replace=False):
    ep = e["entity_properties"]
    if replace:
        keep = {k: ep.attrs[k] for k in ("classname",)}
        ep.attrs.clear(); ep.attrs.update(keep)
    for k, v in props.items():
        if k in ep: ep[k] = str(v)
        else: ep.set(k, T_STRING, str(v))


def add_copy(src, origin, angles=None, props=None, replace=False):
    c = clone(src, {})
    c["origin"] = tuple(float(v) for v in origin)
    if angles is not None: c["angles"] = tuple(float(v) for v in angles)
    if props: setprops(c, props, replace)
    world["children"].append(c)
    return c


report = []
src_ball, tpl_ball = named("pb_src_ball"), named("pb_tpl_ball")
bx, by, bz = src_ball["origin"]

# props: projectile models, the shockwave ring, the hit-flash star and the trail orb
PROPS = ["proj_knot", "proj_cog", "proj_jball", "fx_ring", "fx_burst", "fx_orb"]
for i, key in enumerate(PROPS):
    if "pb_tpl_" + key in names: continue
    o = (bx - 40 * (i + 1), by - 40, bz)
    add_copy(src_ball, o, props={"targetname": "pb_src_" + key, "model": f"models/puppet_brawl/pb_{key}.vmdl"})
    add_copy(tpl_ball, (o[0], o[1], o[2] + 8), props={"targetname": "pb_tpl_" + key, "Template01": "pb_src_" + key})
    report.append("template pb_tpl_" + key)

# stock CS2 particle effects. The source sits exactly on its template, so a spawn lands where asked.
PARTICLES = {
    "sparks": "particles/impact_fx/impact_metal.vpcf",
    "zap": "particles/generic_fx/fx_electricspark_glow_large.vpcf",
    "arc": "particles/generic_fx/fx_electric_arc_spark.vpcf",
    "streak": "particles/generic_fx/fx_electricspark_longtrail.vpcf",
    "firework": "particles/inferno_fx/firework_crate_explosion_01.vpcf",
    "confetti": "particles/money_fx/moneycrate_burst_confetti.vpcf",
    "dust": "particles/impact_fx/impact_dirt_child_smoke_puff.vpcf",
    "embers": "particles/burning_fx/env_embers_small.vpcf",
}
for i, (key, eff) in enumerate(PARTICLES.items()):
    if "pb_tpl_fx_" + key in names: continue
    o = (bx - 40 * (i + 1), by - 80, bz)
    add_copy(src_ball, o, props={"classname": "info_particle_system", "targetname": "pb_src_fx_" + key, "effect_name": eff,
             "start_active": "1", "flag_as_weather": "0", "cpoint1": "", "spawnflags": "0"}, replace=True)
    add_copy(tpl_ball, o, props={"targetname": "pb_tpl_fx_" + key, "Template01": "pb_src_fx_" + key})
    report.append("particle pb_tpl_fx_" + key + " -> " + eff)

# stage announcer: big world text hanging under the torii tie beam, above the fighters, facing the audience
title = next(e for e in ents if e["entity_properties"].get("classname") == "point_worldtext"
             and (e["entity_properties"].get("message") or "") == "PUPPET BRAWL")
if "pb_stage_text" not in names:
    add_copy(title, (0, 140, 248), (0, 0, 90), {"targetname": "pb_stage_text", "message": " ", "font_size": "110",
             "world_units_per_pixel": "0.3", "color": "255 196 70 255", "font_name": "Arial Black"})
    add_copy(title, (0, 140, 221), (0, 0, 90), {"targetname": "pb_stage_sub", "message": " ", "font_size": "60",
             "world_units_per_pixel": "0.3", "color": "255 90 70 255", "font_name": "Arial Black"})
    report.append("stage text pb_stage_text / pb_stage_sub under the torii beam at (0, 140, 248)")

dm.save(OUT)
print("\n".join(report) or "nothing to add")
