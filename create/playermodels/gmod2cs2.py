"""Garry's Mod / Source 1 player model (ValveBiped skeleton) -> CS2 player model on the stock agent skeleton, so CS2's own
animation graph, hit boxes, ragdoll and weapon attachments work with it.

usage: python3 -I gmod2cs2.py <model.mdl> <slug> --roots <folder>[,<folder>...] --template <dir> --out <content addon>
                              [--skin N] [--bodygroup part=index ...] [--maxtex 2048] [--preview <dir>] [--report <json>]

  roots     folders holding models/ and materials/ (the extracted workshop item, plus any it depends on)
  template  a CS2 agent decompiled to ModelDoc with Source 2 Viewer and given ragdoll joints (docs/creation/models.md):
            <name>.vmdl, <name>_thirdperson_body.dmx, _firstperson_arms.dmx, _firstperson_sleeves.dmx, _tools_preview.dmx
  out       content addon root; writes models/player/gmod/<slug>/<slug>.vmdl + <slug>_body.dmx,
            models/player/gmod/shared/ (the template's first-person arms, sleeves, preview pose) and
            materials/models/player/gmod/<slug>/ (vmat + png)

How the mesh is moved: every ValveBiped bone is matched to a CS2 bone. The model keeps its own proportions (one uniform
scale, nothing stretched): each bone's piece of the mesh is only turned so the bone points the way the CS2 bone points
(GMod's reference pose -> CS2's A-pose) and stays joined to its parent at its own length. The uniform scale and offset are
fitted so the joints land as near CS2's as they can, feet on the floor; the report gives each joint's remaining offset.
A vertex weighted to several bones blends their turns. The forearm rolls gradually from elbow to wrist so the palm ends up
where CS2's palm is. Feet keep their soles flat. --fit is the older method (projects/cs21.6/tools/models.py's): pieces
stretched onto CS2's bone lengths and placed on CS2's joints.
Weights go to the matching CS2 bones (helper and jiggle bones follow their nearest mapped parent) and are spread over the
CS2 twist bones along the upper arms, forearms and thighs. Face flexes, jiggle bones, LODs and the GMod c_arms are dropped:
the first-person arms are the template's.
"""
import argparse, copy, json, os, re, shutil, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import dmx9
from dmx9 import Element
from srcmdl import SrcModel
import vtf

MODEL_DIR = 'models/player/gmod'
MAT_DIR = 'materials/models/player/gmod'


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rot_axis(u, a):
    u = u / np.linalg.norm(u); K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def arc(a, b):
    """rotation taking unit vector a onto unit vector b by the shortest arc"""
    v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.9999:
        ax = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


WRIST_BLEND = (3.0, 0.6)  # (u before the wrist where the blend starts, share of the forearm weight given to the hand at the wrist)
TORSO_RECENTRE = True     # move the upper torso back so the chest is centred on CS2's spine like a stock agent's
CHEST_WARN = 4.0          # warn when the chest front is this much (u) further forward than a stock agent's
HAND_WARN = 3.0           # warn when, in CS2's preview pose, the chest surface is this far (u) in front of a wrist (fine models: 0-1.6)
LIMB_WARN = 5.0           # warn when an arm/leg joint ends up this far (u) from CS2's: CS2 bends there, not at the model's joint (6 Nov: Leva at 5.4-6.0 u read as stretched thighs; was 6.0)
OWN_PARTS = ('leg_', 'ankle_', 'ball_')                     # own-joints mode: only the legs take the model's own joints
                                                             # (in game 6 Nov: own arms broke weapon poses, own neck stretched)
ARM_KEEP_HEIGHT = True   # own mode: arms keep the model's shoulder height (CS2's arm joints raised/lowered to it)
SHOULDER_BLEND = 7.0     # u: torso vertices this close to a snapped shoulder follow the arm's snap (fading out); 0 = off
HEAD_SNAP = False         # True: the head moves onto CS2's head joint (no sideways neck drag, ~4 u longer neck). Off: skink52 keeps the model's own head (6 Nov)
GMOD_PLAYER_COLOR = (0.24, 0.34, 0.41)   # GMod's default player colour (PlayerColor proxy), baked into tint-masked textures
HEAD_HITBOX_MIN = 1.0      # a head this close to a stock agent's keeps the stock head/neck hit boxes exactly (skink52, 6 Nov)
HEAD_HITBOX_MAX_NOHEAD = 12.0  # no head mesh (B2 droid): the head hit box may move this far onto the top of the body
HEAD_TOP_BAND = 8.0          # ... taken as the top 8 u of the mesh within 8 u of the centre line
HEAD_HITBOX_MAX = 5.0     # the head (and half of the neck) hit box moves at most this far (u) onto the model's head
FINGER_WARN = 1.8         # warn when finger segments' skin centres sit this far (median, u) off their CS2 bones (fine 0.4-1.7, old pivot bug ~2)
JOINT_SOFTEN = (2.5, 0.5)  # hard-skinned elbows/knees: within 2.5 u of the joint, up to half the weight goes to the other side
TWIST_STEP = 0.34         # split limb triangles whose twist changes more than this (0..1 of the chain) along an edge; 0 = off
SPINE_BEND = 0.5        # share of the spine/neck bones' turn onto CS2's spine that is applied


def partial(R, f):
    """the rotation R scaled to the fraction f of its angle"""
    ang = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if ang < 1e-6: return np.eye(3)
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * np.sin(ang))
    return rot_axis(ax, ang * f)


def frame(p, s):
    x = p / np.linalg.norm(p); z = np.cross(x, s); z /= np.linalg.norm(z); y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def unit(v): return v / (np.linalg.norm(v) or 1.0)


# ---------------------------------------------------------------- the template (CS2 skeleton in its bind pose)
class Template:
    def __init__(self, d):
        files = os.listdir(d)
        self.dir = d
        self.file = lambda sfx: os.path.join(d, next(f for f in files if f.endswith(sfx)))
        self.vmdl, self.body = self.file('.vmdl'), self.file('_thirdperson_body.dmx')
        dm = dmx9.DMX.load(self.body)
        self.joints = [j.name for j in dm.root['skeleton']['jointList'] if j.type == 'DmeJoint']
        self.W = self.joint_world(dm)
        self.parent, self.order = {}, []
        def walk(j, p):
            self.parent[j.name] = p; self.order.append(j.name)
            for c in j['children'] or []:
                if c.type == 'DmeJoint': walk(c, j.name)
        for c in dm.root['skeleton']['children']:
            if c.type == 'DmeJoint': walk(c, None)

    @staticmethod
    def joint_world(dm, pose=None):
        W = {}
        def walk(j, R, t):
            tr = j['transform']; p = (pose or {}).get(j.name, {})
            R2 = R @ quat_mat(p.get('orientation', tr['orientation'])); t2 = R @ np.array(p.get('position', tr['position'])) + t
            W[j.name] = (R2, t2)
            for c in j['children'] or []:
                if c.type == 'DmeJoint': walk(c, R2, t2)
        for c in dm.root['skeleton']['children']:
            if c.type == 'DmeJoint': walk(c, np.eye(3), np.zeros(3))
        return W

    def J(self, n): return self.W[n][1]

    def mesh(self):
        """the template's own body mesh (a stock-agent-shaped body): positions and per-vertex [(joint, weight)]"""
        if not hasattr(self, '_mesh'):
            dm = dmx9.DMX.load(self.body)
            vd = [e for e in dm.elements if e.type == 'DmeMesh'][0]['currentState']
            names = [j.name for j in dm.root['skeleton']['jointList']]
            P = np.array(vd['position$0']); jc = vd['jointCount']
            w = np.array(vd['blendweights$0']).reshape(-1, jc); ix = np.array(vd['blendindices$0']).reshape(-1, jc)
            pi = np.array(vd['position$0Indices'])        # weights are per position in this DMX
            Wt = [[(names[ix[i, k]], float(w[i, k])) for k in range(jc) if w[i, k] > 0] for i in range(len(P))]
            self._mesh = (P, Wt)
        return self._mesh

    def chest(self, V=None):
        """(front, back, centre) x of the chest relative to spine_2, measured between spine_2 and spine_3 + 2 u, |y| < 5"""
        if V is None: V = self.mesh()[0]
        z0, z1 = self.J('spine_2')[2], self.J('spine_3')[2] + 2
        sel = (V[:, 2] > z0) & (V[:, 2] < z1) & (np.abs(V[:, 1]) < 5)
        x = V[sel, 0] - self.J('spine_2')[0]
        if not len(x): return None                      # no mesh at chest height near the centre line (FragTrap, Hollow Knight's vessel)
        return float(x.max()), float(x.min()), float((x.max() + x.min()) / 2) + float(self.J('spine_2')[0])

    def hands_in_torso(self, V, W):
        """in the template's preview pose: how far the torso's front surface lies ahead of each hand joint at the hand's height
        (u; the stock agent body gives the baseline). Larger = the hand sits deeper in the chest."""
        Wp = self.preview_pose()
        Q = np.zeros_like(V); torso = np.zeros(len(V), bool)
        for i, w in enumerate(W):
            tot = sum(x for _, x in w) or 1
            for j, x in w:
                Rb, tb = self.W[j]; Rp, tp = Wp[j]
                Q[i] += x / tot * (Rp @ (Rb.T @ (V[i] - tb)) + tp)
            torso[i] = sum(x for j, x in w if j.startswith(('spine', 'pelvis', 'neck'))) / tot > 0.7
        out = {}
        for s in 'LR':
            h = Wp['hand_' + s][1]
            near = torso & (np.abs(Q[:, 2] - h[2]) < 2) & (np.abs(Q[:, 1] - h[1]) < 2)
            out[s] = round(float((Q[near, 0] - h[0]).max()), 2) if near.any() else None
        return out

    def preview_pose(self):
        """world transforms in the template's tools_preview pose (first frame)"""
        tp = dmx9.DMX.load(self.file('_tools_preview.dmx'))
        pose = {}
        for ch in (e for e in tp.elements if e.type == 'DmeChannel'):
            el, at, log = ch['toElement'], ch['toAttribute'], ch['log']
            if el is None or log is None or at not in ('position', 'orientation'): continue
            lay = log['layers'][0]
            if lay['values']: pose.setdefault(el.name, {})[at] = lay['values'][0]
        return self.joint_world(dmx9.DMX.load(self.body), pose)


