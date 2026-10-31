import sys, json, collections
sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, dmx
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
names=collections.defaultdict(list)
for e in m.entities():
    if m.name(e): names[m.name(e).lower()].append(e)
data={}; adds=[]
for e,c in list(m.all_conns()):
    t=m.conn_tuple(c)
    if t[2].lower()!='enable': continue
    tg=[x for x in names.get(t[1].lower(),[]) if m.cls(x) in ('trigger_hurt','trigger_teleport')]
    if not tg: continue
    nm=m.name(tg[0])
    if nm not in data:
        d={'cls':m.cls(tg[0]),'boxes':[[list(map(float,b[0])),list(map(float,b[1]))] for b in (m.bounds(x) for x in tg) if b]}
        if d['cls']=='trigger_hurt': d['damage']=float(m.P(tg[0],'damage','10') or 10); d['type']=int(float(m.P(tg[0],'damagetype','0') or 0))
        else:
            dst=[x for x in names.get((m.P(tg[0],'target') or '').lower(),[])]
            if not dst: continue
            d['dest']=[float(v) for v in m.origin(dst[0])]; d['yaw']=float(m.g(dst[0],b'angles',[0,0,0])[1])
        f=(m.P(tg[0],'filtername') or '').lower()
        ft=[x for x in names.get(f,[]) if m.cls(x)=='filter_activator_team']
        if ft: d['team']=int(m.P(ft[0],'filterteam','0') or 0); d['negated']=(m.P(ft[0],'Negated') or m.P(ft[0],'negated') or '0') not in ('0','Allow entities that match criteria')
        data[nm]=d
    adds.append((e,t[0],'Sweep_'+nm,t[4]+0.1,t[5]))
for e,c in list(m.all_conns()):
    t=m.conn_tuple(c)
    if t[2].lower()=='disable' and any(m.name(x)==t[1] for x in names.get(t[1].lower(),[])) and t[1] in data:
        adds.append((e,t[0],'Unsweep_'+t[1],t[4],t[5]))
for e,o,inp,dl,tf in adds: m.add_conn(e,o,'sweepscript','RunScriptInput',inp,dl,tf)
anchor=m.origin(names['roulcase'][0])
m.new_entity('point_script',[anchor[0],anchor[1],anchor[2]+64],{'targetname':'sweepscript','cs_script':'maps/scripts/keimusho_sweep.vjs'})
json.dump(data,open('/home/claude/work/sweep_data.json','w'),indent=1)
print(len(data),'triggers;',len(adds),'outputs added'); print({k:(v['cls'],v.get('damage'),v.get('team')) for k,v in data.items()})
m.save('/home/claude/work/out/ba_jail_keimusho.vmap')
open('/home/claude/work/out/edit_log.txt','a').write('triggers enabled with players already inside (CS2 does not re-check them): %d trigger_hurt / trigger_teleport get sweepscript Sweep_<name> 0.1 s after each Enable and Unsweep_<name> with each Disable (%d outputs added; keimusho_sweep.js)\n'%(len(data),len(adds)))
