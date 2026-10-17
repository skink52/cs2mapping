"""Run individual clean passes on an already-cleaned map (keeps your own Hammer edits).

python3 stage_d.py <addon> <root> pass[,pass...]      passes: beams, lights, alpha, radar, daylight, skyvis
Appends to maps/<addon>_cleanup_log.txt (reads the current one from <root>/content/<addon>/maps if present).
"""
import os, re, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, stage_c, beams, lighting, assets, vpk, radar, daylight, skyvis

def run(addon, root, passes):
    c = stage_c.Ctx(addon, root)
    vp = os.path.join(c.content, 'maps', addon + '.vmap')
    m = V.Map(vp)
    vd = os.path.join(root, 'vpk')
    if os.path.exists(os.path.join(vd, 'cs2_pak01_dir.vpk')):
        c.cs2v = vpk.VPK(os.path.join(vd, 'cs2_pak01_dir.vpk')); csgov = vpk.VPK(os.path.join(vd, 'csgo_pak01_dir.vpk'))
        arcs = {int(f[11:14]): os.path.join(vd, f) for f in os.listdir(vd) if re.match(r'csgo_pak01_\d{3}\.vpk$', f)}
        c.src = assets.Source(c, csgov, arcs)
    if 'beams' in passes: beams.run(m, c)
    if 'skyvis' in passes: skyvis.run(m, c)
    if 'lights' in passes: lighting.run(m, c)
    if 'alpha' in passes and c.src: assets.fix_alpha(m, c)
    if 'daylight' in passes: daylight.run(m, c)
    if 'radar' in passes: radar.run(m, c)
    c.log.append('pruned %d orphaned elements' % m.prune())
    c.write('maps/%s.vmap' % addon, m.dumps())
    lp = os.path.join(c.content, 'maps', addon + '_cleanup_log.txt')
    old = open(lp, encoding='utf-8').read() if os.path.exists(lp) else ''
    c.write('maps/%s_cleanup_log.txt' % addon, old.rstrip() + '\n\nFollow-up pass (%s): %s\n' % (datetime.date.today(), ', '.join(passes)) +
            '\n'.join('- ' + l for l in c.log) + '\n' + '\n'.join('- TO CHECK: ' + t for t in c.todo) + '\n')
    return c

if __name__ == '__main__':
    addon, root, passes = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    c = run(addon, root, passes)
    out = os.path.join(root, 'out', addon)
    for rel, data in c.files.items():
        p = os.path.join(out, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
    for rel, data in c.game_files.items():
        p = os.path.join(root, 'out', addon + '_game', rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
    print('\n'.join(['- ' + l for l in c.log] + ['TO CHECK: ' + t for t in c.todo]))