def own_template(t, own):
    """a copy of the template whose joints sit at the model's own joints (own: {CS2 joint: position}), CS2's bind orientations
    kept (CS2's animations rotate bones: in game on 6 Nov 2026 a model kept its own bone lengths). Twist bones are spread along
    their limb; other unmapped joints (eyes, weapon, jiggle) move with their parent."""
    ot = copy.copy(t); ot.stock = t; W = {}
    seg = {}
    for base, chain in TWIST.items():
        for x in chain[1:]: seg[x] = (base, TWIST_END[base])
    for j in t.order:
        Rt, tt = t.W[j]
        if j in own: pos = np.asarray(own[j], float)
        elif j in seg and seg[j][0] in W and seg[j][1] in own:
            a, b = seg[j]
            f = np.linalg.norm(tt - t.J(a)) / max(1e-6, np.linalg.norm(t.J(b) - t.J(a)))
            pos = W[a][1] + f * (np.asarray(own[b]) - W[a][1])
        elif t.parent[j] is not None: pos = W[t.parent[j]][1] + (tt - t.J(t.parent[j]))
        else: pos = tt
        W[j] = (Rt, pos)
    ot.W = W
    def preview_pose():
        Wt = t.preview_pose(); P = {}
        for j in t.order:
            Rp, tp = Wt[j]; Rb, tb = W[j]; p = t.parent[j]
            if p is None: P[j] = (Rp, tp + Rp @ (t.W[j][0].T @ (tb - t.W[j][1])))
            else: P[j] = (Rp, P[p][0] @ (W[p][0].T @ (tb - W[p][1])) + P[p][1])
        return P
    ot.preview_pose = preview_pose
    return ot


# ---------------------------------------------------------------- ValveBiped -> CS2
FINGERS = {0: 'thumb', 1: 'index', 2: 'middle', 3: 'ring', 4: 'pinky'}


def bone_map():
    """ValveBiped short name (after 'bip01_', lower case) -> CS2 bone"""
    m = {'pelvis': 'pelvis', 'spine': 'spine_0', 'spine1': 'spine_1', 'spine2': 'spine_2', 'spine3': 'spine_2', 'spine4': 'spine_3',
         'neck1': 'neck_0', 'neck': 'neck_0', 'head1': 'head_0', 'head': 'head_0'}
    for s in 'LR':
        l = s.lower()
        m.update({f'{l}_clavicle': f'clavicle_{s}', f'{l}_upperarm': f'arm_upper_{s}', f'{l}_forearm': f'arm_lower_{s}',
                  f'{l}_hand': f'hand_{s}', f'{l}_thigh': f'leg_upper_{s}', f'{l}_calf': f'leg_lower_{s}',
                  f'{l}_foot': f'ankle_{s}', f'{l}_toe0': f'ball_{s}'})
        for f, fn in FINGERS.items():
            for k, suf in enumerate(('', '1', '2')):
                m[f'{l}_finger{f}{suf}'] = f'finger_{fn}_{k}_{s}'
    return m


VB2CS = bone_map()
# helper bones some GMod models carry: which main bone's piece they move with
HELPERS = [(r'_(l|r)_(bicep|shoulder|deltoid)', '{s}_upperarm'), (r'_(l|r)_(elbow|ulna|wrist|forearm_twist)', '{s}_forearm'),
           (r'_(l|r)_trapezius', '{s}_clavicle'), (r'_(l|r)_(knee|quad)', '{s}_thigh')]
TWIST = {f'{b}_{s}': [f'{b}_{s}', f'{b}_{s}_TWIST', f'{b}_{s}_TWIST1'] for s in 'LR' for b in ('arm_upper', 'arm_lower', 'leg_upper')}
TWIST_END = {f'arm_upper_{s}': f'arm_lower_{s}' for s in 'LR'}
TWIST_END.update({f'arm_lower_{s}': f'hand_{s}' for s in 'LR'}); TWIST_END.update({f'leg_upper_{s}': f'leg_lower_{s}' for s in 'LR'})


def short(name):
    n = name.lower()
    i = n.find('bip01_')
    return n[i + 6:] if i >= 0 else None


