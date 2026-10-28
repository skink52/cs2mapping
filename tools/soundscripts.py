"""Stage C step `soundscripts`: Source 1 soundscript names (`MetalGrate.ImpactHard`, `Doors.Move1`) that the map's entities use are
silent in CS2, because CS2 only plays soundevents. Each one becomes a soundevent with the SAME name in soundevents_addon.vsndevts,
so no entity has to change. The definitions come from the map's own soundscripts (embedded `maps/<map>_level_sounds.txt`,
`scripts/*.txt`) first, then CS:GO's `scripts/game_sounds_manifest.txt` files. Waves are taken from the addon, stock CS2 (`sounds/...vsnd_c`)
or extracted from CS:GO's VPK (non-16-bit wavs re-encoded, smpl loops given a cue).
Names are looked for in every entity keyvalue of the vmap and in the VMF's func_door noise1/noise2 (the importer drops those; the
`doors` step then points the door at the event, see c.soundscript_events).
Method from github.com/Ninja-Chris/cs2-slop-porting (vmap_asset_slop_import.py), written fresh for this pipeline.
"""
import os, re, json

PREFIX_CHARS = '*^)(}$!?&~`+%<>#@'
# names CS2 uses for gameplay: an addon event of the same name would replace the stock sound map-wide
STOCK_PREFIXES = ('weapon', 'player', 'bot.', 'radio', 'c4.', 'survival', 'ui.', 'music', 'buttons.', 'basecombat', 'physics.', 'flesh', 'default.')

EVENT = '''	// %(comment)s
	"%(name)s" =
	{
		base = "%(base)s"
		volume = %(vol).2f
%(pitch)s		use_time_volume_mapping_curve = false
		vsnd_files_track_01 = %(files)s
		distance_volume_mapping_curve =
		[
			[
				0.0, 1.0, 0.0, 0.0,
				2.0, 3.0,
			],
			[
				%(radius).1f, %(far).1f, 0.0, 0.0,
				2.0, 3.0,
			],
		]
	}
'''

def _tokens(text):
    text = re.sub(r'//[^\n]*', '', text)
    return re.findall(r'"[^"]*"|[{}]|[^\s{}"]+', text)

def parse(text):
    """soundscript file -> {lower name: {'name', 'waves': [...], 'volume', 'pitch', 'soundlevel'}}"""
    t = _tokens(text); out = {}; i = 0
    while i + 1 < len(t):
        if t[i] not in '{}' and t[i + 1] == '{':
            name = t[i].strip('"'); d = {'name': name, 'waves': [], 'volume': None, 'pitch': None, 'soundlevel': None}
            depth = 1; j = i + 2
            while j < len(t) and depth:
                x = t[j]
                if x == '{': depth += 1
                elif x == '}': depth -= 1
                elif j + 1 < len(t) and t[j + 1] not in '{}':
                    k = x.strip('"').lower(); v = t[j + 1].strip('"')
                    if k == 'wave': d['waves'].append(v)
                    elif k in ('volume', 'pitch', 'soundlevel', 'attenuation') and d.get(k if k != 'attenuation' else 'soundlevel') is None:
                        d['soundlevel' if k == 'attenuation' else k] = (('ATTN:' + v) if k == 'attenuation' else v)
                    j += 1
                j += 1
            out.setdefault(name.lower(), d); i = j
        else:
            i += 1
    return out

def index(src):
    """{lower name: definition} from the map's embedded soundscripts first, then CS:GO's manifest"""
    idx = {}
    for p in sorted(src.local):
        if p.endswith('.txt') and (p.startswith('maps/') and p.endswith('_level_sounds.txt') or p.startswith('scripts/') and ('sound' in p)):
            for k, v in parse(open(src.local[p], 'rb').read().decode('utf-8', 'replace')).items():
                idx.setdefault(k, dict(v, file=p))
    man = src.read('scripts/game_sounds_manifest.txt') if src.has('scripts/game_sounds_manifest.txt') else None
    files = re.findall(r'"(?:precache_file|preload_file|file)"\s+"([^"]+)"', man.decode('utf-8', 'replace'), re.I) if man else []
    for f in files:
        f = f.lower().replace('\\', '/')
        if not src.has(f): continue
        data = src.read(f)
        if data is None: continue                       # waiting on a VPK chunk (c.need)
        for k, v in parse(data.decode('utf-8', 'replace')).items():
            idx.setdefault(k, dict(v, file=f))
    return idx

