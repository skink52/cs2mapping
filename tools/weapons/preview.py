import sys, numpy as np; sys.path.insert(0,'/home/claude/fbx')
import dmx
from PIL import Image
def render(V, F, cols, ax, ay, dz, xr, yr, scale, fn):
    W = int((xr[1]-xr[0])*scale); H = int((yr[1]-yr[0])*scale)
    img = np.zeros((H, W, 3), np.uint8) + 25; zbuf = np.full((H, W), -1e9)
    P = np.stack([(V[:,ax]-xr[0])*scale, H-(V[:,ay]-yr[0])*scale], 1); depth = V[:,dz[0]]*dz[1]
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    for k, (a,b,c) in enumerate(F):
        pa, pb, pc = P[a], P[b], P[c]
        x0, x1 = int(max(0, min(pa[0],pb[0],pc[0]))), int(min(W-1, max(pa[0],pb[0],pc[0])))+1
        y0, y1 = int(max(0, min(pa[1],pb[1],pc[1]))), int(min(H-1, max(pa[1],pb[1],pc[1])))+1
        if x1 <= x0 or y1 <= y0: continue
        n = np.cross(V[b]-V[a], V[c]-V[a]); ln = np.linalg.norm(n)
        if ln < 1e-9: continue
        sh = 0.35 + 0.65*max(0, abs(np.dot(n/ln, light)))
        xs, ys = np.meshgrid(np.arange(x0, x1)+0.5, np.arange(y0, y1)+0.5)
        d = (pb[0]-pa[0])*(pc[1]-pa[1]) - (pc[0]-pa[0])*(pb[1]-pa[1])
        if abs(d) < 1e-9: continue
        w1 = ((pb[0]-xs)*(pc[1]-ys) - (pc[0]-xs)*(pb[1]-ys)) / d; w2 = ((pc[0]-xs)*(pa[1]-ys) - (pa[0]-xs)*(pc[1]-ys)) / d; w3 = 1-w1-w2
        m = (w1 >= 0) & (w2 >= 0) & (w3 >= 0); z = w1*depth[a] + w2*depth[b] + w3*depth[c]
        sub = zbuf[y0:y1, x0:x1]; upd = m & (z > sub)
        img[y0:y1, x0:x1][upd] = (np.array(cols[k]) * sh).astype(np.uint8); sub[upd] = z[upd]
    Image.fromarray(img).save(fn)
palette = {'scope.vmat': (60, 62, 68), 'brass.vmat': (190, 150, 70)}
def preview(name, out='/tmp', scale=30, span=(3, 30)):
    h, els = dmx.read(f'/home/claude/out2/models/weapons/ww1/{name}/{name}_body.dmx')
    mesh = [e for e in els if e.type == 'DmeMesh'][0]; V = mesh['currentState']['position$0'].items.astype(float)
    F = []; cols = []
    for fs in mesh['faceSets'].items:
        mt = fs['material']['mtlName'].split('/')[-1]; tri = fs['faces'].items.reshape(-1, 4)[:, :3]; F.append(tri); cols += [palette.get(mt, (120, 85, 50))] * len(tri)
    F = np.vstack(F); xm = V[:,0].min()
    render(V, F, cols, 0, 2, (1, 1), (xm+span[0], xm+span[1]), (V[:,2].mean()-6, V[:,2].mean()+6), scale, f'{out}/{name}_left.png')
    render(V, F, cols, 0, 2, (1, -1), (xm+span[0], xm+span[1]), (V[:,2].mean()-6, V[:,2].mean()+6), scale, f'{out}/{name}_right.png')
    render(V, F, cols, 0, 1, (2, 1), (xm+span[0], xm+span[1]), (V[:,1].min()-1, V[:,1].max()+1), scale, f'{out}/{name}_top.png')
if __name__ == '__main__':
    for n in sys.argv[1:]: preview(n)
