import sys, time; sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, stage_c, visfit
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
c=stage_c.Ctx('ba_jail_keimusho','/home/claude/root')
t=time.time(); pl=visfit.plan(m, detail=True); print(time.time()-t)
print(pl['stats'])
for h in pl['hints']: 
    if h[0]!='Lowest': pass
import collections
print(collections.Counter(h[0] for h in pl['hints']))
import pickle; pickle.dump(pl['hints'],open('/home/claude/work/vis_hints.pkl','wb'))