def _num(v, default):
    if v is None: return default
    v = v.strip().upper()
    if v.startswith('VOL_NORM') or v.startswith('PITCH_NORM'): return default
    if v.startswith('PITCH_LOW'): return 95.0
    if v.startswith('PITCH_HIGH'): return 120.0
    nums = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', v)]
    return sum(nums) / len(nums) if nums else default

def radius_of(sl):
    """soundscript soundlevel / attenuation -> (radius, play everywhere). 75 dB (SNDLVL_NORM) ~ the ambient_generic default 1250."""
    if sl is None: return 1250.0, False
    s = sl.strip().upper()
    if s.startswith('ATTN:'):
        a = s[5:]
        if 'NONE' in a: return 0.0, True
        a = {'ATTN_NORM': 0.8, 'ATTN_IDLE': 2.0, 'ATTN_STATIC': 1.25, 'ATTN_RICOCHET': 1.5, 'ATTN_GUNFIRE': 0.27}.get(a, None) or _num(a, 0.8)
        return (0.0, True) if a <= 0 else (1250.0 * 0.8 / a, False)
    if 'NONE' in s: return 0.0, True
    named = {'SNDLVL_IDLE': 60, 'SNDLVL_TALKING': 60, 'SNDLVL_STATIC': 66, 'SNDLVL_NORM': 75, 'SNDLVL_GUNFIRE': 140}
    lvl = next((float(v) for k, v in named.items() if s.startswith(k)), None) or _num(s, 75.0)
    if lvl <= 0: return 0.0, True
    return 1250.0 * 25.0 / max(lvl - 50.0, 5.0), False

def _used_names(m, idx, vmfpath):
    used = {}
    for e in m.entities():
        for name, at, v in m.props(e)['attrs']:
            if not isinstance(v, (bytes, str)): continue
            s = v.decode('utf-8', 'replace') if isinstance(v, bytes) else v
            if '.' in s and ' ' not in s and s.lower() in idx and name not in (b'classname', b'targetname'):
                used.setdefault(s.lower(), set()).add('%s %s' % (m.cls(e), m.name(e) or '(unnamed)'))
    if vmfpath and os.path.exists(vmfpath):
        import stage_c
        for cls, nm, _, snd in stage_c.vmf_door_sounds(vmfpath):
            for v in snd.values():
                if v.lower() in idx: used.setdefault(v.lower(), set()).add('%s %s' % (cls, nm or '(unnamed)'))
    return used