class Converter:
    def __init__(self, mdl, tpl, log=print):
        self.m, self.t, self.log = mdl, tpl, log
        self.names = [b['name'] for b in mdl.bones]
        self.idx = {}
        for i, n in enumerate(self.names):
            s = short(n)
            if s and s not in self.idx: self.idx[s] = i
        missing = [k for k in ('pelvis', 'l_thigh', 'r_thigh', 'l_upperarm', 'r_upperarm', 'head1') if k not in self.idx and not (k == 'head1' and 'head' in self.idx)]
        if missing: raise ValueError('not a ValveBiped player model (missing %s)' % ', '.join(missing))
        if 'head1' not in self.idx: self.idx['head1'] = self.idx['head']
        if 'neck1' not in self.idx and 'neck' in self.idx: self.idx['neck1'] = self.idx['neck']
        self.orient()

    # -------------------------------------------------- source skeleton, turned to face +X with the floor at z = 0
    def orient(self):
        m = self.m
        T = np.array([b['world'][:, 3] for b in m.bones])
        f = np.zeros(3)
        for s in 'lr':
            if f'{s}_toe0' in self.idx and f'{s}_foot' in self.idx: f += T[self.idx[f'{s}_toe0']] - T[self.idx[f'{s}_foot']]
        if np.hypot(f[0], f[1]) < 1e-3:      # no toes: thighs left-right, forward is up x left
            lr = T[self.idx['l_thigh']] - T[self.idx['r_thigh']]; f = np.cross(lr, [0, 0, 1.])
        a = np.arctan2(f[1], f[0])
        self.G = rot_axis(np.array([0, 0, 1.]), -a)
        self.yaw_deg = float(np.degrees(a))
        self.T = T @ self.G.T
        self.Rb = [self.G @ b['world'][:, :3] for b in m.bones]
        self.floor = float((m.V @ self.G.T)[:, 2].min())
        self.T[:, 2] -= self.floor
        self.height_head = float(self.T[self.idx['head1'], 2])
        self.height = float((m.V @ self.G.T)[:, 2].max() - self.floor)

    def S(self, n): return self.T[self.idx[n]]
    def has(self, n): return n in self.idx

    # -------------------------------------------------- per source bone: how its piece moves
    def transforms(self, mode='rigid'):
        """rigid (default): pieces keep their own lengths and shape; fit: pieces stretched onto CS2's bone lengths (old method)"""
        self.mode = mode
        if mode == 'own': return self.transforms_rigid(own=True)
        return self.transforms_rigid() if mode == 'rigid' else self.transforms_fit()

    def rotations(self, spine=False):
        """per mapped source bone: the rotation that turns its piece from GMod's reference pose into CS2's bind pose.
        spine=False keeps pelvis, spine, neck and head upright as modelled."""
        J = self.t.J
        R = {'pelvis': np.eye(3)}
        tw = {}
        self.unaligned_hands = []
        def d(a, b): return unit(self.S(b) - self.S(a))
        chain = [n for n in ('spine', 'spine1', 'spine2', 'spine3', 'spine4', 'neck1', 'head1') if self.has(n)]
        for n in chain: R[n] = np.eye(3)
        if spine:
            for a, b in zip(chain, chain[1:]): R[a] = partial(arc(d(a, b), unit(J(VB2CS[b]) - J(VB2CS[a]))), SPINE_BEND)
        for s in 'LR':
            l = s.lower()
            for a, b, ca, cb in ((f'{l}_clavicle', f'{l}_upperarm', f'clavicle_{s}', f'arm_upper_{s}'),
                                 (f'{l}_upperarm', f'{l}_forearm', f'arm_upper_{s}', f'arm_lower_{s}'),
                                 (f'{l}_forearm', f'{l}_hand', f'arm_lower_{s}', f'hand_{s}'),
                                 (f'{l}_thigh', f'{l}_calf', f'leg_upper_{s}', f'leg_lower_{s}'),
                                 (f'{l}_calf', f'{l}_foot', f'leg_lower_{s}', f'ankle_{s}')):
                if self.has(a) and self.has(b): R[a] = arc(d(a, b), unit(J(cb) - J(ca)))
            outer = next((k for k in (4, 3, 2) if self.has(f'{l}_finger{k}')), None)   # 3-finger rigs have no ring/pinky
            have_f = self.has(f'{l}_finger1') and outer is not None
            latcs = J(f'finger_index_0_{s}') - J('finger_%s_0_%s' % (FINGERS.get(outer, 'pinky'), s))
            if not have_f: self.unaligned_hands.append(s)
            if have_f:
                lat16 = self.S(f'{l}_finger1') - self.S(f'{l}_finger{outer}')
                mid = f'{l}_finger2' if self.has(f'{l}_finger2') else f'{l}_finger1'
                mcs = 'finger_middle_0_' + s if mid.endswith('2') else 'finger_index_0_' + s
                if self.has(f'{l}_hand'):
                    R[f'{l}_hand'] = frame(J(mcs) - J('hand_' + s), latcs) @ frame(self.S(mid) - self.S(f'{l}_hand'), lat16).T
                if f'{l}_forearm' in R:      # forearm roll spread from elbow (none) to wrist (the hand's)
                    ucs = unit(J(f'hand_{s}') - J(f'arm_lower_{s}'))
                    a1 = R[f'{l}_forearm'] @ lat16; a1 -= ucs * (a1 @ ucs); a2 = latcs - ucs * (latcs @ ucs)
                    if np.linalg.norm(a1) > 1e-6 and np.linalg.norm(a2) > 1e-6:
                        a1, a2 = unit(a1), unit(a2)
                        tw[f'{l}_forearm'] = (ucs, float(np.arctan2(np.cross(a1, a2) @ ucs, a1 @ a2)), d(f'{l}_forearm', f'{l}_hand'),
                                              float(np.linalg.norm(self.S(f'{l}_hand') - self.S(f'{l}_forearm'))))
                palm16 = np.cross(self.S(mid) - self.S(f'{l}_hand'), lat16)
                palmcs = np.cross(J('finger_middle_0_' + s) - J('hand_' + s), latcs)
                for f, fn in FINGERS.items():
                    sec16, seccs = (palm16, palmcs) if f == 0 else (lat16, latcs)
                    bones = [f'{l}_finger{f}', f'{l}_finger{f}1', f'{l}_finger{f}2']
                    cs = [f'finger_{fn}_{k}_{s}' for k in range(3)]
                    for k in range(2):
                        if self.has(bones[k]) and self.has(bones[k + 1]):
                            R[bones[k]] = frame(J(cs[k + 1]) - J(cs[k]), seccs) @ frame(self.S(bones[k + 1]) - self.S(bones[k]), sec16).T
                    for k in (1, 2):
                        if self.has(bones[k]) and bones[k] not in R and bones[k - 1] in R: R[bones[k]] = R[bones[k - 1]]
            elif self.has(f'{l}_hand') and f'{l}_forearm' in R:
                R[f'{l}_hand'] = R[f'{l}_forearm']
            if self.has(f'{l}_foot'):        # feet only turn about Z, so soles stay flat
                toe = self.S(f'{l}_toe0') if self.has(f'{l}_toe0') else self.S(f'{l}_foot') + np.array([4., 0, 0])
                h16 = toe - self.S(f'{l}_foot'); hcs = J(f'ball_{s}') - J(f'ankle_{s}'); h16[2] = hcs[2] = 0
                R[f'{l}_foot'] = arc(unit(h16), unit(hcs))
                if self.has(f'{l}_toe0'): R[f'{l}_toe0'] = R[f'{l}_foot']
        return R, tw

    def transforms_rigid(self, own=False):
        """Each piece only turns; it stays joined to its parent at its own length (forward kinematics down the model's own
        skeleton). One uniform scale (least squares over the main joints) and a horizontal offset are fitted so the joints land as
        near CS2's as they can; the feet stay on the floor. self.joint_offsets: distance from each CS2 joint after the fit."""
        J = self.t.J
        R, tw = self.rotations()
        order = [i for i, n in enumerate(self.names) if short(n) in R]
        def fk(sc):
            tr = {}
            for i in order:
                n = short(self.names[i])
                if n in tr: continue
                p = self.m.bones[i]['parent']
                while p >= 0 and short(self.names[p]) not in tr: p = self.m.bones[p]['parent']
                if p < 0: pcs = self.S(n) * sc
                else:
                    pt = tr[short(self.names[p])]
                    pcs = ((self.S(n) - pt['p16']) * sc) @ pt['R'].T + pt['pcs']
                tr[n] = dict(p16=self.S(n), pcs=pcs, R=R[n], axis=None, along=sc)
                if n in tw:
                    ax, ang, u16, L = tw[n]; tr[n].update(twist=(ax, ang), tw_u16=u16, len16=L)
            return tr
        fit = [n for n in R if n in VB2CS and 'finger' not in n and 'toe' not in n and n in self.idx]
        Q = np.array([fk(1.0)[n]['pcs'] for n in fit]); P = np.array([J(VB2CS[n]) for n in fit])
        Qc, Pc = Q - Q.mean(0), P - P.mean(0)
        sc = float((Qc * Pc).sum() / (Qc * Qc).sum())           # least-squares uniform scale
        tr = fk(sc)
        Qs = np.array([tr[n]['pcs'] for n in fit]); off = (P - Qs).mean(0)
        off[2] = 0.0                                             # feet stay on the floor
        for t in tr.values(): t['pcs'] = t['pcs'] + off
        # Arms and hands must sit on CS2's own pivots: finger bones are ~1.5 u long, so a hand 2-3 u off its CS2 bones is
        # wrung apart as soon as CS2 curls the fingers. Each arm moves as one rigid piece so the shoulder sits on CS2's;
        # then the hand (with its fingers) goes onto CS2's wrist, uniformly sized to CS2's palm. The forearm takes the
        # small difference (its wrist end follows the hand by the skin weights).
        parent = {}
        for i in order:
            n = short(self.names[i]); p = self.m.bones[i]['parent']
            while p >= 0 and short(self.names[p]) not in tr: p = self.m.bones[p]['parent']
            parent[n] = short(self.names[p]) if p >= 0 else None
        def subtree(root):
            out = []
            for n in tr:
                q = n
                while q is not None and q != root: q = parent.get(q)
                if q == root: out.append(n)
            return out
        # Torso depth: GMod chests sit 2-3.5 u further forward on the spine than a stock agent's, which puts CS2's hand poses
        # inside them. The upper torso moves back as one piece until its chest is centred on CS2's spine like the agent's
        # (spine1 half way, so the waist shears gradually); legs stay put, arms are re-seated on the shoulders below.
        self.chest_shift = 0.0
        top = next((n for n in ('spine2', 'spine3', 'spine4') if n in tr), None)
        if top and TORSO_RECENTRE:
            lo, hi = sorted((self.S(top)[2], self.S('spine4' if 'spine4' in tr else top)[2] + 2 / sc))
            V0 = self.m.V @ self.G.T; V0[:, 2] -= self.floor
            sel = (V0[:, 2] > lo) & (V0[:, 2] < hi) & (np.abs(V0[:, 1] - self.S(top)[1]) < 5 / sc)
            if sel.sum() > 10:
                x = self.move(V0[sel], tr[top], sc)[:, 0]
                self.chest_shift = float(self.t.chest()[2] - (x.max() + x.min()) / 2)
                dx = np.array([self.chest_shift, 0, 0])
                for n in subtree(top): tr[n]['pcs'] = tr[n]['pcs'] + dx
                if 'spine1' in tr and top != 'spine1': tr['spine1']['pcs'] = tr['spine1']['pcs'] + dx / 2
        self.hand_scale = {}; self.arm_snap = {}; self.arm_lift = {}
        for s in 'LR':                           # arms and hands on CS2's pivots in every mode (own joints too: CS2's weapon
                                                 # poses are built for an agent's shoulders; own arm joints put the hands off the gun)
            l = s.lower()
            root = f'{l}_clavicle' if f'{l}_clavicle' in tr else f'{l}_upperarm'
            if f'{l}_upperarm' not in tr: continue
            d = J(f'arm_upper_{s}') - tr[f'{l}_upperarm']['pcs']
            lift = np.array([0.0, 0.0, -d[2]]) if (own and ARM_KEEP_HEIGHT) else np.zeros(3)   # own: keep the model's shoulder height
            d = d + lift; self.arm_lift[s] = lift
            for n in subtree(root): tr[n]['pcs'] = tr[n]['pcs'] + d; tr[n]['arm'] = s
            self.arm_snap[s] = (J(f'arm_upper_{s}') + lift, d.copy())
            h = f'{l}_hand'
            if h not in tr: continue
            k = 1.0
            mid = next((f for f in (f'{l}_finger2', f'{l}_finger1') if f in tr), None)
            if mid:
                mcs = 'finger_middle_0_' + s if mid.endswith('2') else 'finger_index_0_' + s
                k = float(np.clip(np.linalg.norm(J(mcs) - J('hand_' + s)) / max(1e-6, np.linalg.norm(tr[mid]['pcs'] - tr[h]['pcs'])), 0.8, 1.25))
            hp = tr[h]['pcs'].copy()
            for n in subtree(h):
                tr[n]['pcs'] = J('hand_' + s) + lift + (tr[n]['pcs'] - hp) * k
                tr[n]['along'] = sc * k
            self.hand_scale[s] = round(k, 3)
        # Head on CS2's head joint (6 Nov): GMod heads pivot ~4 u below CS2's head_0 (shorter HL2 necks). CS2's poses turn and
        # tilt the head about head_0, so a head left low swings sideways about a pivot above it and drags the neck. The head
        # moves rigidly onto head_0 (the neck joint half as far: the neck lengthens evenly); the stock head hit box then fits.
        self.head_snap = 0.0
        if HEAD_SNAP and 'head1' in tr and not own:
            d = J('head_0') - tr['head1']['pcs']
            self.head_snap = round(float(np.linalg.norm(d)), 2)
            for n in subtree('head1'): tr[n]['pcs'] = tr[n]['pcs'] + d
            if 'neck1' in tr: tr['neck1']['pcs'] = tr['neck1']['pcs'] + d / 2
        self.girth = sc
        self.joint_offsets = {VB2CS[n]: round(float(np.linalg.norm(tr[n]['pcs'] - J(VB2CS[n]))), 2) for n in fit}
        if own:
            self.own_joints = {}
            for n in tr:
                cs = VB2CS.get(n)
                if cs and cs not in self.own_joints and cs.startswith(OWN_PARTS): self.own_joints[cs] = tr[n]['pcs'].copy()
            for s, lift in self.arm_lift.items():       # the arm chain: CS2's joints, at the model's shoulder height
                if not lift.any(): continue
                for j in self.t.joints:
                    if j.endswith('_' + s) and j.startswith(('clavicle', 'arm_upper', 'arm_lower', 'hand', 'finger', 'weapon_hand')):
                        self.own_joints[j] = J(j) + lift
        return self._assign(tr)

    def transforms_fit(self):
        J = self.t.J
        g = J('head_0')[2] / self.height_head            # across-the-bone scale (height ratio)
        self.girth = g
        tr = {}
        hip16 = (self.S('l_thigh') + self.S('r_thigh')) / 2; hipcs = (J('leg_upper_L') + J('leg_upper_R')) / 2
        tr['pelvis'] = dict(p16=hip16, pcs=hipcs, R=np.eye(3), axis=None, along=g)

        def seg(a, b, ca, cb, R=None):
            if not (self.has(a) and self.has(b)): return False
            d16 = self.S(b) - self.S(a); dcs = J(cb) - J(ca)
            L16, Lcs = np.linalg.norm(d16), np.linalg.norm(dcs)
            if L16 < 1e-4: return False
            u16, ucs = d16 / L16, dcs / Lcs
            tr[a] = dict(p16=self.S(a), pcs=J(ca), R=arc(u16, ucs) if R is None else R(u16, ucs), axis=u16,
                         along=float(np.clip(Lcs / L16, 0.6, 1.8)), len16=L16)
            return True

        def inherit(n, parent, cs):
            if self.has(n) and parent in tr:
                p = tr[parent]; tr[n] = dict(p16=self.S(n), pcs=J(cs), R=p['R'], axis=None, along=g)

        # spine and neck: chain through whichever spine bones the model has
        chain = [n for n in ('spine', 'spine1', 'spine2', 'spine3', 'spine4', 'neck1', 'head1') if self.has(n)]
        if 'spine3' in chain and 'spine4' in chain: chain.remove('spine3')
        # (only part of each spine/neck bend is applied: the full turn hunches the back and tips the face up; the pieces
        #  still hang from the CS2 joints, so the weights line up)
        for a, b in zip(chain, chain[1:]):
            seg(a, b, VB2CS[a], VB2CS[b], R=lambda u16, ucs: partial(arc(u16, ucs), SPINE_BEND))
        # the head stays level, facing forward, on CS2's head joint
        if self.has('head1'): tr['head1'] = dict(p16=self.S('head1'), pcs=J('head_0'), R=np.eye(3), axis=None, along=g)
        for s in 'LR':
            l = s.lower()
            seg(f'{l}_clavicle', f'{l}_upperarm', f'clavicle_{s}', f'arm_upper_{s}')
            seg(f'{l}_upperarm', f'{l}_forearm', f'arm_upper_{s}', f'arm_lower_{s}')
            seg(f'{l}_thigh', f'{l}_calf', f'leg_upper_{s}', f'leg_lower_{s}')
            seg(f'{l}_calf', f'{l}_foot', f'leg_lower_{s}', f'ankle_{s}')
            # hand: the palm turned so index and pinky knuckles sit where CS2's do
            outer = next((k for k in (4, 3, 2) if self.has(f'{l}_finger{k}')), None)
            have_f = self.has(f'{l}_finger1') and outer is not None
            lat16 = self.S(f'{l}_finger1') - self.S(f'{l}_finger{outer}') if have_f else None
            latcs = J(f'finger_index_0_{s}') - J('finger_%s_0_%s' % (FINGERS.get(outer, 'pinky'), s))
            mid = f'{l}_finger2' if self.has(f'{l}_finger2') else (f'{l}_finger1' if self.has(f'{l}_finger1') else None)
            if mid and have_f and self.has(f'{l}_hand'):
                seg(f'{l}_hand', mid, f'hand_{s}', 'finger_middle_0_' + s if mid.endswith('2') else 'finger_index_0_' + s,
                    R=lambda u16, ucs: frame(ucs, latcs) @ frame(u16, lat16).T)
            elif self.has(f'{l}_hand') and f'{l}_forearm' in tr:
                inherit(f'{l}_hand', f'{l}_forearm', f'hand_{s}')
            # forearm: straight onto CS2's forearm, then twisted from elbow (0) to wrist (full) to meet the hand's roll
            if seg(f'{l}_forearm', f'{l}_hand', f'arm_lower_{s}', f'hand_{s}') and have_f:
                t = tr[f'{l}_forearm']; ucs = unit(J(f'hand_{s}') - J(f'arm_lower_{s}'))
                a1 = t['R'] @ lat16; a1 -= ucs * (a1 @ ucs); a2 = latcs - ucs * (latcs @ ucs)
                if np.linalg.norm(a1) > 1e-6 and np.linalg.norm(a2) > 1e-6:
                    a1, a2 = unit(a1), unit(a2)
                    t['twist'] = (ucs, float(np.arctan2(np.cross(a1, a2) @ ucs, a1 @ a2)))
            # fingers: each piece along its CS2 bone, rolled with the palm (the thumb with the palm's normal)
            if have_f:
                palm16 = np.cross(self.S(mid) - self.S(f'{l}_hand'), lat16) if mid else lat16
                palmcs = np.cross(J('finger_middle_0_' + s) - J('hand_' + s), latcs)
                for f, fn in FINGERS.items():
                    sec16, seccs = (palm16, palmcs) if f == 0 else (lat16, latcs)
                    bones = [f'{l}_finger{f}', f'{l}_finger{f}1', f'{l}_finger{f}2']
                    cs = [f'finger_{fn}_{k}_{s}' for k in range(3)]
                    for k in range(2):
                        seg(bones[k], bones[k + 1], cs[k], cs[k + 1], R=lambda u16, ucs: frame(ucs, seccs) @ frame(u16, sec16).T)
                    if bones[1] in tr: inherit(bones[2], bones[1], cs[2])
                    elif bones[0] in tr: inherit(bones[1], bones[0], cs[1])
            # feet: the sole stays flat on the floor; the foot only turns to point where CS2's foot points
            if self.has(f'{l}_foot'):
                toe = self.S(f'{l}_toe0') if self.has(f'{l}_toe0') else self.S(f'{l}_foot') + np.array([4., 0, 0])
                h16 = toe - self.S(f'{l}_foot'); hcs = J(f'ball_{s}') - J(f'ankle_{s}')
                h16[2] = hcs[2] = 0
                pcs = J(f'ankle_{s}').copy(); pcs[2] = self.S(f'{l}_foot')[2] * g
                tr[f'{l}_foot'] = dict(p16=self.S(f'{l}_foot'), pcs=pcs, R=arc(unit(h16), unit(hcs)), axis=None, along=g)
                if self.has(f'{l}_toe0'): tr[f'{l}_toe0'] = tr[f'{l}_foot']
        return self._assign(tr)

    def _assign(self, tr):
        """every source bone: its own piece, a helper's main bone, or the nearest parent that has one"""
        self.tr_by_bone, self.cs_by_bone, self.unknown = [], [], []
        for i, n in enumerate(self.names):
            s = short(n)
            key = s if s in tr else None
            cs = VB2CS.get(s)
            if key is None and s is not None:
                for pat, main in HELPERS:
                    mm = re.search(pat, '_' + s)
                    if mm and main.format(s=mm.group(1)) in tr:
                        key = main.format(s=mm.group(1)); cs = VB2CS[key]; break
            if key is None or cs is None:
                p = i
                while p >= 0 and (short(self.names[p]) not in tr): p = self.m.bones[p]['parent']
                pk = short(self.names[p]) if p >= 0 else 'pelvis'
                key = key or pk; cs = cs or VB2CS.get(pk, 'pelvis')
                if s not in VB2CS: self.unknown.append(n)
            self.tr_by_bone.append(tr[key]); self.cs_by_bone.append(cs)
        self.tr = tr
        return tr

    @staticmethod
    def move(x, t, g):
        """points x (k,3) by one piece transform"""
        d = x - t['p16']
        if t['axis'] is not None:
            a_ = d @ t['axis']
            y = (a_[:, None] * t['axis'] * t['along'] + (d - a_[:, None] * t['axis']) * g) @ t['R'].T
        else:
            y = (d * t['along']) @ t['R'].T
        if 'twist' in t:
            ax, ang = t['twist']
            f = np.clip((d @ t.get('tw_u16', t['axis'])) / t['len16'], 0, 1)
            c, s_ = np.cos(ang * f)[:, None], np.sin(ang * f)[:, None]
            y = y * c + np.cross(ax, y) * s_ + ax * (y @ ax)[:, None] * (1 - c)
        return y + t['pcs']

    # -------------------------------------------------- the mesh
    def convert_mesh(self, meshes):
        m = self.m
        used = np.unique(np.concatenate([x['tris'].ravel() for x in meshes]))
        remap = -np.ones(len(m.V), int); remap[used] = np.arange(len(used))
        V0 = m.V[used] @ self.G.T; V0[:, 2] -= self.floor
        N0 = m.N[used] @ self.G.T
        W, B = m.W[used], m.B[used]
        g = self.girth
        V = np.zeros_like(V0); N = np.zeros_like(N0)
        for k in range(3):
            for bi in np.unique(B[:, k]):
                sel = (B[:, k] == bi) & (W[:, k] > 0)
                if not sel.any(): continue
                t = self.tr_by_bone[bi]
                V[sel] += W[sel, k:k + 1] * self.move(V0[sel], t, g)
                N[sel] += W[sel, k:k + 1] * (N0[sel] @ t['R'].T)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        # Shoulder blend: the arm moved onto CS2's shoulder as one piece, but chest, trap and armpit vertices skinned to the torso
        # stayed put, so the skin between stretched or caved in (skink52, in game: the NCR ranger's traps, Rogue's armpit). Torso
        # vertices near the shoulder follow the arm's move, fading to nothing SHOULDER_BLEND u away; joints and weapon poses as before.
        if SHOULDER_BLEND > 0 and getattr(self, 'arm_snap', None):
            for side, (sh, d) in self.arm_snap.items():
                armw = np.zeros(len(V))
                for k in range(3):
                    armw += W[:, k] * np.array([self.tr_by_bone[b].get('arm') == side for b in B[:, k]])
                f = np.clip(1 - np.linalg.norm(V - sh, axis=1) / SHOULDER_BLEND, 0, 1) * np.clip(1 - armw, 0, 1)
                V += f[:, None] * d
        # CS2 weights: by bone, then spread along the twist chains
        J = self.t.J
        weights = []
        for i in range(len(V)):
            acc = {}
            for k in range(3):
                if W[i, k] <= 0: continue
                cs = self.cs_by_bone[B[i, k]]
                for j, w in self.spread(cs, V[i]): acc[j] = acc.get(j, 0) + W[i, k] * w
            self.wrist_blend(acc, V[i])
            self.soften_joint(acc, V[i])
            weights.append(sorted(acc.items(), key=lambda x: -x[1])[:3])
        return used, remap, V, N, weights

    def soften_joint(self, acc, x):
        """Hard-skinned rigs (every vertex 100% one bone, HL1/low-poly style) fold into a thin wedge when CS2 bends an elbow or knee.
        A vertex that is >= 95% one side's chain and within JOINT_SOFTEN[0] u of the joint (along the limb) gives up to JOINT_SOFTEN[1]
        of its weight to the other side, fading to nothing at that distance. Blended (properly skinned) vertices are left alone."""
        R, mx = JOINT_SOFTEN
        if mx <= 0: return
        tot = sum(acc.values()) or 1.0
        J = self.t.J
        for s in 'LR':
            for up, lo, top in ((f'arm_upper_{s}', f'arm_lower_{s}', f'hand_{s}'), (f'leg_upper_{s}', f'leg_lower_{s}', f'ankle_{s}')):
                upc = [j for j in acc if j.startswith(up)]
                loc = [j for j in acc if j.startswith(lo)]
                wu = sum(acc[j] for j in upc) / tot; wl = sum(acc[j] for j in loc) / tot
                if max(wu, wl) < 0.95: continue
                a = J(up); k = J(lo)
                u1 = unit(k - a); u2 = unit(J(top) - k)
                d = float((x - k) @ u1) if wu >= 0.95 else float((x - k) @ u2)      # signed distance past (upper) / below (lower) the joint
                dist = abs(min(d, 0.0)) if wu >= 0.95 else abs(max(d, 0.0))
                if wu >= 0.95 and d > 0: dist = 0.0                                   # upper-arm vertices already past the joint
                if wl >= 0.95 and d < 0: dist = 0.0
                f = mx * max(0.0, 1.0 - dist / R)
                if f <= 0: continue
                src, dst = (upc, lo) if wu >= 0.95 else (loc, up + ('_TWIST1' if up + '_TWIST1' in self.t.W else ''))
                moved = 0.0
                for j in src: moved += acc[j] * f; acc[j] *= 1 - f
                acc[dst] = acc.get(dst, 0) + moved
                return

    def wrist_blend(self, acc, x):
        """The last WRIST_BLEND[0] u of the forearm (sleeve cuff included) follow the hand by up to WRIST_BLEND[1], so a hand bent
        back (holding a barrel) lifts the cuff instead of pushing through it. GMod cuffs are weighted to the forearm only."""
        R, mx = WRIST_BLEND
        if mx <= 0: return
        J = self.t.J
        for s in 'LR':
            chain = [f'arm_lower_{s}', f'arm_lower_{s}_TWIST', f'arm_lower_{s}_TWIST1']
            fw = sum(acc.get(j, 0) for j in chain)
            if fw <= 0: continue
            h = J(f'hand_{s}'); u = unit(h - J(f'arm_lower_{s}'))
            f = float(np.clip(((x - h) @ u + R) / R, 0, 1)) * mx
            if f <= 0: continue
            for j in chain:
                if j in acc: acc[j] *= 1 - f
            acc[f'hand_{s}'] = acc.get(f'hand_{s}', 0) + fw * f

    def spread(self, cs, x):
        if cs not in TWIST: return [(cs, 1.0)]
        J = self.t.J
        a = J(cs); u = J(TWIST_END[cs]) - a; L = np.linalg.norm(u); u /= L
        pts = sorted(((float((J(j) - a) @ u / L), j) for j in TWIST[cs] if j in self.t.W), key=lambda p: p[0])
        t = float((x - a) @ u / L)
        if t <= pts[0][0]: return [(pts[0][1], 1.0)]
        for (t0, j0), (t1, j1) in zip(pts, pts[1:]):
            if t <= t1:
                w = (t - t0) / max(1e-6, t1 - t0); return [(j0, 1 - w), (j1, w)]
        return [(pts[-1][1], 1.0)]


