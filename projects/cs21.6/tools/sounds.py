"""1.6 sounds for the map: the player's own 1.6 wavs converted for CS2, sound events for them, and CS2's weapon sound
events replaced so the guns, knife, grenades and C4 sound like 1.6.

usage: python3 tools/sounds.py <cstrike dir> <valve dir> <template soundevents_addon.vsndevts> <cs2 weapon events json> <addon out dir>

  template      the addon's own soundevents_addon.vsndevts (kept as it is; our events go in a marked block at the top)
  events json   CS2's weapon sound events (tools/dump_soundevents.py -> build/soundevents_weapons.json). A replaced event
                is CS2's own event with 1.6 sound files and no child events (so no CS2 distant or layer sounds play).

Writes sounds/cs16/**.wav (44.1 kHz 16-bit mono), soundevents/soundevents_addon.vsndevts and _gen/sounds.json (the
events the map script plays itself; tools/convert_map.py adds a point_soundevent for each).
"""
import os, sys, json, re, wave, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kv3bin

CS, VALVE, TEMPLATE, WEAPON_JSON, OUT = sys.argv[1:6]
SND = os.path.join(OUT, 'sounds/cs16')


def convert(src, dst):
    with wave.open(src, 'rb') as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    a = (np.frombuffer(data, np.uint8).astype(np.float32) - 128) * 256 if sw == 1 else np.frombuffer(data, np.int16).astype(np.float32)
    if ch == 2: a = a.reshape(-1, 2).mean(1)
    t = np.arange(0, len(a), rate / 44100.0)
    b = np.interp(t, np.arange(len(a)), a)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with wave.open(dst, 'wb') as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(44100)
        o.writeframes(np.clip(b, -32768, 32767).astype(np.int16).tobytes())


def wav(rel):
    """1.6 sound path (sound/<rel>.wav, cstrike first, then valve) -> the CS2 path of the converted copy"""
    for base in (CS, VALVE):
        src = os.path.join(base, 'sound', rel + '.wav')
        if os.path.exists(src):
            convert(src, os.path.join(SND, rel + '.wav'))
            return 'sounds/cs16/%s.vsnd' % rel
    print('missing 1.6 sound', rel)
    return None


# ---------------------------------------------------------------- sounds the script plays to players (radio, buying)
SCRIPT = {'terwin': 'radio/terwin', 'ctwin': 'radio/ctwin', 'rounddraw': 'radio/rounddraw', 'bombpl': 'radio/bombpl', 'bombdef': 'radio/bombdef',
          'moveout': 'radio/moveout', 'letsgo': 'radio/letsgo', 'locknload': 'radio/locknload', 'com_go': 'radio/com_go',
          'ct_fireinhole': 'radio/ct_fireinhole', 'gunpickup2': 'items/gunpickup2', 'ammopickup2': 'items/ammopickup2',
          '9mmclip1': 'items/9mmclip1', 'tr_kevlar': 'items/tr_kevlar', 'kevlar': 'items/kevlar'}
events = {}
# heard at full volume by the player it plays at, gone within a few metres (see src/cs2/60_sound.js)
events['cs16.base'] = {'type': 'csgo_mega', 'volume': 1.0, 'pitch': 1.0, 'use_distance_volume_mapping_curve': True,
                       'distance_volume_mapping_curve': [[0.0, 1.0, 0.0, 0.0, 2.0, 3.0], [120.0, 1.0, 0.0, 0.0, 2.0, 3.0], [360.0, 0.0, 0.0, 0.0, 2.0, 3.0]]}
script_events = []
for name, rel in SCRIPT.items():
    p = wav(rel)
    if not p: continue
    events['cs16.' + name] = {'base': 'cs16.base', 'vsnd_files_track_01': [p]}
    script_events.append('cs16.' + name)

