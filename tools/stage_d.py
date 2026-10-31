"""Run individual clean passes on an already-cleaned map (keeps your own Hammer edits).

python3 stage_d.py <addon> <root> pass[,pass...]      passes: beams, lights, alpha, radar, daylight, skyvis, visfit, visfit_lower, visfit_lean, gravity,
        overlayfix (rebuild placeholder overlay quads), overlaydepth (same + projection depth 8 on every overlay), facescale, matflags,
        probes (report static func_breakable/func_brush outside probe volumes), probecover (add volumes for them),
        lightbright (rebuild light brightness from the VMF: the importer's brightness = nan / too dim), relight (delete every light and rebuild it
        from the VMF; run before lights), equipitems (item_* out of equip slots),
        steam (env_steam -> particles), soundscripts (Source 1 soundscript names -> same-named soundevents), physpush (players push physics props by mass),
        gameui (game_ui -> key polling in the io script), physlaunch (physics-only trigger_push cannons -> script launch),
        renderamt (renderamt 255 where rendermode is Normal), ventlight (stationary lights in vents behind func_breakable grates),
        doorsolid (doors flagged Non-solid to Player: meshes -> never-solid func_brush parented to the door),
        skyshell (moondome sky shells -> toolsskybox: the sun bakes through toolsskybox, not through a moondome),
        water (water meshes -> func_water, underwater post_processing_volume, master volume),
        doorhinge (maps already through doorsolid: hinge cubes moved into the frame), iofix (logic_auto is_pc global state, output target name case),
        tesla (point_tesla -> crackle particle), doorparent (doorsolid brushes parented at spawn instead of in the map),
        probefill (light probe volumes over the whole play space, existing ones kept at higher priority),
        probedetail (finer nested volumes over walkable floors: 32 outdoors, 24 indoors),
        lightcover (stationary lights by line-of-sight floor cover per roofed compartment + open-sky fills; for maps that are one open compartment), overlays (static overlay materials -> csgo_static_overlay, opaque ones as <name>_overlay)
Appends to maps/<addon>_cleanup_log.txt (reads the current one from <root>/content/<addon>/maps if present).
"""
import os, re, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tesla, probefill, vmapedit as V, stage_c, gameui, beams, lighting, assets, vpk, radar, daylight, skyvis, visfit, gravity, texfix, probecover, steam, soundscripts, physpush, physlaunch, droppedio, ovlquad, ventlight, doorsolid, watervol