# ---------------------------------------------------------------- materials
def is_shared_eye(name): return name.startswith('eyeball') or name in ('eye_l', 'eye_r', 'eyes', 'eye')
def is_shared_mouth(name): return name in ('mouth', 'teeth', 'tongue') or name.startswith(('mouth_', 'teeth_'))


def eye_standin(n=256, iris=(84, 66, 48)):
    """an eye texture laid out like Source's iris projection (the image spans the iris diameter, the clamped edge is sclera):
    off-white sclera, a brown iris with a darker rim, black pupil, a small highlight"""
    y, x = (np.mgrid[0:n, 0:n] + 0.5) / n - 0.5
    r = np.hypot(x, y) * 2                                   # 1 = edge of the image
    img = np.zeros((n, n, 4), np.float32); img[..., 3] = 255
    img[..., :3] = (232, 226, 218)
    ir = r < 0.9
    shade = 1.0 - 0.35 * np.clip((r - 0.6) / 0.3, 0, 1)
    for k in range(3): img[..., k] = np.where(ir, iris[k] * shade * (0.9 + 0.2 * np.cos(np.arctan2(y, x) * 18) * 0.5), img[..., k])
    img[r < 0.36, :3] = (12, 10, 10)
    img[np.hypot(x + 0.12, y + 0.12) * 2 < 0.12, :3] = (250, 250, 250)
    return img.clip(0, 255).astype(np.uint8)


