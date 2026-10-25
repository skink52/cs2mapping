"""Write Source 2 ModelDoc mesh DMX files (binary 9 / model 22), laid out like Source 2 Viewer exports."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx
from dmx import Element, Attr, T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_VEC2, T_VEC3, T_VEC4, T_QUAT, AOFF

def transform(name, pos=(0,0,0), orient=(0,0,0,1)):
    e = Element('DmeTransform', name)
    e.set('position', T_VEC3, tuple(float(x) for x in pos)); e.set('orientation', T_QUAT, tuple(float(x) for x in orient)); return e

def arr(t, items): return (AOFF + t, Attr(t, items))

def joint(name, pos, children=()):
    j = Element('DmeJoint', name)
    j.set('transform', T_ELEMENT, transform(name, pos)); j.set('shape', T_ELEMENT, None); j.set('visible', T_BOOL, 1)
    j.attrs['children'] = arr(T_ELEMENT, list(children)); return j

def flatten(j, out):
    out.append(j)
    for c in j['children'].items: flatten(c, out)
    return out

def build_model(name, joints, mesh_name, V, N, T, TAN, F, blend, mtl, hull=False):
    """joints: list of root DmeJoint elements (tree). blend: per-vertex joint index into the flattened joint list."""
    model = Element('DmeModel', name)
    model.set('transform', T_ELEMENT, transform('')); model.set('shape', T_ELEMENT, None); model.set('visible', T_BOOL, 1)
    jl = []
    for j in joints: flatten(j, jl)
    dag = Element('DmeDag', mesh_name)
    dag.set('transform', T_ELEMENT, transform(''));
    mesh = Element('DmeMesh', mesh_name)
    mesh.set('visible', T_BOOL, 1); mesh.set('bindState', T_ELEMENT, None)
    vd = Element('DmeVertexData', 'bind')
    n = len(V); idx = np.arange(n, dtype=np.int32)
    if hull:
        vd.attrs['vertexFormat'] = arr(T_STRING, ['position$0']); vd.set('jointCount', T_INT, 0); vd.set('flipVCoordinates', T_BOOL, 0)
        vd.attrs['position$0'] = arr(T_VEC3, np.asarray(V, np.float32)); vd.attrs['position$0Indices'] = arr(T_INT, idx)
    else:
        skinned = blend is not None
        vd.attrs['vertexFormat'] = arr(T_STRING, ['position$0', 'texcoord$0', 'normal$0', 'tangent$0'] + (['blendindices$0', 'blendweights$0'] if skinned else []))
        vd.set('jointCount', T_INT, 1 if skinned else 0); vd.set('flipVCoordinates', T_BOOL, 0)
        vd.attrs['position$0'] = arr(T_VEC3, np.asarray(V, np.float32)); vd.attrs['position$0Indices'] = arr(T_INT, idx)
        vd.attrs['texcoord$0'] = arr(T_VEC2, np.asarray(T, np.float32)); vd.attrs['texcoord$0Indices'] = arr(T_INT, idx)
        vd.attrs['normal$0'] = arr(T_VEC3, np.asarray(N, np.float32)); vd.attrs['normal$0Indices'] = arr(T_INT, idx)
        vd.attrs['tangent$0'] = arr(T_VEC4, np.asarray(TAN, np.float32)); vd.attrs['tangent$0Indices'] = arr(T_INT, idx)
        if skinned: vd.attrs['blendindices$0'] = arr(T_INT, np.asarray(blend, np.int32)); vd.attrs['blendweights$0'] = arr(T_FLOAT, np.ones(n, np.float32))
    mesh.set('currentState', T_ELEMENT, vd); mesh.attrs['baseStates'] = arr(T_ELEMENT, [vd]); mesh.attrs['deltaStates'] = arr(T_ELEMENT, [])
    def faceset(Fs, mtlname, label):
        fs = Element('DmeFaceSet', label)
        if isinstance(Fs, list): faces = np.array([i for poly in Fs for i in list(poly) + [-1]], np.int32)
        else: faces = np.hstack([np.asarray(Fs, np.int32), np.full((len(Fs), 1), -1, np.int32)]).reshape(-1)
        fs.attrs['faces'] = arr(T_INT, faces)
        mat = Element('DmeMaterial', 'material'); mat.set('mtlName', T_STRING, mtlname); fs.set('material', T_ELEMENT, mat); return fs
    if isinstance(mtl, list):   # [(face mask, mtlname), ...]
        sets = [faceset(np.asarray(F)[mask], m, f'{m}') for mask, m in mtl if mask.any()]
    else:
        sets = [faceset(F, mtl, 'hull faces' if hull else f'0..{len(F)}')]
    mesh.attrs['faceSets'] = arr(T_ELEMENT, sets)
    mesh.attrs['deltaStateWeights'] = arr(T_VEC2, np.zeros((0, 2), np.float32)); mesh.attrs['deltaStateWeightsLagged'] = arr(T_VEC2, np.zeros((0, 2), np.float32))
    dag.set('shape', T_ELEMENT, mesh); dag.set('visible', T_BOOL, 1); dag.attrs['children'] = arr(T_ELEMENT, [])
    model.attrs['children'] = arr(T_ELEMENT, list(joints) + [dag])
    model.attrs['jointList'] = arr(T_ELEMENT, jl + [dag])
    tl = Element('DmeTransformsList', ''); tl.attrs['transforms'] = arr(T_ELEMENT, [transform('')])
    model.attrs['baseStates'] = arr(T_ELEMENT, [tl])
    ax = Element('DmeAxisSystem', ''); ax.set('upAxis', T_INT, 3); ax.set('forwardParity', T_INT, 1); ax.set('coordSys', T_INT, 0)
    model.set('axisSystem', T_ELEMENT, ax)
    root = Element('DmElement', 'root')
    root.set('skeleton', T_ELEMENT, model); root.set('model', T_ELEMENT, model)
    tags = Element('DmeExportTags', 'exportTags'); tags.set('source', T_STRING, 'ww1 weapon builder'); root.set('exportTags', T_ELEMENT, tags)
    return root

def write_model(path, root): dmx.write(path, root)
