import json,struct,io,numpy as np
from PIL import Image
CT={5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
NC={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def quat_mat(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def node_mat(n):
    if 'matrix' in n: return np.array(n['matrix']).reshape(4,4).T
    M=np.eye(4)
    R=quat_mat(n.get('rotation',[0,0,0,1]));S=np.diag(n.get('scale',[1,1,1]))
    M[:3,:3]=R@S;M[:3,3]=n.get('translation',[0,0,0]);return M
class GLB:
    def __init__(s,path):
        d=open(path,'rb').read();l=struct.unpack('<I',d[12:16])[0]
        s.j=json.loads(d[20:20+l]);o=20+l;bl=struct.unpack('<I',d[o:o+4])[0];s.bin=d[o+8:o+8+bl]
        j=s.j;s.world={}
        par={}
        for i,n in enumerate(j['nodes']):
            for c in n.get('children',[]):par[c]=i
        def W(i):
            if i in s.world:return s.world[i]
            M=node_mat(j['nodes'][i]);
            if i in par:M=W(par[i])@M
            s.world[i]=M;return M
        for i in range(len(j['nodes'])):W(i)
        s.parent=par
    def acc(s,i):
        a=s.j['accessors'][i];bv=s.j['bufferViews'][a['bufferView']]
        dt=CT[a['componentType']];nc=NC[a['type']]
        off=bv.get('byteOffset',0)+a.get('byteOffset',0);st=bv.get('byteStride',0)
        isz=np.dtype(dt).itemsize*nc
        if st and st!=isz:
            raw=np.frombuffer(s.bin,np.uint8,a['count']*st,off).reshape(a['count'],st)[:,:isz].copy()
            arr=raw.view(dt).reshape(a['count'],nc)
        else: arr=np.frombuffer(s.bin,dt,a['count']*nc,off).reshape(a['count'],nc)
        if a.get('normalized'):arr=arr.astype(np.float32)/np.iinfo(dt).max
        return arr.copy()
    def image(s,i):
        im=s.j['images'][i];bv=s.j['bufferViews'][im['bufferView']]
        return Image.open(io.BytesIO(s.bin[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']]))
    def mesh(s):
        """first mesh node: world positions(not skinned), uv, faces, joints, weights"""
        j=s.j
        ni=next(i for i,n in enumerate(j['nodes']) if 'mesh' in n)
        P=[];UV=[];F=[];JO=[];WE=[];N=[];base=0
        for p in j['meshes'][j['nodes'][ni]['mesh']]['primitives']:
            at=p['attributes'];v=s.acc(at['POSITION']);P.append(v)
            UV.append(s.acc(at['TEXCOORD_0']) if 'TEXCOORD_0' in at else np.zeros((len(v),2)))
            N.append(s.acc(at['NORMAL']) if 'NORMAL' in at else np.zeros_like(v))
            if 'JOINTS_0' in at:JO.append(s.acc(at['JOINTS_0']));WE.append(s.acc(at['WEIGHTS_0']))
            F.append(s.acc(p['indices']).reshape(-1,3)+base);base+=len(v)
        r=dict(node=ni,P=np.vstack(P),UV=np.vstack(UV),N=np.vstack(N),F=np.vstack(F))
        if JO:r['J']=np.vstack(JO).astype(int);r['W']=np.vstack(WE)
        return r
    def material_images(s):
        m=s.j['materials'][0];pb=m.get('pbrMetallicRoughness',{})
        out={}
        def t(k,d): 
            if k in d: out[k]=s.j['textures'][d[k]['index']]['source']
        t('baseColorTexture',pb);t('metallicRoughnessTexture',pb);t('normalTexture',m);t('occlusionTexture',m);t('emissiveTexture',m)
        return out
def splat(P,C,view,W=600,H=800,pad=0.05):
    """orthographic point splat. view: 2x3 axes matrix + depth axis"""
    ax,ay,az=view
    x=P@ax;y=P@ay;z=P@az
    lo=np.array([x.min(),y.min()]);hi=np.array([x.max(),y.max()]);sc=min(W,H)*(1-2*pad)/max(hi-lo)
    px=((x-lo[0])*sc+W*pad).astype(int);py=(H-((y-lo[1])*sc+H*pad)).astype(int)
    ok=(px>=0)&(px<W)&(py>=0)&(py<H);o=np.argsort(z[ok]);img=np.full((H,W,3),40,np.uint8)
    img[py[ok][o],px[ok][o]]=C[ok][o];return Image.fromarray(img)


def load_skinned(path):
    """skinned glTF character: (GLB, mesh dict, joint names without 'mixamorig:', parent map, dense weights [V x J])"""
    g = GLB(path); sk = g.j['skins'][0]; m = g.mesh()
    names = [g.j['nodes'][i]['name'].split(':')[-1] for i in sk['joints']]
    jn = {i: k for k, i in enumerate(sk['joints'])}
    parent = {}
    for k, i in enumerate(sk['joints']):
        p = g.parent.get(i); parent[names[k]] = names[jn[p]] if p in jn else None
    Wd = np.zeros((len(m['P']), len(names)))
    for c in range(m['J'].shape[1]): np.add.at(Wd, (np.arange(len(m['P'])), m['J'][:, c]), m['W'][:, c])
    return g, m, names, parent, Wd


def joints_from_weights(P, names, parent, Wd):
    """bind-pose joint positions estimated where each bone's weights meet its parent's (works when the
    exported skeleton transforms are missing); joints with no shared region are left out"""
    idx = {n: i for i, n in enumerate(names)}; J = {}
    for n in names:
        p = parent[n]
        if p is None: continue
        w = np.minimum(Wd[:, idx[n]], Wd[:, idx[p]])
        if w.sum() > 1e-6: J[n] = (P * w[:, None]).sum(0) / w.sum()
    return J


def joints_bind(g, names):
    """bind-pose joint positions from the inverse bind matrices, or None if they are unusable"""
    sk = g.j['skins'][0]
    try:
        IBM = g.acc(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        ok = all(abs(np.linalg.det(M[:3, :3])) > 1e-6 and np.isfinite(M).all() for M in IBM)
        errs = max(np.abs(g.world[ji] @ IBM[k] - np.eye(4)).max() for k, ji in enumerate(sk['joints']))
    except Exception:
        return None
    if not ok or errs > 1e-3: return None
    return {n: g.world[ji][:3, 3].copy() for n, ji in zip(names, sk['joints'])}