def save_png(arr, path, maxtex):
    im = Image.fromarray(arr)
    if max(im.size) > maxtex:
        s = maxtex / max(im.size); im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    im.save(path)
    return im


def write_material(tex, cd, roots, out, slug, maxtex, log):
    """one Source material -> vmat + png; returns (vmat path, preview texture rgb, info)"""
    rel = None
    for c in cd + ['']:
        p = vtf.find_file('materials/%s%s.vmt' % (c, tex), roots)
        if p: rel = p; break
    base = re.sub(r'[^a-z0-9_]', '_', os.path.basename(tex).lower())
    d = os.path.join(out, MAT_DIR, slug); os.makedirs(d, exist_ok=True)
    mat_rel = '%s/%s/%s' % (MAT_DIR, slug, base)
    info = {'source': tex, 'vmt': bool(rel)}
    shader, prm = ('missing', {}) if rel is None else vtf.load_vmt(rel, roots)
    info['shader'] = shader
    if prm.get('$additive', '0').strip('"') == '1':          # glows, sparks, tesla arcs: light added on top in Source; CS2's
        info['additive'] = True                              # character shader would draw them as solid sheets: left out
    def tex_of(key):
        v = prm.get(key)
        if not v: return None
        p = vtf.find_file('materials/%s.vtf' % v.replace('.vtf', ''), roots) or vtf.find_file('materials/%s.png' % v.replace('.vtf', ''), roots)
        if not p: info.setdefault('missing', []).append(v); return None
        try: return vtf.load_vtf(p)
        except Exception as e: info.setdefault('missing', []).append('%s (%s)' % (v, e)); return None
    eye = shader in ('eyerefract', 'eyes', 'teeth') and shader != 'teeth'
    col = tex_of('$iris') if shader == 'eyerefract' else None
    if col is None: col = tex_of('$basetexture')
    glass = False
    if col is None and (prm.get('$envmap') or 'glass' in tex.lower()):
        col = np.full((8, 8, 4), (40, 45, 52, 70), np.uint8); glass = True       # envmap-only lens: dark see-through glass
        info['glass'] = True
    if col is not None and col.shape[-1] == 4 and prm.get('$blendtintbybasealpha', '0').strip('"') == '1':
        # GMod's PlayerColor / TF2 team tint: the texture's alpha masks the parts tinted by a colour the game supplies at run time
        # (greyscale in the texture). CS2 has no such proxy: bake in the VMT's own tint, else GMod's default player colour.
        tint = None
        for key in ('$colortint_base', '$color2'):
            nums = re.findall(r'[-\d.]+', prm.get(key, '') or '')
            if len(nums) >= 3: tint = np.array([float(x) for x in nums[:3]]); break
        if tint is None: tint = np.array(GMOD_PLAYER_COLOR)
        if tint.max() > 1.5: tint = tint / 255.0
        a = col[..., 3:4].astype(float) / 255.0
        rgb = col[..., :3].astype(float)
        col = col.copy(); col[..., :3] = np.clip(rgb * (1 - a) + rgb * tint * a, 0, 255).astype(np.uint8); col[..., 3] = 255
        info['tinted'] = [round(float(x), 2) for x in tint]
    base_name = os.path.basename(tex).lower()
    if col is None and is_shared_eye(base_name):          # HL2's shared eyeball_l/r: models rely on the game's copy
        col = eye_standin(); eye = True; info['standin'] = 'eye'
        log('   . %s: HL2 shared eye texture not in the item, generated stand-in' % tex)
    elif col is None and is_shared_mouth(base_name):      # HL2's shared mouth/teeth/tongue
        col = np.full((8, 8, 4), (88, 38, 40, 255), np.uint8); info['standin'] = 'mouth'
        log('   . %s: HL2 shared mouth texture not in the item, dark stand-in' % tex)
    if col is None:
        col = np.full((8, 8, 4), (150, 150, 150, 255), np.uint8); info['flat'] = True
        log('   ! %s: no base texture found (%s), flat grey' % (tex, 'no vmt' if rel is None else shader))
    alphatest = prm.get('$alphatest', '0').strip('"') == '1'
    translucent = glass or prm.get('$translucent', '0').strip('"') == '1'
    nocull = prm.get('$nocull', '0').strip('"') == '1'
    lines = ['// GMod material %s (%s)' % (tex, shader), 'Layer0', '{']
    cutout = alphatest or translucent
    # csgo_character for everything: on a player model CS2 doesn't draw csgo_complex at all (in game, 6 Nov 2026: the grim reaper's
    # alpha-tested robe and Rogue were invisible); csgo_character takes F_ALPHA_TEST with TextureTranslucency
    lines.append('\tshader "csgo_character.vfx"')
    save_png(col[..., :3], os.path.join(d, base + '_color.png'), maxtex)
    lines.append('\tTextureColor "%s_color.png"' % mat_rel)
    if cutout:
        save_png(np.repeat(col[..., 3:], 3, 2), os.path.join(d, base + '_trans.png'), maxtex)
        if alphatest:
            lines += ['\tF_ALPHA_TEST 1', '\tg_flAlphaTestReference "%s"' % prm.get('$alphatestreference', '0.5').strip('"')]
        else:
            lines.append('\tF_TRANSLUCENT 1')
        lines.append('\tTextureTranslucency "%s_trans.png"' % mat_rel)
    if nocull: lines.append('\tF_RENDER_BACKFACES 1')
    nrm = tex_of('$bumpmap')
    if nrm is None and prm.get('$normalmap'): nrm = tex_of('$normalmap')
    if nrm is not None and not eye:
        n = nrm[..., :3].copy(); n[..., 1] = 255 - n[..., 1]          # Source 1 normal maps are Y- ; Source 2 wants Y+
        save_png(n, os.path.join(d, base + '_normal.png'), maxtex)
        lines.append('\tTextureNormal "%s_normal.png"' % mat_rel)
        if prm.get('$phong', '0').strip('"') == '1' and nrm[..., 3].min() < 250:
            r = (225 - nrm[..., 3].astype(np.float32) * 0.55).clip(60, 235).astype(np.uint8)      # phong mask -> roughness
            save_png(np.repeat(r[..., None], 3, 2), os.path.join(d, base + '_rough.png'), maxtex)
            lines.append('\tTextureRoughness "%s_rough.png"' % mat_rel)
        else:
            lines.append('\tTextureRoughness "[0.780000 0.780000 0.780000 0.000000]"')
    else:
        lines.append('\tTextureNormal "materials/default/default_normal.tga"')
        lines.append('\tTextureRoughness "[%s]"' % ('0.300000 0.300000 0.300000 0.000000' if eye else '0.780000 0.780000 0.780000 0.000000'))
    lines += ['\tTextureMetalness "materials/default/default_metal.tga"', '}']
    open(os.path.join(d, base + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    info.update(alphatest=alphatest, translucent=translucent, eye=eye)
    return mat_rel + '.vmat', col[..., :3], info


# ---------------------------------------------------------------- writing the mesh into a copy of the template DMX
def write_dmx(tpl, path, name, V, N, cuv, mats, sets, weights, joints=None):
    """the template's first mesh gets this geometry (one DMX vertex per input vertex), its other meshes go.
    weights: per vertex [(joint, w), ...]. Faces are re-wound counter-clockwise from the normals' side if needed."""
    agree = 0
    for faces in sets:
        f = np.asarray(faces)
        if not len(f): continue
        p = V[f]; n = N[f].sum(1)
        agree += int(np.sign((np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]) * n).sum(1)).sum())
    flipped = agree < 0
    if flipped: sets = [np.asarray(f)[:, [0, 2, 1]] for f in sets]
    UV = np.asarray(cuv, float)
    tan = np.zeros((len(V), 3))
    for faces in sets:
        f = np.asarray(faces)
        if not len(f): continue
        p0, p1, p2 = V[f[:, 0]], V[f[:, 1]], V[f[:, 2]]; t0, t1, t2 = UV[f[:, 0]], UV[f[:, 1]], UV[f[:, 2]]
        e1, e2, d1, d2 = p1 - p0, p2 - p0, t1 - t0, t2 - t0
        r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]; ok = np.abs(r) > 1e-12
        tv = np.zeros_like(e1); tv[ok] = (e1[ok] * d2[ok, 1:2] - e2[ok] * d1[ok, 1:2]) / r[ok, None]
        for k in range(3): np.add.at(tan, f[:, k], tv)
    tan -= N * (tan * N).sum(1, keepdims=True)
    ln = np.linalg.norm(tan, axis=1); bad = ln < 1e-9
    tan[bad] = np.cross(N[bad], [0, 0, 1]) + 1e-6; tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    dm = dmx9.DMX.load(tpl)
    meshes = [e for e in dm.elements if e.type == 'DmeMesh']
    mesh = meshes[0]
    vd = mesh['currentState'] or next(e for e in dm.elements if e.type == 'DmeVertexData')
    model = dm.root['model']
    gone = [c for c in model['children'] if c is not None and c.type == 'DmeDag' and any(c.get('shape') is x for x in meshes[1:])]
    if gone:
        model['children'] = [c for c in model['children'] if not any(c is g for g in gone)]
        model['jointList'] = [j for j in model['jointList'] if not any(j is g for g in gone)]
        model['baseStates'] = model['baseStates'][:len(model['baseStates']) - len(gone)]
    jidx = {j.name: i for i, j in enumerate(dm.root['skeleton']['jointList']) if j.type == 'DmeJoint'}
    if joints:            # own joints: {joint: (R world, position world)}; local position in the parent's frame, orientation kept
        def place(j, pw):
            if j.name in joints:
                pos = joints[j.name][1] if pw is None else pw[0].T @ (joints[j.name][1] - pw[1])
                old = j['transform']['position']
                try: j['transform']['position'] = type(old)(tuple(map(float, pos)))
                except Exception: j['transform']['position'] = tuple(map(float, pos))
            for c in j['children'] or []:
                if c.type == 'DmeJoint': place(c, joints.get(j.name))
        for c in dm.root['skeleton']['children']:
            if c.type == 'DmeJoint': place(c, None)
    fs0 = mesh['faceSets'][0]
    n = len(V); jc = vd['jointCount']
    vd['position$0'] = [tuple(map(float, x)) for x in V]
    vd['normal$0'] = [tuple(map(float, x)) for x in N]
    vd['texcoord$0'] = [(float(u), float(1 - v) if vd.get('flipVCoordinates') else float(v)) for u, v in UV]
    vd['tangent$0'] = [tuple(map(float, x)) + (1.0,) for x in tan]
    wts, ids = [], []
    for w in weights:
        w = w[:jc]; tot = sum(x for _, x in w) or 1.0
        wts += [x / tot for _, x in w] + [0.0] * (jc - len(w)); ids += [jidx[j] for j, _ in w] + [0] * (jc - len(w))
    vd['blendweights$0'] = wts; vd['blendindices$0'] = ids
    seq = list(range(n))
    for k in ('position$0Indices', 'normal$0Indices', 'texcoord$0Indices', 'tangent$0Indices'): vd[k] = seq
    new_sets = []
    for mat, faces in zip(mats, sets):
        fs = Element('DmeFaceSet', 'faceSet')
        for k, (t, v) in fs0.attrs.items(): fs.attrs[k] = [t, copy.copy(v)]
        me = Element('DmeMaterial', 'material')
        for k, (t, v) in fs0['material'].attrs.items(): me.attrs[k] = [t, v]
        me['mtlName'] = mat.replace('/', '\\')
        fs['material'] = me
        fl = []
        for f in np.asarray(faces).tolist(): fl += f + [-1]
        fs['faces'] = fl
        new_sets.append(fs)
    mesh['faceSets'] = new_sets
    mesh.name = name
    for e in dm.elements:
        if e.type == 'DmeDag' and e.get('shape') is mesh: e.name = name
    dm.save(path)
    return sets, flipped