def run(m, c, vmfpath=None):
    if c.src is None: return
    import stage_c
    idx = index(c.src)
    used = _used_names(m, idx, vmfpath)
    c.soundscript_events = getattr(c, 'soundscript_events', {})
    if not used: return
    evp = os.path.join(c.content, 'soundevents', 'soundevents_addon.vsndevts')
    ev = c.files.get('soundevents/soundevents_addon.vsndevts')
    ev = ev.decode('utf-8') if ev else (open(evp, encoding='utf-8').read() if os.path.exists(evp) else '{\n}\n')
    have = set(x.lower() for x in re.findall(r'^\s*"([^"]+)"\s*=', re.sub(r'//[^\n]*', '', ev), re.M))
    added, stock, missing, partial, extracted, converted = {}, [], [], [], set(), []
    for key in sorted(used):
        d = idx[key]; nm = d['name']
        if key in have: c.soundscript_events[key] = nm; continue
        if key.startswith(STOCK_PREFIXES): stock.append(nm); continue
        files, lost = [], []
        for w in d['waves']:
            rel = w.lstrip(PREFIX_CHARS).replace('\\', '/').lstrip('/').lower()
            if not rel: continue
            stem, ext = os.path.splitext(rel)
            exts = [ext] if ext else ['.wav', '.mp3']
            src = next(('sounds/' + stem + x for x in exts if c.exists('sounds/' + stem + x)), None)
            if src is None and c.cs2v and c.cs2v.has('sounds/' + stem + '.vsnd_c'): src = 'sounds/' + stem + '.vsnd'
            if src is None:
                for x in exts:
                    if c.src.has('sound/' + stem + x):
                        data = c.src.read('sound/' + stem + x)
                        if data is None: break
                        src = 'sounds/' + stem + x; c.write(src, data); extracted.add(src); break
            if src is None: lost.append(rel); continue
            lp = os.path.join(c.content, src)
            data = c.files.get(src) or (open(lp, 'rb').read() if src.endswith('.wav') and os.path.exists(lp) else None)
            if src.endswith('.wav') and data:
                nw, note = stage_c.wav_to_pcm16(data)
                if nw: data = nw; c.write(src, nw); converted.append('%s (%s)' % (os.path.basename(src), note))
                if b'smpl' in data and b'cue ' not in data:
                    cued = stage_c.wav_add_cue(data)
                    if cued: c.write(src, cued)
            files.append(os.path.splitext(src)[0] + '.vsnd')
        files = list(dict.fromkeys(files))
        if not files: missing.append('%s (%s)' % (nm, ', '.join(lost) or 'no waves')); continue
        if lost: partial.append('%s (missing %s)' % (nm, ', '.join(lost)))
        radius, everywhere = radius_of(d['soundlevel'])
        pitch = _num(d['pitch'], 100.0) / 100.0
        added[key] = EVENT % dict(comment='soundscript %s (%s), used by %s' % (nm, d['file'], ', '.join(sorted(used[key]))[:150]), name=nm,
                                  base='amb.looping.stereo.base' if everywhere else 'amb.base', vol=max(0.0, min(1.0, _num(d['volume'], 1.0))),
                                  pitch=('\t\tpitch = %.2f\n' % pitch) if abs(pitch - 1) > 0.01 else '',
                                  files=('"%s"' % files[0]) if len(files) == 1 else '[ %s ]' % ', '.join('"%s"' % f for f in files),
                                  radius=100000.0 if everywhere else max(radius, 64.0), far=1.0 if everywhere else 0.0)
        c.soundscript_events[key] = nm
    if added:
        block = '\n\t///////////////////////////////////////////////////////////\n\t/////////////// SOUNDSCRIPTS - Source 1 soundscript names used by the map, added by the CS2 post-import clean\n\n' + '\n'.join(added.values())
        i = ev.rstrip().rfind('}')
        c.write('soundevents/soundevents_addon.vsndevts', ev[:i] + block + ev[i:])
        c.log.append('%d Source 1 soundscript names used by entities defined as same-named soundevents: %s' % (len(added), ', '.join(idx[k]['name'] for k in sorted(added))))
    if extracted: c.log.append('soundscript waves copied into the addon from the map's packed files / CS:GO VPK: %s' % ', '.join(sorted(extracted))[:600])
    if converted: c.log.append('soundscript wavs re-encoded to 16-bit PCM: %s' % ', '.join(converted))
    if stock: c.todo.append('soundscript names left alone because CS2 likely has a stock event of that name (an addon copy would replace it map-wide): %s' % ', '.join(stock))
    if partial: c.todo.append('soundscript events built with some waves missing: %s' % '; '.join(partial)[:600])
    if missing: c.todo.append('soundscript names with no wave found in the addon, CS2 or CS:GO (still silent): %s' % '; '.join(missing)[:600])
