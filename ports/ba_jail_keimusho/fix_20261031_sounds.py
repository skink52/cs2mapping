import sys, os, json, re
sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, stage_c, assets, vpk
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
c=stage_c.Ctx('ba_jail_keimusho','/home/claude/root')
vd='/mnt/user-data/uploads/csgo'
csgov=vpk.VPK(vd+'/pak01_dir.vpk')
arcs={int(f[6:9]):os.path.join(vd,f) for f in os.listdir(vd) if re.match(r'pak01_\d{3}\.vpk$',f)}
c.src=assets.Source(c,csgov,arcs)
c.files['soundevents/soundevents_addon.vsndevts']=open('/home/claude/work/out/content/soundevents/soundevents_addon.vsndevts','rb').read()
E=json.load(open('/home/claude/work/v3ents.json'))
open('/home/claude/work/v3_all.vmf','w').write(''.join('entity\n{\n'+''.join('\t"%s" "%s"\n'%(k,v) for k,v in e if '\x1b' not in v)+'}\n' for e in E))
stage_c.door_sounds(m,c,'/home/claude/work/v3_all.vmf')
# buttons: CS:GO "sounds" 10 -> buttons/button10.wav as soundevent, use_sound on the matching buttons
data=c.src.read('sound/buttons/button10.wav')
nd,note=stage_c.wav_to_pcm16(data); data=nd or data
c.write('sounds/buttons/button10.wav',data)
ev=c.files['soundevents/soundevents_addon.vsndevts'].decode()
EVB='''	// func_button sounds 10 (CS:GO buttons/button10.wav)
	"keimusho.button10" =
	{
		base = "amb.base"
		volume = 1.00
		use_time_volume_mapping_curve = false
		vsnd_files_track_01 = "sounds/buttons/button10.vsnd"
		distance_volume_mapping_curve =
		[
			[
				0.0, 1.0, 0.0, 0.0,
				2.0, 3.0,
			],
			[
				1000.0, 0.0, 0.0, 0.0,
				2.0, 3.0,
			],
		]
	}
'''
if '"keimusho.button10"' not in ev:
    i=ev.rstrip().rfind('}'); ev=ev[:i].rstrip('\n')+'\n'+EVB+'\n}\n'; c.files['soundevents/soundevents_addon.vsndevts']=ev.encode()
btns=m.by_class('func_button'); n=0
for e in E:
    d=dict(e)
    if d['classname']!='func_button' or d.get('sounds') in (None,'0'): continue
    o=[float(x) for x in d['origin'].split()]
    cand=[b for b in btns if (m.name(b) or '')==(d.get('targetname') or '') ]
    best=min(cand,key=lambda b:sum((p-q)**2 for p,q in zip(m.origin(b),o)),default=None)
    if best is not None and sum((p-q)**2 for p,q in zip(m.origin(best),o))<48**2:
        m.setp(best,'use_sound','keimusho.button10'); n+=1
c.log.append('func_button: %d buttons with CS:GO "sounds 10" -> use_sound keimusho.button10 (buttons/button10.wav from CS:GO)'%n)
print('\n'.join(c.log)); print(c.todo)
for k,v in c.files.items():
    p=os.path.join('/home/claude/work/out/content',k); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(v); print('wrote',k,len(v))
m.save('/home/claude/work/out/ba_jail_keimusho.vmap')
open('/home/claude/work/out/edit_log.txt','a').write('\n'.join(c.log)+'\n')