# ---------------------------------------------------------------- one model
def eye_uvs(conv, eyeball, V):
    """Source projects the iris onto the eyeball: u, v = (point - eye centre) . (right, up) * iris_scale + 0.5"""
    m = conv.m
    Bw = m.bones[eyeball['bone']]['world']
    org = conv.tr_by_bone[eyeball['bone']]
    o16 = conv.G @ (Bw[:, :3] @ eyeball['org'] + Bw[:, 3]); o16[2] -= conv.floor
    o = Converter.move(o16[None], org, conv.girth)[0]
    R = org['R'] @ conv.G @ Bw[:, :3]
    fwd = unit(R @ eyeball['forward']); up = unit(R @ eyeball['up'])
    right = unit(np.cross(fwd, up)); up = unit(np.cross(right, fwd))
    s = eyeball['iris_scale'] / max(conv.girth, 1e-6)
    d = V - o
    return np.stack([0.5 + (d @ right) * s, 0.5 - (d @ up) * s], 1).clip(0.002, 0.998)


LIMB_PARAM = {}
for _s in 'LR':
    for _j, _v in ((f'arm_upper_{_s}', 0.0), (f'arm_upper_{_s}_TWIST', 0.5), (f'arm_upper_{_s}_TWIST1', 1.0), (f'arm_lower_{_s}', 1.0),
                   (f'arm_lower_{_s}_TWIST', 1.5), (f'arm_lower_{_s}_TWIST1', 2.0), (f'hand_{_s}', 2.0)):
        LIMB_PARAM[_j] = ('arm_' + _s, _v)
    for _j, _v in ((f'leg_upper_{_s}', 0.0), (f'leg_upper_{_s}_TWIST', 0.5), (f'leg_upper_{_s}_TWIST1', 1.0), (f'leg_lower_{_s}', 1.0)):
        LIMB_PARAM[_j] = ('leg_' + _s, _v)


def twist_param(w):
    """per limb: how far down its twist chain the vertex is (arm: upper arm 0..1, forearm 1..2), for vertices mostly on that limb"""
    tot = sum(x for _, x in w) or 1.0
    acc = {}
    for j, x in w:
        if j in LIMB_PARAM:
            limb, v = LIMB_PARAM[j]; a = acc.setdefault(limb, [0.0, 0.0]); a[0] += x; a[1] += x * v
    return {limb: a[1] / a[0] for limb, a in acc.items() if a[0] / tot > 0.5}


