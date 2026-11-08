"""Map types: what each kind of map needs beyond the normal pipeline, and how to tell whether a map still needs a person.

Add a type: a row in PROFILES and, if it needs one, a function in EXTRAS. classify_todo() decides what a tool's TO CHECK line means for the build.
"""
import glob, os, re, shutil, sys
from common import CS2, REPO, S1, WORK, read
import vmapedit as V

class Profile:
    def __init__(s, name, label, extras=(), passes=(), vis='visfit', needs='', other_ports_matter=True):
        s.name, s.label, s.extras, s.passes, s.vis, s.needs, s.other_ports_matter = name, label, extras, passes, vis, needs, other_ports_matter

# first match wins
PROFILES = [
    # other people's TTT ports need a dedicated server; ours play from the map's own script, so they aren't duplicates
    (r'^ttt_', Profile('ttt', 'TTT', extras=('ttt_build',), needs='full TTT build: entities, map data, ttt.js and HUD', other_ports_matter=False)),
    (r'^mg_.*course', Profile('course', 'minigame course', extras=('course_check', 'respawn_window'), needs='finish score check, respawn window before the AFK killer')),
    (r'^(jb_|ba_jail|ba_)', Profile('jail', 'jailbreak', extras=('jail_audit',), passes=('iofix',), vis='visfit_detail', needs='I/O audit, iofix, detailed vis hints')),
    (r'^mg_', Profile('minigame', 'minigame')),
    (r'^(de|cs|ar|dm|gg|aim|awp|fy|surf|bhop|kz|ze|zm|hns|am)_', Profile('generic', 'standard')),
]
UNKNOWN = Profile('unknown', 'unknown type', needs='no known type, so a person should check it')

def detect(addon):
    for pat, p in PROFILES:
        if re.search(pat, addon, re.I): return p
    return UNKNOWN

def counts_as_duplicate(profile, listed):
    """Whether a line from existing_ports.txt should stop this map."""
    return profile.other_ports_matter or '[ext. port]' not in listed

# VMF classes that are expected to be gone from the finished map: each is converted or knowingly dropped by the pipeline.
# Measured across every port on the PC. A class that vanishes and isn't here goes to the log as unknown.
KNOWN_GONE = set('''worldspawn light light_spot light_environment light_dynamic func_detail func_viscluster func_areaportal func_areaportalwindow func_occluder
water_lod_control env_cubemap info_overlay infodecal trigger_push env_sprite move_rope keyframe_rope func_dustmotes env_fog_controller sky_camera env_sun
env_laser env_beam point_spotlight game_score trigger_gravity player_speedmod shadow_control env_detail_controller env_tonemap_controller func_breakable_surf
func_wall_toggle func_precipitation env_steam env_spark env_fire point_viewcontrol func_physbox_multiplayer game_ui func_water_analog point_tesla func_illusionary
env_spritetrail env_screenoverlay point_clientcommand point_servercommand game_weapon_manager
prop_physics_respawnable info_ladder_dismount trigger_waterydeath func_wall'''.split())   # last line: tools/respawnable.py and mapcheck.py

TODO_RULES = [
    # lines only someone in the game can answer
    ('playtest', r'pops? in|flicker|compare a few rooms|feel wrong|seams after the bake|counter fed by|in game|in Hammer|heuristic|chat messages use|check the substituted|'
                 r'check the new probe|starts on|Don.t Drop|still works in CS2|ropes rebuilt|no Medium corridor'),
    # stops the map working or looking right: a person decides before the build
    ('missing', r'materials still missing|models referenced but not|outputs from the \.vmf are missing|could not be matched 1:1|prefab .* not found|not staged|'
                r'could not rebuild|sky brushes dropped by the importer were not rebuilt|moondome cube map|soundscript events built with some waves missing'),
    ('io', r'not converted automatically|VScript|game_ui .*not (converted|emulated)|FieldOfView|physics-only trigger_push|has no mesh|did damage in CS:GO'),
    # known, doesn't block the build
    ('minor', r'env_spritetrail|overlay materials not converted|door sounds|ambient_generic|soundscript names|placeholder static overlays|non-box sky|importer leaves these out|'
              r'face scales fixed|faces still with|material file names|splitfaces: not split|env_spark|env_steam inputs|env_fire Enable|beams with no usable|re-encode|'
              r'overlays touching brush entities|projection depth|origindup|physpush: no CS:GO|compartments|'
              r'ssbump normal maps|no VMF at|left as a prefab|was rotated|no map path|CS:GO 3D skybox|static func_breakable|'
              r'particles: several CS2 particles|particles: no CS2 or addon particle'),
]

