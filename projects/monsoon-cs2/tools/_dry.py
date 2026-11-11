"""scratch: places + entities without the terrain build, with a profile"""
import sys, os, time, cProfile, pstats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapgen as G, layout as L, mv_terrain as TER, mv_places as PL
d = G.open_map('../out/template.vmap', os.path.abspath('../out/addon'))
clone = lambda cls, origin, angles=(0, 0, 0), **k: G.clone(d, cls, origin, angles, 'mv_gen', **k)
karst = TER.build_karst('mv_gen')
t0 = time.time()
class StubT:
    def surf_z(self, x, y, pad=24.0): return L.gz(x, y) + 1.0
PL.build(d, 'mv_gen', os.path.abspath('../out/addon'), StubT(), karst, clone)
import mv_entities as EN
PL.W.T = StubT()
EN.build(d, 'mv_gen', os.path.abspath('../out/addon'), StubT(), clone)
G.finish(d, '../out/dry.vmap', group='mv_gen', drop_classes=G.GENERATOR_OWNS_EXAMPLE, extra_refs=[G.NAVATTR, G.LMRES])
print('dry %.0f s' % (time.time() - t0))