def subdivide_twist(V, N, UV, W, sets, max_step=TWIST_STEP if 'TWIST_STEP' in globals() else 0.34, passes=3):
    """Low-poly limbs with a vertex ring only at each end (e.g. a forearm: elbow ring on arm_lower, wrist ring on its TWIST1) fold into a
    flat twisted ribbon when CS2 rolls the limb. Triangles where the twist changes by more than max_step along an edge are split in four
    (shared midpoints, so no cracks; midpoint weights = the average of the ends, so the roll is spread over the new rings).
    Returns V, N, UV, W, sets and the number of triangles added."""
    V = [v for v in V]; N = [n for n in N]; UV = [u for u in UV]; W = [list(w) for w in W]
    added = 0
    for _ in range(passes):
        tp = [twist_param(w) for w in W]
        def steep(a, b):
            for k, ta in tp[a].items():
                tb = tp[b].get(k)
                if tb is not None and abs(ta - tb) > max_step: return True
            return False
        mid = {}
        def midpoint(a, b):
            key = (min(a, b), max(a, b))
            if key not in mid:
                V.append((V[a] + V[b]) / 2); n = N[a] + N[b]; N.append(n / (np.linalg.norm(n) or 1)); UV.append((np.asarray(UV[a]) + np.asarray(UV[b])) / 2)
                acc = {}
                for j, x in W[a] + W[b]: acc[j] = acc.get(j, 0.0) + x / 2
                W.append(sorted(acc.items(), key=lambda x: -x[1])[:3]); mid[key] = len(V) - 1
            return mid[key]
        new_sets, split_any = [], False
        for faces in sets:
            out = []
            for f in np.asarray(faces).tolist():
                # split only the steep edges (a neighbour sharing the edge splits it the same way: no T-junctions, no cracks)
                e = [steep(f[k], f[(k + 1) % 3]) for k in range(3)]
                n = sum(e)
                if n == 0: out.append(f); continue
                split_any = True
                if n == 3:
                    a_, b_, c_ = f; ab, bc, ca = midpoint(a_, b_), midpoint(b_, c_), midpoint(c_, a_)
                    out += [[a_, ab, ca], [ab, b_, bc], [ca, bc, c_], [ab, bc, ca]]; added += 3; continue
                k = e.index(True) if n == 1 else e.index(False)      # rotate so the special edge comes first
                a_, b_, c_ = f[k], f[(k + 1) % 3], f[(k + 2) % 3]
                if n == 1:                                            # a-b steep: two triangles
                    m = midpoint(a_, b_); out += [[a_, m, c_], [m, b_, c_]]; added += 1
                else:                                                 # b-c and c-a steep (a-b not): three triangles
                    m1, m2 = midpoint(b_, c_), midpoint(c_, a_); out += [[a_, b_, m1], [a_, m1, m2], [m2, m1, c_]]; added += 2
            new_sets.append(np.array(out, int))
        sets = new_sets
        if not split_any: break
    return np.array(V), np.array(N), np.array(UV), W, sets, added


