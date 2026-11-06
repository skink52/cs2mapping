"""Stock CS2 agents as hat references: the JSON written by create/s2/agent_mesh.mjs (skeleton bind pose + third-person meshes,
Valve data: kept in <work>/agents/, out of git).

    a = Agent('<work>/agents/tm_professional_varf.json')
    a.world['head_0'] -> (R 3x3, t 3)   bind pose, model space (CS2 agents face +X, Z up)
    a.meshes  [{'material', 'P' (n,3), 'N', 'UV' (n,2), 'I' (m,3), 'J' (n,4), 'W' (n,4)}]
    a.head()  the head's vertices (>= 50 % on head_0 or the eyes), and its measures
"""
import base64, json
import numpy as np


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _arr(s, dt, cols):
    a = np.frombuffer(base64.b64decode(s), dt)
    return a.reshape(-1, cols) if cols > 1 else a


class Agent:
    def __init__(self, path):
        d = json.load(open(path, encoding='utf-8'))
        self.path = path
        self.bones = d['skeleton']
        self.names = [b['name'] for b in self.bones]
        self.world = {}
        W = []
        for b in self.bones:
            R, t = quat_mat(b['quat']), np.array(b['pos'], float)
            if b['parent'] >= 0:
                Rp, tp = W[b['parent']]
                R, t = Rp @ R, Rp @ t + tp
            W.append((R, t)); self.world[b['name']] = (R, t)
        self.meshes = []
        for m in d['meshes']:
            self.meshes.append({'material': m['material'], 'P': _arr(m['P'], '<f4', 3).astype(float), 'N': _arr(m['N'], '<f4', 3).astype(float),
                                'UV': _arr(m['UV'], '<f4', 2).astype(float), 'J': _arr(m['J'], '<u2', 4).astype(int),
                                'W': _arr(m['W'], '<f4', 4).astype(float), 'I': _arr(m['I'], '<u4', 3).astype(int)})

    def body_meshes(self):
        return [m for m in self.meshes if 'glove' not in m['material'] and 'firstperson' not in m['material']]

    def head(self):
        """vertices mostly on head_0 / eyes (all body meshes), plus measures: top, eye centre, width, depth"""
        hj = [i for i, n in enumerate(self.names) if n in ('head_0', 'eyeball_l', 'eyeball_r', 'eye_target') or n.startswith(('face_', 'jaw', 'lip', 'brow'))]
        pts = []
        for m in self.body_meshes():
            w = np.zeros(len(m['P']))
            for k in range(4): w += np.where(np.isin(m['J'][:, k], hj), m['W'][:, k], 0)
            pts.append(m['P'][w > 0.5])
        P = np.vstack(pts)
        eye = (self.world['eyeball_l'][1] + self.world['eyeball_r'][1]) / 2 if 'eyeball_l' in self.world else None
        return P, {'top': float(P[:, 2].max()), 'eye': eye, 'lo': P.min(0), 'hi': P.max(0)}
