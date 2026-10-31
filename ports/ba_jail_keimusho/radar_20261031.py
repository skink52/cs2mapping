import sys, os, time
sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, stage_c, radar, radar_props
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
c=stage_c.Ctx('ba_jail_keimusho','/home/claude/root')
emb='/home/claude/work/embedded'
texdir='/home/claude/root/embedded/ba_jail_keimusho/materials'
src=radar_props.Source(emb,'/mnt/user-data/uploads/csgo')
t=time.time(); print('world tex', radar_props.world_textures(m, src, texdir), time.time()-t)
t=time.time(); P=radar_props.polys(m, emb, '/mnt/user-data/uploads/csgo', c.log); print(len(P), time.time()-t)
t=time.time(); radar.run(m,c,size=2048,ss=2,pct=0,tex=radar.textures_for(c),extra_polys=P); print('radar',time.time()-t)
print('\n'.join(c.log))
for k,v in list(c.files.items())+list(c.game_files.items()):
    p=os.path.join('/home/claude/work/radar2',k); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(v)