def run(addon, root, passes):
    c = stage_c.Ctx(addon, root)
    vp = os.path.join(c.content, 'maps', addon + '.vmap')
    m = V.Map(vp)
    vd = os.path.join(root, 'vpk')
    if os.path.exists(os.path.join(vd, 'cs2_pak01_dir.vpk')):
        c.cs2v = vpk.VPK(os.path.join(vd, 'cs2_pak01_dir.vpk')); csgov = vpk.VPK(os.path.join(vd, 'csgo_pak01_dir.vpk'))
        arcs = {int(f[11:14]): os.path.join(vd, f) for f in os.listdir(vd) if re.match(r'csgo_pak01_\d{3}\.vpk$', f)}
        c.src = assets.Source(c, csgov, arcs)
    vmfp = os.path.join(root, 'source1', 'maps', addon + '.vmf')
    if 'overlayfix' in passes or 'overlaydepth' in passes: texfix.overlay_geometry(m, c, vmfp, depth=8.0 if 'overlaydepth' in passes else None)
    if 'ovlquads' in passes: ovlquad.run(m, c)   # overlays on brush entities -> parented quads
    if 'facescale' in passes: texfix.face_scales(m, c, vmfp)
    if 'matflags' in passes: texfix.material_flags(m, c)
    if 'beams' in passes: beams.run(m, c)
    if 'skyvis' in passes: skyvis.run(m, c)
    if 'visfit' in passes or 'visfit_lower' in passes or 'visfit_lean' in passes: visfit.run(m, c, all_lower='visfit_lower' in passes, lean='visfit_lean' in passes)
    if 'relight' in passes: lighting.relight(m, c, vmfp)
    elif 'lightbright' in passes: lighting.fix_brightness(m, c, vmfp)
    if 'equipitems' in passes:
        stage_c.equip_items(m, c)
        if c.items_js:
            jp = os.path.join(c.content, 'maps', 'scripts', addon + '_io.js')
            js = stage_c.gen_script.patch_items(open(jp, encoding='utf-8').read(), c.items_js) if os.path.exists(jp) else stage_c.gen_script.build(addon, c.script, equip_items=c.items_js)
            c.write('maps/scripts/%s_io.js' % addon, js)
            if not any(m.name(e) == c.script for e in m.by_class('point_script')):
                sp = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + m.entities())[0]; o = m.origin(sp)
                m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': c.script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
    if 'steam' in passes: steam.run(m, c, vmfp)
    if 'soundscripts' in passes: soundscripts.run(m, c, vmfp)
    if 'physpush' in passes:
        physpush.run(m, c)
        if c.phys:
            jp = os.path.join(c.content, 'maps', 'scripts', addon + '_io.js')
            js = physpush.patch_script(open(jp, encoding='utf-8').read(), c.phys) if os.path.exists(jp) else stage_c.gen_script.build(addon, c.script, phys=c.phys)
            c.write('maps/scripts/%s_io.js' % addon, js)
            if not any(m.name(e) == c.script for e in m.by_class('point_script')):
                sp = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + m.entities())[0]; o = m.origin(sp)
                m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': c.script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
    if 'renderamt' in passes: stage_c.render_alpha(m, c)
    if 'ventlight' in passes: ventlight.run(m, c)
    if 'doorsolid' in passes: doorsolid.run(m, c)
    if 'doorhinge' in passes: doorsolid.rebury(m, c)
    if 'tesla' in passes: tesla.run(m, c)
    if 'doorparent' in passes: doorsolid.unparent(m, c)
    if 'probefill' in passes: probefill.run(m, c)
    if 'probedetail' in passes: probefill.detail(m, c, probefill.tiles_of(m))
    if 'overlays' in passes: stage_c.overlays(m, c)
    if 'iofix' in passes: stage_c.io_fixups(m, c)
    if 'water' in passes and watervol.run(m, c) and c.needs_underwater_vpost and not c.exists(watervol.VPOST):
        c.write(watervol.VPOST, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'postprocess_filmic_underwater.vpost'), 'rb').read())
    if 'skyshell' in passes:
        import skysplit
        n = skysplit.moondome_to_skybox(m)
        c.log.append('skyshell: %d moondome sky shells -> toolsskybox (areas under them baked black: the sun only bakes through toolsskybox)' % n)
    if 'lightcover' in passes:
        import lightcover
        lightcover.run(m, c)
    if 'lights' in passes: lighting.run(m, c)
    if 'alpha' in passes and c.src: assets.fix_alpha(m, c)
    if 'daylight' in passes: daylight.run(m, c)
    if 'probecover' in passes or 'probes' in passes: probecover.run(m, c, fix='probecover' in passes)
    if 'radar' in passes: radar.run(m, c, tex=radar.textures_for(c))
    if 'gravity' in passes:
        gravity.run(m, c)
        if c.gravities:
            jp = os.path.join(c.content, 'maps', 'scripts', addon + '_io.js')
            if os.path.exists(jp): js = gravity.patch_script(open(jp, encoding='utf-8').read(), c.gravities)
            else: js = stage_c.gen_script.build(addon, c.script, gravities=c.gravities)
            c.write('maps/scripts/%s_io.js' % addon, js)
            if not any(m.name(e) == c.script for e in m.by_class('point_script')):
                spawn = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + m.entities())[0]
                o = m.origin(spawn)
                m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': c.script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
                c.log.append('added point_script %s (maps/scripts/%s_io.js)' % (c.script, addon))
    if 'gameui' in passes and gameui.run(m, c):
        jp = os.path.join(c.content, 'maps', 'scripts', addon + '_io.js')
        js = open(jp, encoding='utf-8').read() if os.path.exists(jp) else 'import { Instance } from "cs_script/point_script";\n'
        c.write('maps/scripts/%s_io.js' % addon, gameui.patch_script(js, c.gameuis, gravity.THINK_JS))
        if not any(m.name(e) == c.script for e in m.by_class('point_script')):
            spawn = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + m.entities())[0]
            o = m.origin(spawn)
            m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': c.script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
            c.log.append('added point_script %s (maps/scripts/%s_io.js)' % (c.script, addon))
    if 'physlaunch' in passes and physlaunch.run(m, c):
        jp = os.path.join(c.content, 'maps', 'scripts', addon + '_io.js')
        js = open(jp, encoding='utf-8').read() if os.path.exists(jp) else 'import { Instance } from "cs_script/point_script";\n'
        c.write('maps/scripts/%s_io.js' % addon, physlaunch.patch_script(js, c.launch))
        if not any(m.name(e) == c.script for e in m.by_class('point_script')):
            spawn = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + m.entities())[0]
            o = m.origin(spawn)
            m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': c.script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
            c.log.append('added point_script %s (maps/scripts/%s_io.js)' % (c.script, addon))
    if 'droppedio' in passes and os.path.exists(vmfp): droppedio.run(m, c, vmfp)   # last, so it sees what our steps converted
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
