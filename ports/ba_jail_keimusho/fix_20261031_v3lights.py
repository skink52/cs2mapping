import sys, json, math
sys.path.insert(0,'/home/claude/cs2mapping/tools')
import vmapedit as V, stage_c, lighting, collections
m=V.Map('/home/claude/work/out/ba_jail_keimusho.vmap')
c=stage_c.Ctx('ba_jail_keimusho','/home/claude/root')
E=json.load(open('/home/claude/work/v3ents.json'))
open('/home/claude/work/v3_lights.vmf','w').write(''.join('entity\n{\n'+''.join('\t"%s" "%s"\n'%(k,v) for k,v in e if '\x1b' not in v)+'}\n' for e in E if dict(e)['classname'] in('light','light_spot','light_environment')))
L=m.by_class('light_omni2','light_barn')
before={e:(m.P(e,'range'),m.P(e,'directlight'),m.P(e,'brightness_legacy')) for e in L}
src=[(('light_omni2' if dict(x)['classname']=='light' else 'light_barn'),[float(v) for v in dict(x)['origin'].split()]) for x in E if dict(x)['classname'] in('light','light_spot')]
used=set()
for want,o in src:
    cand=[(sum((a-b)**2 for a,b in zip(m.origin(e),o)),e) for e in L if m.cls(e)==want and e not in used]
    if cand:
        d2,e=min(cand,key=lambda x:x[0])
        if d2<=64**2: used.add(e)
lighting.fix_brightness(m,c,'/home/claude/work/v3_lights.vmf')
K=lighting.OMNI_RANGE_K
for e in used:
    if m.cls(e)=='light_omni2':
        rg=math.sqrt(float(m.P(e,'brightness_legacy'))*K)
        if before[e][1]=='3': rg=min(rg,float(before[e][0]))
        m.setp(e,'range','%.0f'%rg)
legs=sorted(float(m.P(e,'brightness_legacy')) for e in used if m.cls(e)=='light_omni2'); med=legs[len(legs)//2]
added=[e for e in L if e not in used]
for e in added:
    if m.cls(e)!='light_omni2': continue
    for k,v in (('brightness_legacy','%g'%med),('brightness','%g'%round(math.log2(med),6)),('brightness_lumens','%d'%round(1000*med)),('brightness_candelas','%d'%round(1000*med/(4*math.pi))),('brightness_nits','%d'%round(9816*med))):
        m.setp(e,k,v)
print('matched',len(used),'of',len(src),'lights in vmap',len(L),'unmatched (added by us)',len(added),'median legacy',med)
print(collections.Counter(round(float(m.P(e,'brightness_legacy')),3) for e in used).most_common(8))
print('\n'.join(c.log))
m.save('/home/claude/work/out/ba_jail_keimusho.vmap')
open('/home/claude/work/out/edit_log.txt','a').write('brightness re-done from the v3 BSP _light values (%d of %d v3 lights matched); the %d lights added by lightcover set to the v3 median (legacy %g); stationary ranges kept at their trimmed value\n'%(len(used),len(src),len(added),med))
