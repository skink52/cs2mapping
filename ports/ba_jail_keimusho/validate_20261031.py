import sys, json, re, os, collections
sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, stage_c, probecover, dmx
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
c=stage_c.Ctx('ba_jail_keimusho','/home/claude/root')
P=print
# 1 point_scripts -> files, inputs
S='/home/claude/work/out/scripts/'
ps={m.name(e):m.P(e,'cs_script') for e in m.by_class('point_script')}
P('point_scripts',ps)
inputs=collections.defaultdict(set)
for n,p in ps.items():
    f=S+os.path.basename(p).replace('.vjs','.js')
    if not os.path.exists(f): P('MISSING script file',f); continue
    js=open(f).read()
    lits=set(re.findall(r'OnScriptInput\("([^"]+)"',js)); pref=set(re.findall(r'OnScriptInput\("([^"]+)" \+',js))
    inputs[n]=(lits,pref,js)
bad=[]
for e,cc in m.all_conns():
    t=m.conn_tuple(cc)
    if t[2]=='RunScriptInput':
        if t[1] not in inputs: bad.append(('no script entity',t)); continue
        lits,pref,js=inputs[t[1]]
        ok=t[3] in lits or any(t[3].startswith(p) for p in pref)
        if not ok: bad.append(('unknown input',t))
P('RunScriptInput problems',bad[:10], len(bad))
# 2 targets exist
names=set(m.name(e).lower() for e in m.entities() if m.name(e))
miss=collections.Counter(m.conn_tuple(cc)[1] for e,cc in m.all_conns() if m.conn_tuple(cc)[1] and not m.conn_tuple(cc)[1].startswith('!') and m.conn_tuple(cc)[1].lower() not in names and not m.conn_tuple(cc)[1].endswith('*'))
P('missing targets',miss)
# 3 v3 diff
E=json.load(open('/home/claude/work/v3ents.json'))
def norm(t): return tuple(x.lower() if isinstance(x,str) else x for x in t)
bsp=collections.Counter()
for e in E:
    d={k.lower():v for k,v in e}
    for k,v in e:
        if '\x1b' in v:
            p=v.split('\x1b'); bsp[norm((d['classname'],k,p[0],p[1],p[2],round(float(p[3] or 0),3)))]+=1
vm=collections.Counter(norm((m.cls(e),)+m.conn_tuple(cc)[:5]) for e,cc in m.all_conns())
P('v3 outputs still missing',[k for k in (bsp-vm)])
# 4 entity classes that don't exist / dead
dead=('player_speedmod','env_sun','game_ui','point_clientcommand','env_screenoverlay','env_laser','env_beam','func_wall_toggle','func_breakable_surf','prop_hallucination','env_sprite','env_spritetrail','logic_script','game_score','item_ammo','trigger_gravity','phys_thruster','env_steam','point_tesla','func_monitor','func_physbox_multiplayer','light_dynamic','color_correction','cs_minimap_boundary','sky_camera','move_rope','logic_auto')
P('dead classes present',collections.Counter(m.cls(e) for e in m.entities() if m.cls(e) in dead))
# 5 AddOutput / Alpha / Color on players, SetRemoteDestination, Use on equips
odd=[(m.cls(e),m.name(e),m.conn_tuple(cc)[:4]) for e,cc in m.all_conns() if m.conn_tuple(cc)[2].lower() in ('addoutput','alpha','color','setremotedestination','modifyspeed','use') ]
P('odd inputs',odd)
# 6 equips slots
for e in m.by_class('game_player_equip'):
    items=[m.P(e,'weapon%d'%i) for i in range(22) if m.P(e,'weapon%d'%i)]
    legacy=[a[0] for a in m.props(e)['attrs'] if re.match(rb'^(weapon|item)_',a[0])]
    if legacy or any(x.startswith('item_') or x in ('weapon_bumpmine','weapon_tagrenade') for x in items): P('equip issue',m.name(e),items,legacy)
# 7 renderamt, filters
P('renderamt<255 normal',[(m.cls(e),m.name(e)) for e in m.entities() if m.P(e,'renderamt') not in (None,'','255') and m.P(e,'rendermode') in (None,'0','kRenderNormal')])
P('filters',[(m.name(e),m.P(e,'filterteam'),m.P(e,'Negated')) for e in m.by_class('filter_activator_team')])
# 8 trigger_push left, physbox
P('trigger_push',len(m.by_class('trigger_push')))
# 9 lights
P('lights',collections.Counter((m.cls(e),m.P(e,'directlight')) for e in m.by_class('light_omni2','light_barn','light_environment')))
nan=[e for e in m.by_class('light_omni2','light_barn') if 'nan' in (m.P(e,'brightness') or '')]
P('nan brightness',len(nan))
# 10 probe coverage
probecover.run(m,c); P(c.log[-1:], c.todo)
# 11 weapons in map that CS2 lacks
P('map weapons',collections.Counter(m.cls(e) for e in m.entities() if m.cls(e).startswith('weapon_') and m.cls(e) in ('weapon_tagrenade','weapon_bumpmine','weapon_breachcharge','weapon_shield','weapon_fists','weapon_axe','weapon_hammer','weapon_spanner','weapon_snowball','weapon_tablet')))