def finger_fit(t, V, W):
    """per hand: median over finger segments of the distance (u) between the segment's skin centre and its CS2 finger bone (bone to
    next joint). Skin centred off the bone it bends about gets thrown when CS2 curls the fingers (the "wrung fingers" bug)."""
    groups = {}
    for i, w in enumerate(W):
        if not w: continue
        j = max(w, key=lambda x: x[1])[0]
        if j.startswith('finger') and '_meta_' not in j: groups.setdefault(j, []).append(i)
    out = {}
    for s_ in 'LR':
        d = []
        for j, idx in groups.items():
            if not j.endswith('_' + s_) or len(idx) < 4: continue
            k = int(j.split('_')[2]); nxt = j.replace('_%d_' % k, '_%d_' % (k + 1))
            a = t.J(j); b = t.J(nxt) if nxt in t.W else a
            c = V[idx].mean(0); ab = b - a; u = np.clip(((c - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
            d.append(np.linalg.norm(c - (a + u * ab)))
        out[s_] = round(float(np.median(d)), 2) if d else None
    return out


def eye_centre(conv):
    """mid point of the model's eyeballs on the CS2 skeleton (None if it has none)"""
    m = conv.m
    if not m.eyeballs: return None
    pts = []
    for e in m.eyeballs:
        Bw = m.bones[e['bone']]['world']
        o16 = conv.G @ (Bw[:, :3] @ e['org'] + Bw[:, 3]); o16[2] -= conv.floor
        pts.append(Converter.move(o16[None], conv.tr_by_bone[e['bone']], conv.girth)[0])
    return np.mean(pts, 0)


def head_hitbox_shift(conv, t, V, weights):
    """How far the head hit box must move to sit on this model's head (world, bind pose). The model keeps its own neck length, so its
    head isn't where a stock agent's is. From the eyes (vs CS2's eyeball joints) when the model has eyeballs, else from the centre of
    the head-weighted mesh below its top fifth (hats and hair left out) vs the stock body's."""
    e = eye_centre(conv)
    if e is not None:
        d = e - (t.J('eyeball_l') + t.J('eyeball_r')) / 2; how = 'eyes'
    else:
        def centre(P, W):
            hs = np.array([bool(w) and max(w, key=lambda x: x[1])[0].startswith('head') for w in W])
            H = P[hs]
            if len(H) < 4: return None                     # no head of its own (the B2 droid's sits in its chest)
            top = H[:, 2].max() - 0.2 * (H[:, 2].max() - H[:, 2].min())
            H = H[H[:, 2] < top]
            return (H.min(0) + H.max(0)) / 2 if len(H) else None
        c = centre(V, weights)
        if c is None:
            # no mesh on the head bone (the B2 droid: its "head" is the top block of its chest, the head bone floats in the air
            # above it): the head hit box goes on the top HEAD_TOP_BAND u of the body near the centre line, up to HEAD_HITBOX_MAX_NOHEAD
            top = V[:, 2].max()
            B = V[(V[:, 2] > top - HEAD_TOP_BAND) & (np.abs(V[:, 0]) < HEAD_TOP_BAND)]
            if len(B) < 4: return np.zeros(3), 'none (no head mesh found: stock head hit box)'
            d = (B.min(0) + B.max(0)) / 2 - centre(*t.mesh()); d[1] = 0.0
            n = np.linalg.norm(d)
            if n > HEAD_HITBOX_MAX_NOHEAD: d *= HEAD_HITBOX_MAX_NOHEAD / n
            return d, 'top of the body (no head mesh)'
        d = c - centre(*t.mesh()); how = 'head mesh'
        if hasattr(t, 'stock'): d = d - (t.J('head_0') - t.stock.J('head_0'))   # own joints: the capsule already moved with the head bone
    d[1] = 0.0                                              # stay on the centre line
    n = np.linalg.norm(d)
    if n < HEAD_HITBOX_MIN: return np.zeros(3), how + ' (within %.0f u: stock hit boxes kept)' % HEAD_HITBOX_MIN
    if n > HEAD_HITBOX_MAX: d *= HEAD_HITBOX_MAX / n
    return d, how


def shift_capsules(txt, t, bone, d):
    """move the HitboxCapsule entries on bone by world vector d (converted to the bone's bind-pose space)"""
    dl = t.W[bone][0].T @ d
    def fix(mo):
        blk = mo.group(0)
        if not re.search(r'parent_bone\s*=\s*"%s"' % re.escape(bone), blk, re.I): return blk
        def pt(m2):
            v = np.array([float(x) for x in m2.group(2).split(',')]) + dl
            return '%s[ %s ]' % (m2.group(1), ', '.join('%.3f' % x for x in v))
        return re.sub(r'(point[01]\s*=\s*)\[\s*([^\]]+)\]', pt, blk)
    return re.sub(r'_class = "HitboxCapsule".*?\}', fix, txt, flags=re.S)


LIMB_SEGMENTS = {f'{b}_{s}': f'{c}_{s}' for s in 'LR' for b, c in (('arm_upper', 'arm_lower'), ('arm_lower', 'hand'),
                                                                   ('leg_upper', 'leg_lower'), ('leg_lower', 'ankle'))}


def scale_capsules(txt, bone, k):
    """stretch the HitboxCapsule entries on a limb bone along the bone (its local x) by k: own joints with a longer or shorter limb"""
    def fix(mo):
        blk = mo.group(0)
        if not re.search(r'parent_bone\s*=\s*"%s"' % re.escape(bone), blk, re.I): return blk
        def pt(m2):
            v = np.array([float(x) for x in m2.group(2).split(',')]); v[0] *= k
            return '%s[ %s ]' % (m2.group(1), ', '.join('%.3f' % x for x in v))
        return re.sub(r'(point[01]\s*=\s*)\[\s*([^\]]+)\]', pt, blk)
    return re.sub(r'_class = "HitboxCapsule".*?\}', fix, txt, flags=re.S)


def convert(mdl_path, slug, roots, template, out, skin=0, choices=None, maxtex=2048, preview=None, log=print, mode='rigid'):
    m = SrcModel(mdl_path)
    t = Template(template) if isinstance(template, str) else template
    conv = Converter(m, t, log)
    conv.transforms(mode)
    if mode == 'own':                    # CS2's joints move to the model's own (skin weights, checks, previews, the DMX)
        t = own_template(t, conv.own_joints); conv.t = t
    meshes = m.default_meshes(choices)
    used, remap, V, N, weights = conv.convert_mesh(meshes)
    # fit checks against a stock agent body: chest depth and hands in CS2's preview pose
    chest_t = t.chest(); chest_m = t.chest(V) or chest_t      # no chest mesh: no chest check
    hands = t.hands_in_torso(V, weights)
    warnings = []
    extra = chest_m[0] - chest_t[0]
    if extra > CHEST_WARN:
        warnings.append('bulky torso: chest %.1f u further forward than a stock agent; CS2 hand poses (two-handed weapons) will clip into it' % extra)
    for side in 'LR':
        if hands[side] is not None and hands[side] > HAND_WARN:
            warnings.append('hand_%s inside the torso in the CS2 preview pose (chest surface %.1f u in front of the wrist)' % (side, hands[side]))
    far = {j: d for j, d in (getattr(conv, 'joint_offsets', None) or {}).items() if j.startswith(('arm_', 'leg_', 'hand_', 'ankle_')) and d > LIMB_WARN and mode != 'own'}
    if far: warnings.append('skeleton does not match CS2 (limb joints more than %.0f u off: %s): CS2 will bend the limbs away from the joints of the model'
                            % (LIMB_WARN, ', '.join('%s %.1f' % kv for kv in sorted(far.items()))))
    fingers = finger_fit(t, V, weights)
    for side, v in fingers.items():
        if v is not None and v > FINGER_WARN:
            warnings.append('hand_%s fingers sit %.1f u from their CS2 finger bones: CS2 finger curls will distort them' % (side, v))
    for side in getattr(conv, 'unaligned_hands', []):
        warnings.append('hand_%s not aligned to CS2 (the rig has no index finger plus an outer finger): fingers will bend about the wrong points' % side)
    for w_ in warnings: log('   WARNING: ' + w_)
    UV = m.UV[used].copy()
    fam = m.skins[skin] if skin < len(m.skins) else m.skins[0]
    by_mat, texs, infos = {}, {}, []
    for me in meshes:
        if not len(me['tris']): continue
        ti = fam[me['material']] if me['material'] < len(fam) else me['material']
        tex = m.textures[ti]
        if tex not in by_mat:
            mat, rgb, info = write_material(tex, m.cdtextures, roots, out, slug, maxtex, log)
            by_mat[tex] = (mat, []); texs[tex] = rgb; infos.append(info)
        if infos[[i['source'] for i in infos].index(tex)].get('additive'):
            continue                                         # additive effect material (glow, arcs): not drawn, see write_material
        tri = remap[me['tris']]
        by_mat[tex][1].append(tri)
        if me['eyeball'] >= 0 and infos[[i['source'] for i in infos].index(tex)].get('eye'):
            vs = np.unique(tri.ravel())
            UV[vs] = eye_uvs(conv, m.eyeballs[me['eyeball']], V[vs])
    for k in [k for k in by_mat if not by_mat[k][1]]:
        log('   . %s: additive effect material, left out' % k); del by_mat[k]
    names = list(by_mat)
    mats = [by_mat[k][0] for k in names]; sets = [np.vstack(by_mat[k][1]) for k in names]
    sets_src = sets                      # the source mesh's own triangles (for the GMod-pose preview)
    if TWIST_STEP > 0:
        V, N, UV, weights, sets, n_sub = subdivide_twist(V, N, UV, weights, sets, TWIST_STEP)
        if n_sub: log('   . %d triangles added along low-poly limbs (twist spread)' % n_sub)
    else: n_sub = 0
    d = os.path.join(out, MODEL_DIR, slug); os.makedirs(d, exist_ok=True)
    sets, flipped = write_dmx(t.body, os.path.join(d, slug + '_body.dmx'), 'gmod_%s_body' % slug, V, N, UV, mats, sets, weights,
                              joints=t.W if mode == 'own' else None)
    # shared first-person arms, sleeves and preview pose: the template's
    sh = os.path.join(out, MODEL_DIR, 'shared'); os.makedirs(sh, exist_ok=True)
    for sfx, dst in (('_firstperson_arms.dmx', 'firstperson_arms.dmx'), ('_firstperson_sleeves.dmx', 'firstperson_sleeves.dmx'), ('_tools_preview.dmx', 'tools_preview.dmx')):
        if not os.path.exists(os.path.join(sh, dst)): shutil.copy(t.file(sfx), os.path.join(sh, dst))
    txt = open(t.vmdl, encoding='utf-8').read()
    hd, hhow = head_hitbox_shift(conv, t, V, weights)
    if mode == 'own':                    # limb capsules stretched to the model's own limb lengths
        for b, c in LIMB_SEGMENTS.items():
            k = np.linalg.norm(t.J(c) - t.J(b)) / max(1e-6, np.linalg.norm(t.stock.J(c) - t.stock.J(b)))
            if abs(k - 1) > 0.02: txt = scale_capsules(txt, b, float(np.clip(k, 0.6, 1.6)))
    txt = shift_capsules(txt, t, 'head_0', hd)
    txt = shift_capsules(txt, t, 'neck_0', hd * 0.5)
    import hitboxes
    hit = hitboxes.fit(t, V, weights, hitboxes.capsules(txt))
    def swap(name, path):
        nonlocal txt
        t2 = re.sub(r'(name = "%s"\s*\n\s*filename = ")[^"]+(")' % re.escape(name), r'\g<1>%s\g<2>' % path, txt)
        assert t2 != txt, 'template vmdl has no render mesh named ' + name
        txt = t2
    swap('thirdperson_body', '%s/%s/%s_body.dmx' % (MODEL_DIR, slug, slug))
    swap('firstperson_default_gloves_arms', MODEL_DIR + '/shared/firstperson_arms.dmx')
    swap('firstperson_sleeves', MODEL_DIR + '/shared/firstperson_sleeves.dmx')
    txt = re.sub(r'(source_filename = ")[^"]*_tools_preview\.dmx(")', r'\g<1>%s/shared/tools_preview.dmx\g<2>' % MODEL_DIR, txt)
    stray = sorted(set(re.findall(r'"([^"]*\.(?:dmx|vmat|fbx|smd))"', txt)) - {
        '%s/%s/%s_body.dmx' % (MODEL_DIR, slug, slug), MODEL_DIR + '/shared/firstperson_arms.dmx',
        MODEL_DIR + '/shared/firstperson_sleeves.dmx', MODEL_DIR + '/shared/tools_preview.dmx'})
    assert not stray, 'template vmdl still points at %s' % stray
    head = '// %s: converted from the GMod model %s by create/playermodels/gmod2cs2.py\n' % (slug, m.name)
    vm = txt.split('\n', 1)
    open(os.path.join(d, slug + '.vmdl'), 'w', encoding='utf-8', newline='\n').write(vm[0] + '\n' + head + vm[1])
    rep = {'slug': slug, 'source_mdl': m.name, 'mdl_version': m.version, 'vertices': int(len(V)),
           'triangles': int(sum(len(s) for s in sets)), 'materials': infos, 'source_height': round(conv.height, 1),
           'source_eye_height': round(conv.height_head, 1), 'scale': round(conv.girth, 3), 'yaw_turned_deg': round(-conv.yaw_deg, 1),
           'mode': mode, 'warnings': warnings, 'twist_subdivided_tris': n_sub, 'finger_fit': fingers, 'head_hitbox_shift': [round(float(x), 2) for x in hd], 'head_hitbox_from': hhow, 'hitbox_fit': hit, 'chest_front_vs_stock': round(extra, 2), 'chest_shift': round(getattr(conv, 'chest_shift', 0.0), 2), 'hands_in_torso': hands, 'joint_offsets': getattr(conv, 'joint_offsets', None), 'hand_scale': getattr(conv, 'hand_scale', None), 'bones_following_parent': conv.unknown, 'winding_flipped': bool(flipped),
           'vmdl': '%s/%s/%s.vmdl' % (MODEL_DIR, slug, slug)}
    if preview:
        from preview import render
        os.makedirs(preview, exist_ok=True)
        groups = [(np.asarray(f), texs[k]) for f, k in zip(sets, names)]
        marks = np.array([t.J(n) for n in t.joints if not any(x in n for x in ('TWIST', 'finger', 'eye', 'wpn', 'root', 'jiggle', 'scap'))])
        lo = np.minimum(V.min(0), [-20, -40, 0]); hi = np.maximum(V.max(0), [20, 40, 76])
        render(V, UV, groups, os.path.join(preview, slug + '_bind.png'), views=('front', 'side', 'back'), H=700, marks=marks,
               label='%s  bind pose on the CS2 skeleton (dots = CS2 joints)' % slug, box=(lo, hi))
        Wp = t.preview_pose()
        Q = np.zeros_like(V)
        for i, w in enumerate(weights):
            tot = sum(x for _, x in w) or 1
            for j, x in w:
                Rb, tb = t.W[j]; Rp, tp_ = Wp[j]
                Q[i] += x / tot * (Rp @ (Rb.T @ (V[i] - tb)) + tp_)
        render(Q, UV, groups, os.path.join(preview, slug + '_posed.png'), views=('front', 'three', 'side'), H=700,
               label='%s  skinned to the template preview pose' % slug)
        import poses                     # every pose on one sheet: shooting (CS2's), run, crouch, arms up, twist; textured
        poses.pose_sheet(t, V, UV, groups, weights, os.path.join(preview, slug + '_poses.png'), slug)
        # the source model as it was (turned to face +X), for comparison
        V0 = m.V[used] @ conv.G.T; V0[:, 2] -= conv.floor
        render(V0, m.UV[used], [(np.asarray(f), texs[k]) for f, k in zip(sets_src, names)], os.path.join(preview, slug + '_source.png'), views=('front', 'side'), H=700,
               label='%s  GMod reference pose (%.1f u tall)' % (slug, conv.height))
    return rep


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('mdl'); ap.add_argument('slug')
    ap.add_argument('--roots', required=True); ap.add_argument('--template', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--skin', type=int, default=0); ap.add_argument('--bodygroup', action='append', default=[])
    ap.add_argument('--fit', action='store_true', help='old method: stretch pieces onto CS2 bone lengths'); ap.add_argument('--own', action='store_true', help="CS2's joints at the model's own joints"); ap.add_argument('--maxtex', type=int, default=2048); ap.add_argument('--preview'); ap.add_argument('--report')
    a = ap.parse_args()
    ch = {k: int(v) for k, v in (b.split('=') for b in a.bodygroup)}
    rep = convert(a.mdl, a.slug, a.roots.split(','), a.template, a.out, a.skin, ch, a.maxtex, a.preview, mode='fit' if a.fit else 'own' if a.own else 'rigid')
    js = json.dumps(rep, indent=1)
    if a.report: open(a.report, 'w').write(js)
    print(js)
