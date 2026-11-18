"""Hellmatch ZE music: each ZE level's own Freedoom track (pool "level"), the boss track (pool "boss") and the Hellmatch
theme (pool "opener"), written as MP3s plus _gen/music.json (id, pool, seconds, title, by, level) for the sound
events, the map and the script.

usage: music.py <addon_out>

Where each track comes from (first that works; results are cached in build/music):
  1. build/music/<id>.mp3 from an earlier run
  2. adlmidiplay ($ADLMIDI or build/libADLMIDI, tools/get_adlmidi.sh) + ffmpeg loudnorm: the Hellmatch render chain
  3. the Hellmatch content addon's rendered copy (sounds/fdm/music/<id>.mp3, read only): same render, same loudness
  4. tools/oplmidi.py: Freedoom's GENMIDI patches on a numpy OPL2 model (no external tools)
"""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets

OUT = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'build/music')
ADLMIDI = os.environ.get('ADLMIDI') or os.path.join(ROOT, 'build/libADLMIDI/build/adlmidiplay')
HELLMATCH_MUSIC = os.environ.get('HELLMATCH_CONTENT', r'C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/content/csgo_addons/mg_freedm') + '/sounds/fdm/music'
BANK, CHIPS = '72', '2'           # DMXOPL3 (Sneakernets, MIT), two OPL3 chips so no notes drop
TARGET = 'I=-16:TP=-1.5:LRA=11'
BOSS = os.environ.get('HZE_BOSS_TRACK', 'e2m8')     # Freedoom E2M8 (a Phase 1 boss level); Hellmatch has it compiled


def have(tool):
    return shutil.which(tool) is not None


def titles():
    # every current track (Phase 1, Phase 2, FreeDM); the 'Previously Featured' lists after them are old versions
    txt = open(os.path.join(assets.FD, 'CREDITS-MUSIC'), encoding='utf-8').read().split('--Previously Featured', 1)[0]
    out = {}
    for m in re.finditer(r'((?:DM|MAP)\d\d|E\dM\d): "([^"]+)" by (.+)', txt):
        out.setdefault(m.group(1).lower(), (m.group(2), m.group(3).strip()))
    return out


def render_adl(tid, mp3):
    tmp = os.path.join(CACHE, 'tmp'); os.makedirs(tmp, exist_ok=True)
    mid = os.path.join(tmp, tid + '.mid')
    shutil.copy(os.path.join(assets.FD, 'musics/d_%s.mid' % tid), mid)
    subprocess.run([ADLMIDI, mid, '--emu-nuked', '-vm', '3', '--gain', '1.0', BANK, CHIPS], cwd=tmp,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    wav = mid + '.wav'
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', wav, '-af', 'loudnorm=%s:print_format=json' % TARGET,
                          '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex('{'):err.rindex('}') + 1])
    af = ('loudnorm=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true'
          % (TARGET, m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset']))
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', wav, '-af', af, '-ar', '44100',
                    '-c:a', 'libmp3lame', '-b:a', '128k', mp3], check=True)
    os.remove(wav); os.remove(mid)


def track(tid):
    """(mp3 path, how) for a Freedoom track id ('map01', 'e2m8', ...)"""
    os.makedirs(CACHE, exist_ok=True)
    mp3 = os.path.join(CACHE, tid + '.mp3')
    if os.path.exists(mp3): return mp3, 'cached'
    if os.path.exists(ADLMIDI) and have('ffmpeg'):
        render_adl(tid, mp3); return mp3, 'adlmidi'
    hm = os.path.join(HELLMATCH_MUSIC, tid + '.mp3')
    if os.path.exists(hm):
        shutil.copy(hm, mp3); return mp3, 'hellmatch render'
    import oplmidi
    oplmidi.save(oplmidi.render(os.path.join(assets.FD, 'musics/d_%s.mid' % tid)), mp3)
    return mp3, 'oplmidi'


def seconds(path):
    if have('ffprobe'):
        return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]))
    from mutagen.mp3 import MP3
    return MP3(path).info.length


def opener():
    """the Hellmatch theme (music/theme.mp3); the Hellmatch content addon's loudness-matched copy when there is no ffmpeg"""
    tj = json.load(open(os.path.join(ROOT, 'music/tracks.json')))
    t = next(x for x in tj if x['pool'] == 'opener')
    hm = os.path.join(HELLMATCH_MUSIC, t['id'] + '.mp3')
    src = hm if os.path.exists(hm) else os.path.join(ROOT, 'music', t['file'])
    return t, src


levels = json.load(open(os.path.join(OUT, '_gen/levels.json')))
bases = sorted({L['base'] for L in levels})
names = titles()
d = os.path.join(OUT, 'sounds/fdm/music'); os.makedirs(d, exist_ok=True)
tracks = []
for pool, ids in (('level', bases), ('boss', [BOSS])):
    for tid in ids:
        src, how = track(tid)
        shutil.copy(src, os.path.join(d, tid + '.mp3'))
        title, by = names.get(tid, (tid.upper(), ''))
        tracks.append({'id': tid, 'pool': pool, 'seconds': round(seconds(src), 1), 'title': title, 'by': by,
                       'level': tid if pool == 'level' else '', 'source': how})
        print('music: %s %s (%s, %.0f s)' % (pool, tid, how, tracks[-1]['seconds']))
# Hellmatch's generated tracks (rendered and loudness-matched for Hellmatch, heard in game) join every level's playlist, so a
# round never rests on one short Freedoom render; level '' = any level (55_music.js)
for x in json.load(open(os.path.join(ROOT, 'music/tracks.json'))):
    if x['pool'] != 'long': continue
    hm = os.path.join(HELLMATCH_MUSIC, x['id'] + '.mp3')
    src = hm if os.path.exists(hm) else os.path.join(ROOT, 'music', x['file'])
    shutil.copy(src, os.path.join(d, x['id'] + '.mp3'))
    tracks.append({'id': x['id'], 'pool': 'level', 'seconds': round(seconds(src), 1), 'title': x['title'], 'by': x.get('by', ''),
                   'level': '', 'source': 'music/' + x['file']})
t, src = opener()
shutil.copy(src, os.path.join(d, t['id'] + '.mp3'))
tracks.append({'id': t['id'], 'pool': 'opener', 'seconds': round(seconds(src), 1), 'title': t['title'], 'by': t.get('by', ''),
               'level': '', 'source': 'music/' + t['file']})
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
json.dump(tracks, open(os.path.join(OUT, '_gen/music.json'), 'w'), indent=1)
lines = ['Hellmatch ZE music.', '',
         'Theme (opens every round): original music made for Hellmatch by skink52.',
         'Level and boss tracks from Freedoom, BSD licence like the rest of Freedoom, rendered from the original MIDI with',
         'libADLMIDI (Nuked OPL3, DMXOPL3 bank by Sneakernets, MIT) or with tools/oplmidi.py (Freedoom\'s own GENMIDI patches).', '']
lines += ['%-7s %-34s %s' % (x['id'].upper(), x['title'], x['by']) for x in tracks]
open(os.path.join(OUT, 'MUSIC_CREDITS.txt'), 'w', newline='\n').write('\n'.join(lines) + '\n')
print('music: %d tracks, %.1f MB' % (len(tracks), sum(os.path.getsize(os.path.join(d, x['id'] + '.mp3')) for x in tracks) / 1e6))
