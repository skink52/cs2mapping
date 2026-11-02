"""Random music for a course map that has none: a shuffled song at round start, and the next one when it ends.

  python coursemusic.py <addon content dir> <vmap in> <vmap out> <song.mp3[=name]> [...] [--volume 0.6]

A song's name is its file name unless given after '=': other maps' songs are often all called disco1/2/3 but are different tracks,
so name them after where they came from (skylight_1, seaside_inthenavy).

Each song is copied to sounds/port_music/, gets a "play everywhere" soundevent in soundevents/soundevents_addon.vsndevts, and an
ambient_generic port_music_<n> (play everywhere, start silent, not looped), the way the maps that came with music do it (mg_metal_course_level_2's
musicselector). A logic_case port_music_case picks one with PickRandomShuffle 1 s into the round (port_logic_auto); that song's logic_relay
plays it and asks the case for another once the song's length (read from the file) has passed, so nothing loops (skink52, 3 Nov 2026).
Map entities are made again every round, so each round starts a fresh song. Songs whose tags name them are listed in
sounds/port_music/credits.txt for the Steam description. At least 3 songs; a map that already has port_music_case is left alone.
"""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V
try: import mutagen
except ImportError: mutagen = None

HEADER = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n{\n}\n'
EVENT = '''	// port music (coursemusic.py)
	"port_music.%s" =
	{
		base = "amb.looping.stereo.base"
		volume = %.2f
		use_time_volume_mapping_curve = false
		vsnd_files_track_01 = "sounds/port_music/%s.vsnd"
		distance_volume_mapping_curve =
		[
			[
				0.0, 1.0, 0.0, 0.0,
				2.0, 3.0,
			],
			[
				100000.0, 1.0, 0.0, 0.0,
				2.0, 3.0,
			],
		]
	}
'''

def slug(path): return re.sub(r'[^a-z0-9]+', '_', os.path.splitext(os.path.basename(path))[0].lower()).strip('_')[:48]

def length(path):
    if mutagen is None: sys.exit('coursemusic: needs mutagen (python -m pip install --user mutagen) to read song lengths')
    f = mutagen.File(path)
    if not f or not f.info.length: raise ValueError('cannot read the length of ' + path)
    return float(f.info.length)

def credit(path):
    """'Title by Artist (Album)' from the file's tags, or '' when it has none (most songs carried over from CS:GO maps)"""
    t = (mutagen.File(path).tags or {}) if mutagen else {}
    g = lambda k: str(t.get(k) or '').strip()
    return ('%s by %s' % (g('TIT2'), g('TPE1')) if g('TPE1') else g('TIT2')) + (' (%s)' % g('TALB') if g('TALB') and g('TIT2') else '') if g('TIT2') else ''

def run(m, content, songs, volume=0.6):
    if any(m.name(e) == 'port_music_case' for e in m.by_class('logic_case')): return 'music: port_music_case already there, left alone'
    if len(songs) < 3: return 'music: needs at least 3 songs'
    if len(songs) > 16: songs = songs[:16]   # logic_case has 16 cases
    la = next((e for e in m.by_class('logic_auto') if m.name(e) == 'port_logic_auto'), None)
    if la is None: return 'music: no port_logic_auto (run round setup first)'
    ev = os.path.join(content, 'soundevents', 'soundevents_addon.vsndevts'); os.makedirs(os.path.dirname(ev), exist_ok=True)
    text = open(ev, encoding='utf-8').read() if os.path.exists(ev) else HEADER
    o = m.origin(la); case = m.new_entity('logic_case', [o[0], o[1] + 64, o[2]], {'targetname': 'port_music_case'})
    names, credits = [], []
    for i, src in enumerate(songs, 1):
        src, _, nm = src.rpartition('=') if '=' in os.path.basename(src) else (src, '', '')
        s = slug(nm or src); n = 'port_music_%d' % i; secs = length(src)
        dst = os.path.join(content, 'sounds', 'port_music', s + '.mp3'); os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.abspath(src) != os.path.abspath(dst): shutil.copy2(src, dst)
        if '"port_music.%s"' % s not in text:
            k = text.rstrip().rfind('}'); text = text[:k] + EVENT % (s, volume, s) + text[k:]
        pos = [o[0] + 32 * i, o[1] + 96, o[2]]
        m.new_entity('ambient_generic', pos, {'targetname': n, 'message': 'port_music.' + s, 'spawnflags': '49', 'health': '10', 'radius': '1250'})
        r = m.new_entity('logic_relay', [pos[0], pos[1] + 32, pos[2]], {'targetname': n + '_relay', 'spawnflags': '0'})
        m.add_conn(r, 'OnTrigger', n, 'PlaySound', '', 0.0, -1)
        m.add_conn(r, 'OnTrigger', 'port_music_case', 'PickRandomShuffle', '', round(secs + 2.0, 1), -1)
        m.add_conn(case, 'OnCase%02d' % i, n + '_relay', 'Trigger', '', 0.0, -1)
        m.setp(case, 'Case%02d' % i, str(i))
        names.append('%s (%d:%02d)' % (s, secs // 60, secs % 60))
        if credit(src): credits.append(credit(src))
    m.add_conn(la, 'OnMapSpawn', 'port_music_case', 'PickRandomShuffle', '', 1.0, -1)
    open(ev, 'w', encoding='utf-8', newline='\n').write(text)
    # the Steam description credits these (autoport's description step reads it)
    open(os.path.join(content, 'sounds', 'port_music', 'credits.txt'), 'w', encoding='utf-8').write(''.join(c + '\n' for c in credits))
    return 'music: %d songs shuffled from round start, the next when one ends: %s' % (len(songs), ', '.join(names))

if __name__ == '__main__':
    a = sys.argv[1:]; vol = 0.6
    if '--volume' in a: i = a.index('--volume'); vol = float(a[i + 1]); del a[i:i + 2]
    if len(a) < 6: sys.exit(__doc__)
    m = V.Map(a[1]); msg = run(m, a[0], a[3:], vol); print(msg)
    if msg.startswith('music: %d songs' % min(len(a) - 3, 16)): m.save(a[2])
