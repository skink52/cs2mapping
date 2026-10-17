"""Daylight pass for indoor maps: lets a light_environment reach the playable areas.

1. adds a light_environment (stationary sun + sky ambient from the map's env_sky) if the map has none
2. picks the sun angle that lights the most floor, traces from sampled floor points towards the sun and straight up; every ceiling / roof mesh (face |normal z| >= 0.5)
   in the way gets disableShadows, walls are left casting shadows
3. adds env_combined_light_probe_volumes over the playable space if the map has none (players / weapons need them
   for indirect light, otherwise they render near black)
4. lets auto exposure brighten dark rooms (post_processing_volume maxexposure)
"""
import math, collections
import numpy as np
import dmx
from lighting import mesh_polys, voxelise, label_empty, TOOL_PASS

SUN_CANDIDATES = [(p, y, 0.0) for p in (60.0, 70.0) for y in range(0, 360, 45)]   # the one that lights most floor points wins
PLAY_CLASSES = ('info_player_counterterrorist', 'info_player_terrorist', 'info_teleport_destination', 'info_player_start') + \
               ('light_omni2', 'light_spot', 'light_barn', 'light_rect')

def all_meshes(m):
    out = []
    def walk(n, ent):
        for c in m.children(n):
            t = m.type(c)
            if t == b'CMapMesh': out.append((c, ent))
            elif t == b'CMapGroup': walk(c, ent)
            elif t == b'CMapEntity':
                cn = m.P(c, 'classname') or ''
                if not cn.startswith('trigger_'): walk(c, cn)
    walk(m.world, None)
    return out

def tris_of(m, meshes):
    A, B, C, mid, kind = [], [], [], [], []
    for i, (node, ent) in enumerate(meshes):
        for mat, loop in mesh_polys(m, node):
            k = 1 if ('moondome' in mat or 'toolsskybox' in mat or 'skybox/' in mat) else (2 if mat.startswith(TOOL_PASS) or 'toolsnodraw' in mat else 0)
            P = np.array(loop, np.float64)
            for j in range(1, len(P) - 1):
                A.append(P[0]); B.append(P[j]); C.append(P[j + 1]); mid.append(i); kind.append(k)
    return np.array(A), np.array(B), np.array(C), np.array(mid), np.array(kind)

def trace(A, B, C, O, d, chunk=48):
    """yields (ray index offset, t of every hit per ray, inf where no hit) in chunks"""
    e1, e2 = B - A, C - A
    p = np.cross(d, e2); det = np.einsum('ij,ij->i', e1, p)
    ok = np.abs(det) > 1e-9; inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
    for s in range(0, len(O), chunk):
        tv = O[s:s + chunk, None, :] - A[None]
        u = np.einsum('rij,ij->ri', tv, p) * inv
        q = np.cross(tv, e1[None])
        v = (q @ d) * inv
        t = np.einsum('rij,ij->ri', q, e2) * inv
        hit = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 1.0)
        yield s, np.where(hit, t, np.inf)

