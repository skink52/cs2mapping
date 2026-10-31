"""Stage D pass `lightcover`: stationary lights for maps whose interior is one open compartment.

lighting.run (the `lights` pass) picks stationary lights per sealed compartment. On maps where every room connects to the
outdoors (doorways, open yards, roofs) the whole map is one compartment, so it switched only 3 of 132 lights on
ba_jail_keimusho and weapons stayed black indoors. This pass instead splits the empty space into roofed compartments
(first solid above is a wall, with doors / func_brush / func_breakable meshes counted as walls) and open-to-sky areas,
then per roofed compartment greedily switches lights to Stationary until 90% of the walkable floor (32-96 u above a floor)
is lit with line of sight, ranges capped at 640 u and no spot inside more than 4. Uncovered pockets near spawns, teleports,
buttons, triggers or weapons get a new unshadowed stationary light_omni2 (at most 320 u above the pocket floor). Every
open-to-sky play area (spawn / teleport destination clusters, 1500 u apart) gets an unshadowed stationary fill on top of
the stationary light_environment (skink52's rule, 29 Oct 2026). Existing lights are never deleted.
From ba_jail_keimusho (31 Oct 2026)."""
import math, collections
import numpy as np
from scipy import ndimage
import lighting

CAP = 640.0; MAXOV = 4

