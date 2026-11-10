"""Patch onto the mapper's map: WALKABLESEED nav seeds (group ifr_nav) and Low vis hints round the train tunnels (group ifr_vis),
both arenas. Re-runnable (both groups are replaced). usage: python -I tools/patch_nav_vis.py <map as saved in Hammer> <out .vmap>
Tunnel boxes were read from the mapper's meshes (walls/portals at z 256..1088); the existing ifr_gen hints (Lowest all, Lower per arena)
stay, the Low boxes refine the tunnel interiors."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create'))); sys.path.insert(0, HERE)
import vmapgen as G

DZ = -8664.0
TUNNELS = [(-6100, -6750, -4900, -4900), (-6100, 4900, -4900, 6700), (-4300, -1050, -2050, -130), (4650, 4300, 6080, 6100), (2450, -750, 4520, 1150)]
# (x, y, ground z of arena 1) from the drops: ground = drop z - 1500
ARENA_NAV = False   # True: seeds on the arena ground flood the whole 14000 u terrain (96k polys) and the nav build then ran > 3 h (9 Nov 2026); the bot pawns only need the booth
SEEDS = [(-5600, -3500, 270), (-5600, 500, 295), (5600, -3500, 295), (5600, 500, 263)]

def main(src, out):
    d = G.open_map(src, '')
    kids = G.world_of(d).attr('children')
    old = [c for c in kids[2] if c.get('customVisGroup', '') in ('ifr_nav', 'ifr_vis')]
    kids[2] = [c for c in kids[2] if c not in old]
    for off in (0.0, DZ):
        for (x0, y0, x1, y1) in TUNNELS:
            G.hint((x0, y0, 200 + off, x1, y1, 1500 + off), 'Low', group='ifr_vis')
        for (x, y, gz) in (SEEDS if ARENA_NAV else []):
            G.nav_seed((x - 80, y - 80, gz - 100 + off, x + 80, y + 80, gz + 100 + off), group='ifr_nav')
    for y in (-300, 300):
        G.nav_seed((-100, y - 100, -12000, 100, y + 100, -11960), group='ifr_nav')
    G.finish(d, out, group=None, first_run_cleanup=False)
    print('replaced %d old nodes; added %d hints, %d nav seeds -> %s' % (len(old), 2 * len(TUNNELS), (2 * len(SEEDS) if ARENA_NAV else 0) + 2, out))

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