def classify_todo(text):
    """A TO CHECK line this table has never seen is unknown, so a new tool message can't slip past unread."""
    for kind, pat in TODO_RULES:
        if re.search(pat, text, re.I): return kind
    return 'unknown'

# ------------------------------------------------------------------ extras
def course_check(m):
    """Course maps normally award the finish score through game_score, which CS2 doesn't have (stage C makes it script Score_n)."""
    vmf = read(os.path.join(S1, 'maps', m.addon + '.vmf'))
    scores, applied = vmf.count('"classname" "game_score"'), vmf.count('ApplyScore')
    if not scores and not applied:
        m.note('io', 'Course map with no game_score or ApplyScore: find how the finish works in the map, because players may never get a finish score.'); return
    mp = V.Map(m.vmap)
    wired = sum('Score_' in str(mp.conn_tuple(c)) for e in mp.entities() for c in mp.conns(e))
    script = read(os.path.join(m.content, 'maps', 'scripts', m.addon + '_io.js'))
    if not wired or 'Score_' not in script:
        m.note('io', 'Finish score lost: the VMF has %d game_score / %d ApplyScore, but the map has %d outputs to Score_n and the io script %s them.' % (scores, applied, wired, 'has' if 'Score_' in script else 'lacks'))

def respawn_window(m):
    """Respawning on until 5 s before the spawn AFK killer switches on (tools/respawnwindow.py; skink52, 3 Nov 2026)."""
    import respawnwindow
    mp = V.Map(m.vmap); msg = respawnwindow.run(mp)
    if not msg: return
    if not msg.startswith('respawn window: respawning'): m.note('review', msg[0].upper() + msg[1:] + '.'); return
    mp.save(m.vmap); guns = respawnwindow.weapons(mp)
    m.note('playtest', msg[0].upper() + msg[1:] + '. Die on an early obstacle and check you come back.' +
           (' The map also hands out %s: if it is a shooting map rather than a course, remove port_respawn_window.' % ', '.join(guns) if guns else ''))

JAIL_RISKS = [('AddOutput', r'AddOutput', 'often dead in CS2'), ('RunScript', r'RunScript', 'VScript has to be ported to cs_script'), ('sm_ commands', r'\bsm_\w+', 'need a server plugin or a script'),
              ('logic_case', r'"logic_case"', 'math_counter sends a float string, so case values may need 1.000000'), ('math_counter', r'"math_counter"', 'check what reads its value'),
              ('point_template', r'"point_template"|"env_entity_maker"', 'map entities are re-created each round, so scripts must re-hook them')]

def jail_audit(m):
    """Every jail port so far needed hand work on its I/O, so this lists what to read rather than claiming to fix it."""
    vmf = read(os.path.join(S1, 'maps', m.addon + '.vmf'))
    found = ['%d %s (%s)' % (n, name, why) for name, pat, why in JAIL_RISKS for n in [len(re.findall(pat, vmf))] if n]
    if found: m.note('io', 'Jail I/O to check (lessons in autoport/REVIEW.md): ' + '; '.join(found))
    else: m.note('review', 'Jail map with no risky I/O found: still test its doors, buttons and minigames.')

HUD_IMAGES = ('kf.png', 'sb.png', 'shop.png', 'top.png')