# ---------------------------------------------------------------- CS2 weapon events played with 1.6 sounds
W = 'weapons/'
OVERRIDE = {
    'Weapon_AK47.Single': ['ak47-1'], 'Weapon_M4A1.Silenced': ['m4a1-1'], 'Weapon_M4A1.Single': ['m4a1_unsil-1'], 'Weapon_M4A4.Single': ['m4a1_unsil-1'],
    'Weapon_AWP.Single': ['awp1'], 'Weapon_DEagle.Single': ['deagle-1'], 'Weapon_Glock.Single': ['glock18-1'], 'Weapon_USP.SilencedShot': ['usp1'],
    'Weapon_USP.Single': ['usp_unsil-1'], 'Weapon_hkp2000.Single': ['usp_unsil-1'], 'Weapon_P250.Single': ['p228-1'],
    'Weapon_FiveSeven.Single': ['fiveseven-1'], 'Weapon_ELITE.Single': ['elite_fire'], 'Weapon_Nova.Single': ['m3-1'], 'Weapon_XM1014.Single': ['xm1014-1'],
    'Weapon_MAC10.Single': ['mac10-1'], 'Weapon_MP9.Single': ['tmp-1'], 'Weapon_MP5.Single': ['mp5-1'], 'Weapon_UMP45.Single': ['ump45-1'],
    'Weapon_P90.Single': ['p90-1'], 'Weapon_GalilAR.Single': ['galil-1'], 'Weapon_FAMAS.Single': ['famas-1'], 'Weapon_sg556.Single': ['sg552-1'],
    'Weapon_AUG.Single': ['aug-1'], 'Weapon_SSG08.Single': ['scout_fire-1'], 'Weapon_G3SG1.Single': ['g3sg1-1'], 'Weapon_SCAR20.Single': ['sg550-1'],
    'Weapon_M249.Single': ['m249-1'],
    # knife: swings, hits on players, stabs, the wall
    'Weapon_Knife.Slash': ['knife_slash1', 'knife_slash2'], 'Weapon_Knife.Swish.Light': ['knife_slash1', 'knife_slash2'],
    'Weapon_Knife.Swish.Heavy': ['knife_slash1', 'knife_slash2'],
    'Weapon_Knife.Hit': ['knife_hit1', 'knife_hit2', 'knife_hit3', 'knife_hit4'], 'Weapon_Knife.Hit.Flesh': ['knife_hit1', 'knife_hit2', 'knife_hit3', 'knife_hit4'],
    'Weapon_Knife.Hit.Light': ['knife_hit1', 'knife_hit2', 'knife_hit3', 'knife_hit4'],
    'Weapon_Knife.Hit.Light.Flesh': ['knife_hit1', 'knife_hit2', 'knife_hit3', 'knife_hit4'],
    'Weapon_Knife.Stab': ['knife_stab'], 'Weapon_Knife.Hit.Heavy': ['knife_stab'], 'Weapon_Knife.Hit.Heavy.Flesh': ['knife_stab'],
    'Weapon_Knife.Hit.Heavy.Backstab': ['knife_stab'], 'Weapon_Knife.Hit.Heavy.Backstab.Flesh': ['knife_stab'],
    'Weapon_Knife.Hit.Light.Backstab': ['knife_stab'], 'Weapon_Knife.Hit.Light.Backstab.Flesh': ['knife_stab'],
    'Weapon_Knife.HitWall': ['knife_hitwall1'], 'Weapon_Knife.Deploy': ['knife_deploy1'],
    # grenades
    'BaseGrenade.Explode': ['hegrenade-1', 'hegrenade-2'], 'HEGrenade.Bounce': ['he_bounce-1'], 'Flashbang.Bounce': ['he_bounce-1'],
    'Flashbang.Explode': ['flashbang-1', 'flashbang-2'], 'HEGrenade.PullPin_Grenade': ['pinpull'], 'Flashbang.PullPin_Grenade': ['pinpull'],
    # C4: the beeps (faster ones in the last seconds), planting, defusing, the blast
    'C4.PlantSound': ['c4_beep1'], 'C4.PlantSoundB': ['c4_beep2'], 'C4.PlantSound_10sec': ['c4_beep4'], 'C4.PlantSoundB_10sec': ['c4_beep5'],
    'c4.plant': ['c4_plant'], 'c4.initiate': ['c4_click'], 'c4.keypressquiet': ['c4_click'], 'c4.disarmstart': ['c4_disarm'],
    'c4.disarmfinish': ['c4_disarmed'], 'c4.explode': ['c4_explode1'],
}
SILENCE = ['c4.shockwave.boom', 'c4.shockwave.hit', 'c4.shockwave.debris', 'c4.explode.close']   # CS2's extra blast layers
cs2 = json.load(open(WEAPON_JSON))
done, missing = [], []
for ev, files in OVERRIDE.items():
    if ev not in cs2: missing.append(ev); continue
    paths = [p for p in (wav(W + f) for f in files) if p]
    if not paths: continue
    e = copy.deepcopy(cs2[ev])
    for k in [k for k in e if k.startswith('vsnd_files') or k.startswith('soundevent_')]: del e[k]
    e['vsnd_files_track_01'] = paths
    e['enable_child_events'] = False
    if ev.startswith('Weapon_Knife.'): e['volume'] = max(float(e.get('volume', 1.0)), 0.8)
    events[ev] = e
    done.append(ev)
for ev in SILENCE:
    if ev in cs2:
        e = copy.deepcopy(cs2[ev]); e['volume'] = 0.0; e['enable_child_events'] = False
        for k in [k for k in e if k.startswith('soundevent_')]: del e[k]
        events[ev] = e

# ---------------------------------------------------------------- write: our block inside the template's root braces
body = kv3bin.to_kv3_text(events, header=False)
body = body[body.index('{') + 1:body.rindex('}')]
t = open(TEMPLATE, encoding='utf-8').read()
t = re.sub(r'\n\t// ---- cs16 sound events \(generated\) ----.*?// ---- end cs16 ----\n', '\n', t, flags=re.S)   # a previous run's block
first = t.index('\n{') + 2
out = t[:first] + '\n\t// ---- cs16 sound events (generated) ----' + body.rstrip() + '\n\t// ---- end cs16 ----\n' + t[first:]
os.makedirs(os.path.join(OUT, 'soundevents'), exist_ok=True)
open(os.path.join(OUT, 'soundevents/soundevents_addon.vsndevts'), 'w', encoding='utf-8', newline='\n').write(out)
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
json.dump(script_events, open(os.path.join(OUT, '_gen/sounds.json'), 'w'))
print('sounds: %d script events, %d CS2 events replaced, %d silenced; not in CS2: %s' % (len(script_events), len(done), len(SILENCE), missing))