def run(m, c):
    LOG = c.log
    for env in m.by_class('light_environment'): m.setp(env, 'directlight', '3')
    lights0 = m.by_class('light_omni2')
    def _leg(e):
        try: v = float(m.P(e, 'brightness_legacy', '') or 'nan'); return v if math.isfinite(v) and v > 0 else None
        except ValueError: return None
    legs = sorted(x for x in (_leg(e) for e in lights0) if x)
    med_leg = legs[len(legs) // 2] if legs else 1.0
    used = set(lights0)
    vs = 32.0
    polys = lighting.world_polys(m)
    for e in m.by_class('func_door', 'func_door_rotating', 'func_movelinear', 'func_brush', 'func_breakable'):
        for ch in m.children(e):
            if m.type(ch) == b'CMapMesh': polys.extend(lighting.mesh_polys(m, ch))
    solid, lo = lighting.voxelise(polys, vs); S = np.array(solid.shape)
    above = np.zeros(solid.shape, np.uint8); cur = np.zeros(solid.shape[:2], np.uint8)
    for z in range(solid.shape[2] - 1, -1, -1):
        above[:, :, z] = cur; nz = solid[:, :, z]; cur = np.where(nz > 0, nz, cur)
    walk = np.zeros(solid.shape, bool); band = np.zeros(solid.shape, bool); dist = np.full(solid.shape[:2], 999)
    for z in range(solid.shape[2]):
        dist = np.where(solid[:, :, z] == 1, 0, dist + 1); walk[:, :, z] = (dist >= 1) & (dist <= 3); band[:, :, z] = dist <= 6
    empty = solid == 0
    li, ni = ndimage.label(empty & (above == 1)); lo_, no = ndimage.label(empty & (above != 1) & band)
    wall = solid == 1
    def vox(p): return tuple(np.clip(np.floor((np.array(p) - lo) / vs).astype(int), 0, S - 1))
    def reg(p):
        i = vox(p)
        for dz in (0, 1, -1, 2, 3, -2):
            j = (i[0], i[1], int(np.clip(i[2] + dz, 0, S[2] - 1)))
            if li[j]: return ('in', int(li[j]))
            if lo_[j]: return ('out', int(lo_[j]))
        return None
    def los(a, b):
        d = b - a; n = int(np.linalg.norm(d, axis=1).max() / 16) + 2; ok = np.ones(len(b), bool)
        for t in np.linspace(0.05, 0.95, n):
            q = a + d * t; idx = np.clip(np.floor((q - lo) / vs).astype(int), 0, S - 1); ok &= ~wall[idx[:, 0], idx[:, 1], idx[:, 2]]
        return ok
    PLAYCLS = ('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination')
    INTER = PLAYCLS + ('func_button', 'trigger_teleport', 'trigger_multiple', 'trigger_hurt', 'game_player_equip')
    play = collections.Counter(reg(m.origin(e)) for e in m.by_class(*PLAYCLS))
    inter_pts = np.array([m.origin(e) for e in m.by_class(*INTER)] + [m.origin(e) for e in m.entities() if m.cls(e).startswith('weapon_')])
    lights = m.by_class(*lighting.LIGHT_CLASSES)
    byreg = collections.defaultdict(list)
    for e in lights: byreg[reg(m.origin(e))].append(e)
    tmpl = lights0[0] if lights0 else None
    def new_light(p, rg, leg, color='255 255 214', shadows='0'):
        props = {a[0].decode(): a[2].decode() for a in m.props(tmpl)['attrs'] if a[0] not in (b'classname',)} if tmpl else dict(lighting.OMNI_DEFAULTS)
        props.update({'targetname': '', 'directlight': '3', 'range': '%.0f' % rg, 'enabled': '1', 'color': color, 'colormode': '0', 'castshadows': shadows,
                      'brightness_legacy': '%g' % leg, 'brightness': '%g' % round(math.log2(leg), 6), 'brightness_lumens': '%d' % round(1000 * leg),
                      'brightness_candelas': '%d' % round(1000 * leg / (4 * math.pi)), 'brightness_nits': '%d' % round(9816 * leg)})
        return m.new_entity('light_omni2', p, props)
    added = 0; switched = 0; rep = []
    sz_i = ndimage.sum(np.ones_like(li), li, index=np.arange(ni + 1))
    for key in [k for k in set(byreg) | set(play) if k and k[0] == 'in' and sz_i[k[1]] >= 64]:
        mask = (li == key[1]) & walk
        pts = lo + (np.argwhere(mask) + .5) * vs
        if not len(pts): continue
        if len(pts) > 8000: pts = pts[np.random.RandomState(1).choice(len(pts), 8000, replace=False)]
        Ls = byreg.get(key, []); P = np.array([m.origin(e) for e in Ls]).reshape(-1, 3)
        D = np.linalg.norm(pts[:, None, :] - P[None, :, :], axis=2) if len(Ls) else np.zeros((len(pts), 0))
        Vv = np.zeros_like(D, bool)
        for j in range(len(Ls)):
            nr = D[:, j] < CAP
            if nr.any(): Vv[nr, j] = los(P[j], pts[nr])
        cov = np.zeros(len(pts), bool); ov = np.zeros(len(pts), int); chosen = []
        while cov.mean() < 0.9:
            best = None
            for j in range(len(Ls)):
                if j in [x[0] for x in chosen]: continue
                rg = CAP
                while rg >= 192 and (ov[(D[:, j] < rg) & Vv[:, j]] >= MAXOV).any(): rg *= 0.85
                if rg < 192: continue
                h = (D[:, j] < rg) & Vv[:, j]; g = (h & ~cov).sum()
                if best is None or g > best[0]: best = (g, j, rg, h)
            if not best or best[0] < 0.004 * len(pts): break
            g, j, rg, h = best; chosen.append((j, rg)); cov |= h; ov += h
        for j, rg in chosen:
            e = Ls[j]; m.setp(e, 'directlight', '3'); switched += 1
            if rg < float(m.P(e, 'range', '0') or 0) - 1: m.setp(e, 'range', '%.0f' % rg)
        # uncovered play-relevant pockets -> new stationary lights
        unc = pts[~cov]; newn = 0
        if len(unc) >= 15:
            g = np.zeros(solid.shape, bool); ii = np.clip(np.floor((unc - lo) / vs).astype(int), 0, S - 1); g[ii[:, 0], ii[:, 1], ii[:, 2]] = 1
            lab, nn = ndimage.label(ndimage.binary_dilation(g, iterations=2) & (li == key[1]))
            for k in range(1, nn + 1):
                cell = np.argwhere(lab == k); cnt = int(g[lab == k].sum())
                if cnt < 15: continue
                cp = lo + (cell + .5) * vs; ctr = cp.mean(0)
                if not len(inter_pts) or np.min(np.linalg.norm(inter_pts - ctr, axis=1)) > max(256, float(np.ptp(cp, axis=0).max()) / 2 + 128): continue
                # light near the top of the pocket above its centre
                col = cell[np.argmin(np.linalg.norm(cp[:, :2] - ctr[:2], axis=1))]
                top = col.copy()
                while top[2] + 1 < S[2] and (li[top[0], top[1], top[2] + 1] == key[1]): top[2] += 1
                bot = col.copy()
                while bot[2] - 1 >= 0 and (li[bot[0], bot[1], bot[2] - 1] == key[1]): bot[2] -= 1
                p = lo + (top + .5) * vs - np.array([0, 0, 16])
                p[2] = min(p[2], lo[2] + bot[2] * vs + 320)
                rg = min(CAP, float(np.linalg.norm(cp - p, axis=1).max()) + 64)
                hit = (np.linalg.norm(pts - p, axis=1) < rg)
                while rg > 192 and (ov[hit] >= MAXOV).any(): rg *= 0.85; hit = (np.linalg.norm(pts - p, axis=1) < rg)
                new_light(p, rg, med_leg); ov += hit; cov |= hit & los(p, pts) ; added += 1; newn += 1
        rep.append((key, len(Ls), len(chosen), newn, round(float(cov.mean()), 2)))
    LOG.append('stationary: %d existing lights -> Stationary (line-of-sight cover of the walkable floor per roofed compartment, cap %d u, <= %d overlapping); %d new unshadowed stationary light_omni2 in uncovered play pockets; per compartment (lights, switched, new, cover): %s'
               % (switched, CAP, MAXOV, added, [(k[1], a, b, d, cv) for k, a, b, d, cv in rep]))
    # outdoor fills: one per cluster of spawns/teleport dests in each open-to-sky area with no stationary light
    env = m.by_class('light_environment')[0]; suncol = m.P(env, 'color') or '255 255 255'
    fills = 0
    for key in [k for k in play if k and k[0] == 'out']:
        ps = np.array([m.origin(e) for e in m.by_class(*PLAYCLS) if reg(m.origin(e)) == key])
        groups = []
        for p in ps:
            for gp in groups:
                if np.linalg.norm(np.mean(gp, 0)[:2] - p[:2]) < 1500: gp.append(p); break
            else: groups.append([p])
        for gp in groups:
            p = np.mean(gp, 0) + np.array([0, 0, 192])
            new_light(p, 1024, max(med_leg, 0.5), color=suncol); fills += 1
    LOG.append('outdoor: %d unshadowed stationary fill lights over the open-to-sky play areas (on top of the stationary sun)' % fills)

