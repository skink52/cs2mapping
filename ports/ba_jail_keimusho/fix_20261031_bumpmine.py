import sys; sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, dmx, collections
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
LOG=[]
btns=[e for e in m.by_class('func_button') if m.name(e)=='bumpminebutton']
for b in btns: m.add_conn(b,'OnPressed','bumpscript','RunScriptInput','bump_give',0.05,-1)
eq=[e for e in m.by_class('game_player_equip') if m.name(e)=='awp spawner'][0]
for i in range(22):
    if m.P(eq,'weapon%d'%i)=='weapon_bumpmine': m.setp(eq,'weapon%d'%i,'weapon_decoy')
o=m.origin(btns[0]); print('buttons',[ [round(x) for x in m.origin(b)] for b in btns])
lo_z=min(m.origin(e)[2] for e in m.entities())-512
home=[o[0],o[1],lo_z]
m.new_entity('point_script',[o[0],o[1],o[2]+96],{'targetname':'bumpscript','cs_script':'maps/scripts/keimusho_bumpmine.vjs'})
tmpl=next(e for e in m.by_class('prop_dynamic'))
for i in range(1,9):
    n='bumpmine_%d'%i
    p={a[0].decode():a[2].decode() for a in m.props(tmpl)['attrs'] if a[0]!=b'classname'}
    p.update({'targetname':n,'model':'models/weapons/w_eq_bumpmine_dropped.vmdl','solid':'0','parentname':'','DefaultAnim':'','skin':'0','StartDisabled':'0','disableshadows':'1','renderamt':'255','rendermode':'kRenderNormal'})
    m.new_entity('prop_dynamic',[home[0]+i*32,home[1],home[2]],p)
    for k,ev in (('land','keimusho.bumpmine.land'),('det','keimusho.bumpmine.detonate')):
        m.new_entity('point_soundevent',[home[0]+i*32,home[1],home[2]+16],{'targetname':'%s_%s'%(n,k),'soundName':ev,'sourceEntityName':n,'startOnSpawn':'0','toLocalPlayer':'0','stopOnNew':'1'})
LOG.append('bump mines: %d bumpminebutton -> bumpscript bump_give; awp spawner weapon_bumpmine -> weapon_decoy; bumpscript + 8 pooled prop_dynamic bumpmine_N (w_eq_bumpmine_dropped, non-solid, parked at z %d) + land/detonate point_soundevents'%(len(btns),lo_z))
m.save('/home/claude/work/out/ba_jail_keimusho.vmap')
print('\n'.join(LOG))
open('/home/claude/work/out/edit_log.txt','a').write('\n'.join(LOG)+'\n')
