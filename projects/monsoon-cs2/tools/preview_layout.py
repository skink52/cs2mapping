"""Top-down preview of layout.py: hillshaded height, water, roads, zones, flags, karst, paddies. usage: preview_layout.py out.png [cell=32]"""
import sys, math
import numpy as np
from PIL import Image, ImageDraw
import layout as L

def main(out, cell=32):
    xs = np.arange(-L.TERRAIN_X, L.TERRAIN_X + cell, cell, dtype=float); ys = np.arange(-L.TERRAIN_Y, L.TERRAIN_Y + cell, cell, dtype=float)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    Z = L.height(X, Y)
    print('height range %.0f .. %.0f' % (Z.min(), Z.max()))
    # hillshade
    dzdx = np.gradient(Z, cell, axis=0); dzdy = np.gradient(Z, cell, axis=1)
    nx, ny, nz = -dzdx, -dzdy, np.ones_like(Z); l = np.sqrt(nx*nx+ny*ny+nz*nz); nx/=l; ny/=l; nz/=l
    sun = np.array([-0.5, -0.3, 0.8]); sun /= np.linalg.norm(sun)
    sh = np.clip(nx*sun[0]+ny*sun[1]+nz*sun[2], 0, 1)
    # colour by height + paint
    sl = L.grid_slope(Z, cell)
    w, tint = L.paint_weight(X, Y, Z, sl)
    mud = np.array([0.42, 0.33, 0.22]); grass = np.array([0.38, 0.52, 0.22]); rock = np.array([0.55, 0.55, 0.50])
    col = mud[None,None]*(1-w[...,None]) + grass[None,None]*w[...,None]
    col = col*(1-np.clip((sl-30)/20,0,1))[...,None] + rock*np.clip((sl-30)/20,0,1)[...,None]
    j = L.jungle(X, Y); col = col*(1-0.45*j[...,None]) + np.array([0.08,0.22,0.06])*(0.45*j[...,None])
    g = L.grass(X, Y); col = col*(1-0.3*g[...,None]) + np.array([0.6,0.62,0.3])*(0.3*g[...,None])
    col = col*(0.45+0.65*sh[...,None])*tint[...,None]
    water = Z < L.WATER_Z - 1
    up = (X < L.FALL_X) & (Z < L.UPPER_WATER_Z - 1)
    col[water | up] = np.array([0.25, 0.42, 0.55])
    # paddy water
    yr = Y - L.river_y(X)
    img = (np.clip(col, 0, 1)*255).astype(np.uint8)
    im = Image.fromarray(np.transpose(img, (1, 0, 2))[::-1])   # x right, y up
    d = ImageDraw.Draw(im)
    def px(x, y): return ((x + L.TERRAIN_X) / cell, (L.TERRAIN_Y - y) / cell)
    for hw, pts in L.ROADS:
        d.line([px(*p) for p in pts], fill=(200, 170, 110), width=max(1, int(2*hw/cell)))
    for (kx, ky, kr, kh, ks) in L.KARST:
        x0, y0 = px(kx - kr, ky + kr); x1, y1 = px(kx + kr, ky - kr); d.ellipse([x0, y0, x1, y1], outline=(230, 230, 230), width=2)
    for l, n, c in L.FLAGS:
        x0, y0 = px(c[0] - L.FLAG_R, c[1] + L.FLAG_R); x1, y1 = px(c[0] + L.FLAG_R, c[1] - L.FLAG_R)
        d.ellipse([x0, y0, x1, y1], outline=(255, 220, 60), width=2); d.text(px(c[0] - 60, c[1] + 40), l.upper() + ' ' + n, fill=(255, 255, 200))
    for c, r, name in ((L.CT_BASE, L.CT_PLATEAU_R, 'CT firebase'), (L.T_BASE, L.T_PLATEAU_R, 'T camp')):
        x0, y0 = px(c[0] - r, c[1] + r); x1, y1 = px(c[0] + r, c[1] - r); d.ellipse([x0, y0, x1, y1], outline=(255, 90, 90), width=2); d.text(px(c[0]-120, c[1]+r+60), name, fill=(255, 160, 160))
    # play space
    d.rectangle([px(-L.MAP_X, L.MAP_Y), px(L.MAP_X, -L.MAP_Y)], outline=(255, 255, 255), width=1)
    im.save(out); print('wrote', out, im.size)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '../out/layout_preview.png', int(sys.argv[2]) if len(sys.argv) > 2 else 32)