def hud_images(m, addon_out):
    """ttt_hud.css names four background images that aren't in git, and one that's missing stops the stylesheet compiling, which loses the whole HUD.
    Copy them from any TTT addon that has them; with none, drop them from this map's stylesheet so the HUD builds in flat colours."""
    rel = os.path.join('panorama', 'images', 'custom_game', 'ttt')
    roots = [os.path.join(REPO, 'projects', 'cs2mapTTT', 'addon')] + sorted(glob.glob(os.path.join(CS2, 'content', 'csgo_addons', 'ttt_*')))
    src = next((os.path.join(r, rel) for r in roots if all(os.path.exists(os.path.join(r, rel, f)) for f in HUD_IMAGES)), None)
    if src:
        os.makedirs(os.path.join(addon_out, rel), exist_ok=True)
        for f in HUD_IMAGES: shutil.copyfile(os.path.join(src, f), os.path.join(addon_out, rel, f))
        return
    css = os.path.join(addon_out, 'panorama', 'styles', 'custom_game', 'ttt_hud.css')
    text = re.sub(r'\s*background-image:\s*url\([^)]*\)[^;]*;', '', read(css))
    open(css, 'w', encoding='utf-8', newline='').write(text)
    m.note('minor', 'No TTT HUD images found anywhere, so this map\'s HUD uses flat colours. Make them with projects/cs2mapTTT/tools/hud_theme.py if you want them.')

def ttt_check(m):
    """After a build: the parts a TTT map can't play without."""
    game = os.path.join(CS2, 'game', 'csgo_addons', m.addon)
    want = ['maps/scripts/ttt.vjs_c', 'panorama/layout/custom_game/ttt_hud.vxml_c', 'panorama/styles/custom_game/ttt_hud.vcss_c']
    gone = [w for w in want if not os.path.exists(os.path.join(game, w.replace('/', os.sep)))]
    if gone: m.note('missing', 'The TTT build is incomplete, these never compiled: %s. See logs\\%s_assets.log' % (', '.join(gone), m.addon))

def ttt_build(m):
    """The full cs2mapTTT install, in a copy of the project so a port never changes the repo: ttt_convert, map data baked into ttt.js, addon files copied in."""
    src = os.path.join(REPO, 'projects', 'cs2mapTTT'); work = os.path.join(WORK, 'ttt_project')
    if not os.path.isdir(src): raise m.StepFail('cs2mapTTT not found at ' + src)
    for sub in ('tools', 'addon'):
        shutil.rmtree(os.path.join(work, sub), ignore_errors=True)
        shutil.copytree(os.path.join(src, sub), os.path.join(work, sub))
    os.makedirs(os.path.join(work, 'maps'), exist_ok=True)
    for f in glob.glob(os.path.join(src, 'maps', '*.json')):
        if os.path.basename(f) != m.addon + '.json': shutil.copyfile(f, os.path.join(work, 'maps', os.path.basename(f)))
    if m.run('ttt_convert', [sys.executable, os.path.join(work, 'tools', 'ttt_convert.py'), m.vmap, m.out, m.addon, '--cs2mapping', REPO, '--data', os.path.join(work, 'maps')]):
        raise m.StepFail('ttt_convert.py failed, see ' + m.log('ttt_convert'))
    if m.run('ttt_data', [sys.executable, os.path.join(work, 'tools', 'build_data.py')]):
        raise m.StepFail('build_data.py failed, see ' + m.log('ttt_data'))
    addon_out = os.path.join(WORK, 'out', m.addon)
    shutil.copytree(os.path.join(work, 'addon'), addon_out, dirs_exist_ok=True)
    hud_images(m, addon_out)
    mp = V.Map(m.out)
    if not any(mp.name(e) == 'ttt_script' for e in mp.by_class('point_script')): raise m.StepFail('ttt_convert.py wrote no ttt_script: see ' + m.log('ttt_convert'))
    for line in read(m.log('ttt_convert')).splitlines():
        if line.strip().startswith('dropped:'): m.note('io', 'TTT conversion ' + line.strip())
    m.apply()
    data = os.path.join(work, 'maps', m.addon + '.json')
    if os.path.exists(data): m.note('review', 'Copy %s to projects/cs2mapTTT/maps/ in the repo and run tools/build_data.py there, so the map data is kept.' % data)
    m.note('review', 'TTT: compare the map with projects/cs2mapTTT/docs/MAP_REQUIREMENTS.md. The ttt.js mock test (test/run_mock.sh) needs node and has not been run for this map.')
    m.note('playtest', 'TTT: play a full round (roles, shop, body search, win conditions) and record the result in projects/cs2mapTTT/TESTING.md.')

EXTRAS = dict(course_check=course_check, respawn_window=respawn_window, jail_audit=jail_audit, ttt_build=ttt_build)
