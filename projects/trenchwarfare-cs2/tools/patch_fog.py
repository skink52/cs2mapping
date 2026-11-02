"""tw32: fog without particle overdraw, applied straight onto the user's vmap.
Removes the always-on fog sprites (vietnam_fog_ground, vietnam_fog_volume_1024: turning particles off fixed the frame rate looking
across no man's land) and leans on the cheap fog instead: env_cubemap_fog starts nearer (400 -> 250), volumetric fog a bit
thicker and patchier (FogStrength 0.6 -> 0.8, NoiseStrength 0.55 -> 0.7). Smoke columns and event effects are kept.
usage: patch_fog.py <user vmap> <out vmap>"""
import sys
import dmx

FOG = ('particles/maps/gg_vietnam/vietnam_fog_ground.vpcf', 'particles/maps/gg_vietnam/vietnam_fog_volume_1024.vpcf')
SET = {'env_cubemap_fog': {'cubemapfogstartdistance': '250'},
       'env_volumetric_fog_controller': {'FogStrength': '0.8', 'NoiseStrength': '0.7'}}
d = dmx.DMX.load(sys.argv[1])
kids = [a for a in d.root.get('world').attrs if a[0] == 'children'][0]
kept, removed, changed = [], 0, []
for c in kids[2]:
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties'); cls = ep.get('classname')
        if cls == 'info_particle_system' and ep.get('effect_name') in FOG: removed += 1; continue
        for k, v in SET.get(cls, {}).items():
            for a in ep.attrs:
                if a[0] == k: changed.append('%s.%s %s -> %s' % (cls, k, a[2], v)); a[2] = v
    kept.append(c)
kids[2] = kept
pre = {a[0]: a for a in d.prefix[0]}
if 'map_subasset_reference_names' in pre:
    names = pre['map_subasset_reference_names'][2]; counts = pre['map_subasset_reference_counts'][2]
    if 'info_particle_system' in names: counts[names.index('info_particle_system')] -= removed
d.elements = [d.root]
d.save(sys.argv[2])
print('removed %d fog particle systems; %s' % (removed, '; '.join(changed)))