def run(m, c, spacing=64.0):
    ents = {m.P(e, 'classname'): e for e in m.entities()}
    meshes = all_meshes(m)
    A, B, C, mid, kind = tris_of(m, meshes)
    N = np.cross(B - A, C - A); N /= np.maximum(np.linalg.norm(N, axis=1), 1e-9)[:, None]
    # playable space: empty-space regions containing spawns / teleports / lights
    world = [pl for node, ent in meshes if ent is None for pl in mesh_polys(m, node)]
    vs = 32.0
    solid, lo = voxelise(world, vs); lab, _ = label_empty(solid); shape = np.array(lab.shape)
    vox = lambda p: tuple(np.clip(np.floor((np.asarray(p) - lo) / vs).astype(int), 0, shape - 1))
    play = set()
    for e in m.entities():
        if (m.P(e, 'classname') or '') in PLAY_CLASSES:
            o = m.g(e, b'origin'); l = lab[vox(o)]
            if l: play.add(l)
    exterior = set(np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(), lab[:, :, 0].ravel(), lab[:, :, -1].ravel()])))
    play -= exterior; play.discard(0)
    # floor samples
    S = []
    for mat, loop in world:
        if mat.startswith(TOOL_PASS) or 'tools' in mat: continue
        P = np.array(loop); n = np.cross(P[1] - P[0], P[2] - P[0]); ln = np.linalg.norm(n)
        if ln < 1e-6 or n[2] / ln < 0.6: continue
        for j in range(1, len(P) - 1):
            a, b, cc = P[0], P[j], P[j + 1]
            k = int(max(np.linalg.norm(b - a), np.linalg.norm(cc - a)) / spacing) + 1
            for uu in np.linspace(0, 1, k + 1):
                for ww in np.linspace(0, 1 - uu, max(1, int(k * (1 - uu)) + 1)):
                    q = a + uu * (b - a) + ww * (cc - a) + [0, 0, 16]
                    if lab[vox(q + [0, 0, 24])] in play: S.append(q)
    S = np.unique(np.round(np.array(S) / 16) * 16, axis=0) if S else np.zeros((0, 3))
    def cover(d):
        lit = 0; hits_all = set()
        for s0, T in trace(A, B, C, S, d):
            for r in range(len(T)):
                cand = np.nonzero(np.isfinite(T[r]))[0]
                order = cand[np.argsort(T[r][cand])]; hits = []; done = False
                for h in order:
                    if kind[h] == 1: lit += 1; done = True; break
                    if kind[h] == 2: continue
                    if abs(N[h, 2]) >= 0.5: hits.append(mid[h]); continue
                    done = True; break
                if not done: lit += 1
                hits_all.update(hits)
        return lit, hits_all
    def sun_dir(ang):
        p, y = math.radians(ang[0]), math.radians(ang[1])
        return np.array([-math.cos(p) * math.cos(y), -math.cos(p) * math.sin(y), math.sin(p)])
    best = None
    for ang in SUN_CANDIDATES:
        r = cover(sun_dir(ang))
        if best is None or r[0] > best[1][0]: best = (ang, r)
    sun_ang, (lit_sun, marked) = best
    lit_up, up_hits = cover(np.array([0, 0, 1.0])); marked |= up_hits
    lit = {'sun': lit_sun, 'up': lit_up}
    n_ent = 0
    for i in marked:
        node, ent = meshes[i]
        a = dmx.geta(m.E[node], b'disableShadows')
        if a: a[2] = 1 if a[1] == 2 else True
        else: dmx.set_(m.E[node], b'disableShadows', 2, 1)
        n_ent += ent is not None
    c.log.append('daylight: %d floor sample points in the playable space; %d ceiling / roof meshes between them and the sky set to cast no shadows (%d inside entities)'
                 % (len(S), len(marked), n_ent))
    c.log.append('daylight: with those ceilings open, %d%% of floor points see the sky towards the sun and %d%% straight up'
                 % (round(100.0 * lit['sun'] / max(1, len(S))), round(100.0 * lit['up'] / max(1, len(S)))))
    # light_environment
    if 'light_environment' not in ents:
        sky = ents.get('env_sky'); skyname = (m.P(sky, 'targetname') if sky is not None else '') or 'sky'
        if sky is not None and not m.P(sky, 'targetname'): m.setp(sky, 'targetname', skyname)
        allp = np.vstack([A, B, C]); top = allp.max(0); ctr = (allp.min(0) + top) / 2
        props = dict(enabled=1, color='255 246 228', brightness='1.5', range=512, castshadows=1, nearclipplane=1, shadowpriority=-1, style=0, pattern='',
                     fademindist=-250, fademaxdist=1250, rendertocubemaps=1, priority=0, lightgroup='', bouncescale='1.0', renderdiffuse=1, renderspecular=1,
                     rendertransmissive=1, directlight=3, indirectlight=1, angulardiameter='0.5', cascadecrossfade='.1', cascadedistancefade='.05',
                     skycolor='200 220 255', skyintensity='1.25', skytexture=skyname, skytexturescale='1.0', skyambientbounce='0 0 0', sunlightminbrightness=32,
                     skydirectlight=1, skybouncescale='1.0', brightnessscale='1.0', ambient_occlusion=0, max_occlusion_distance='16.0',
                     fully_occluded_fraction='1.0', occlusion_exponent='1.0', baked_light_indexing=1, minroughness=0, clientSideEntity=1)
        m.new_entity('light_environment', (ctr[0], ctr[1], top[2] - 64), props, angles=sun_ang)
        c.log.append('daylight: added a stationary light_environment (sun pitch %g yaw %g, brightness 1.5, sky ambient 1.25 from env_sky "%s")' % (sun_ang[0], sun_ang[1], skyname))
    # light probe volumes
    if 'env_combined_light_probe_volume' not in ents and play:
        idx = np.argwhere(np.isin(lab, list(play)))
        P = lo + (idx + 0.5) * vs
        ax = int(np.argmax(P.max(0) - P.min(0))); n_vol = 0
        start = P[:, ax].min()
        while start <= P[:, ax].max():
            sel = P[(P[:, ax] >= start) & (P[:, ax] < start + 2048)]
            start += 2048
            if not len(sel): continue
            mn, mx = sel.min(0) - 48, sel.max(0) + 48; o = (mn + mx) / 2
            props = dict(StartDisabled=0, cubemaptexture='', bakenearz='2.0', bakefarz='4096.0', lightgroup='', moveable=0, lightprobetexture='',
                         box_mins='%f %f %f' % tuple(mn - o), box_maxs='%f %f %f' % tuple(mx - o), voxel_size='48.0', flood_fill=1, voxelize=1,
                         light_probe_volume_from_cubemap=0, storage=-1, indoor_outdoor_level=0, edge_fade_dists='0 32 0', clientSideEntity=1)
            m.new_entity('env_combined_light_probe_volume', o, props); n_vol += 1
        c.log.append('daylight: map had no light probe volumes (players and weapons get no indirect light without them) - added %d env_combined_light_probe_volume over the playable space' % n_vol)
    for e in m.entities():
        if m.P(e, 'classname') == 'post_processing_volume':
            try: mx = float(m.P(e, 'maxexposure') or 0)
            except ValueError: mx = 0
            if mx < 2.0:
                m.setp(e, 'maxexposure', '2.0'); m.setp(e, 'enableexposure', '1')
                c.log.append('daylight: post_processing_volume maxexposure %g -> 2.0 so auto exposure can brighten dark rooms' % mx)
    c.todo.append('daylight: check the course in game - ceilings no longer cast shadows, so indoor floors get sun and sky light; adjust the light_environment brightness / angle if it looks too bright')
