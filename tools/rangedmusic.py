"""Ranged music keeps playing out of range: CS2's csgo_mega stack stops a voice once its distance volume drops below
`voice_culling_threshold` (default 0.001). A non-looping sound (music mp3s, wavs without loop markers) then ends for good, so music with a
range (jail jukeboxes, disco rooms) didn't come back when you walked back in, and never started for anyone out of range when it was triggered.
Looping wavs were culled and restarted from the beginning. CS:GO kept the sound playing silently out of range.

This adds `voice_culling_threshold = -1.0` to every event in soundevents_addon.vsndevts that has a range (its distance volume curve,
own or inherited through `base`, reaches 0) and whose audio is at least --min seconds long (music and long ambience, not short SFX).
The voice then keeps running silently, so the music is at the right point when you come back. Global (play everywhere) events are
untouched. Rerun-safe: events that already set the threshold are left alone.

    python rangedmusic.py <content addon dir> [--min 20] [--dry]     prints what it changed (or would change)
    python rangedmusic.py --all <content_addons dir> [--min 20] [--dry]

Needs mutagen for mp3 lengths. Recompile the vsndevts afterwards (resourcecompiler, or open the addon in the tools).
Found from CS2's compiled soundstacks/soundstacks_csgo_mega.vsndstck_c (operators distance_volume_greater_than_zero,
switch_start_mode, culling_and_unstopped), 9 Nov 2026.
"""
import os, re, sys, wave

KEY = 'voice_culling_threshold'
LINE = '\t\t%s = -1.0\t// keep playing silently out of range so it resumes in step (rangedmusic.py)\n' % KEY


def _strip(text):
    return re.sub(r'//[^\n]*', lambda m: ' ' * len(m.group(0)), text)


def events(text):
    """[(name, start of '{', end after '}')] for the events inside the root block"""
    s = _strip(text); out = []
    s = re.sub(r'<!--.*?-->', lambda m: ' ' * len(m.group(0)), s, flags=re.S)   # the kv3 header has braces in it
    root = s.find('{')
    for m in re.finditer(r'"([^"]+)"\s*=\s*\{', s):
        if m.start() < root: continue
        depth = 0; i = m.end() - 1
        # only events at depth 1 (directly in the root block)
        if s[root:m.start()].count('{') - s[root:m.start()].count('}') != 1: continue
        while i < len(s):
            if s[i] == '{': depth += 1
            elif s[i] == '}':
                depth -= 1
                if depth == 0: break
            i += 1
        out.append((m.group(1), m.end() - 1, i + 1))
    return out


def _field(body, key):
    m = re.search(r'(?m)^\s*%s\s*=\s*' % re.escape(key), body)
    if not m: return None
    rest = body[m.end():]
    if rest.startswith('['):
        depth = 0
        for i, ch in enumerate(rest):
            depth += ch == '['; depth -= ch == ']'
            if depth == 0: return rest[:i + 1]
    return rest.split('\n', 1)[0].strip()


def _last_point(curve):
    nums = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?(?:e-?\d+)?', curve)]
    pts = [nums[i:i + 6] for i in range(0, len(nums) - 5, 6)]
    return (pts[-1][0], pts[-1][1]) if pts else None


def ranged(name, bodies, seen=None):
    """(max distance, volume there) of the event's distance volume curve, through its base chain; None if it has none"""
    seen = seen or set()
    if name in seen or name not in bodies: return None
    seen.add(name)
    c = _field(bodies[name], 'distance_volume_mapping_curve')
    if c: return _last_point(c)
    base = _field(bodies[name], 'base')
    return ranged(base.strip('"'), bodies, seen) if base else None


def _inherit(name, bodies, key, seen=None):
    seen = seen or set()
    if name in seen or name not in bodies: return None
    seen.add(name)
    v = _field(bodies[name], key)
    if v is not None: return v
    base = _field(bodies[name], 'base')
    return _inherit(base.strip('"'), bodies, key, seen) if base else None


def length(content, vsnd):
    """seconds of a .vsnd's source (wav/mp3 next to it in the content addon), None if not found"""
    stem = os.path.splitext(os.path.join(content, vsnd.replace('/', os.sep)))[0]
    for ext in ('.wav', '.mp3', '.ogg', '.flac'):
        p = stem + ext
        if not os.path.exists(p): continue
        try:
            if ext == '.wav':
                with wave.open(p) as w: return w.getnframes() / float(w.getframerate())
            import mutagen
            f = mutagen.File(p)
            return f.info.length if f else None
        except Exception:
            try:
                import mutagen
                f = mutagen.File(p); return f.info.length if f else None
            except Exception: return None
    return None


def length_of_bytes(data):
    """seconds of wav/mp3 bytes (stage C keeps extracted files in memory), None if unknown"""
    import io
    try:
        if data[:4] == b'RIFF':
            with wave.open(io.BytesIO(data)) as w: return w.getnframes() / float(w.getframerate())
    except Exception: pass
    try:
        import mutagen
        f = mutagen.File(io.BytesIO(data)); return f.info.length if f else None
    except Exception: return None


def fix(content, min_len=20.0, dry=False):
    p = os.path.join(content, 'soundevents', 'soundevents_addon.vsndevts')
    if not os.path.exists(p): return []
    text = open(p, encoding='utf-8', errors='replace').read()
    text, done = apply_text(text, lambda v: length(content, v), min_len)
    if done and not dry:
        open(p, 'w', encoding='utf-8', newline='').write(text)
    return done


def apply_text(text, length_fn, min_len=20.0):
    """-> (new text, [what changed]); length_fn(vsnd path) -> seconds or None"""
    evs = events(text)
    bodies = {n: text[a:b] for n, a, b in evs}
    done = []
    for n, a, b in sorted(evs, key=lambda e: -e[1]):            # back to front so offsets stay valid
        body = bodies[n]
        if n.endswith('.base') or _field(body, 'vsnd_files_track_01') is None and _field(body, 'vsnd_files') is None: continue
        if _field(body, KEY) is not None: continue
        typ = (_inherit(n, bodies, 'type') or '').strip('"')
        if typ and typ != 'csgo_mega': continue                 # csgo_music etc. have no distance culling
        lp = ranged(n, bodies)
        if lp is None or lp[1] > 0.0 or lp[0] >= 50000: continue  # no range, or heard everywhere
        files = re.findall(r'"([^"]+\.vsnd)"', _field(body, 'vsnd_files_track_01') or _field(body, 'vsnd_files') or '')
        secs = max([x for x in (length_fn(f) for f in files) if x] or [0])
        if secs < min_len: continue
        nl = text.index('\n', a) + 1                            # just after the event's opening brace
        text = text[:nl] + LINE + text[nl:]
        done.append('%s (%s, %.0f s, silent at %.0f u)' % (n, ', '.join(os.path.basename(f) for f in files), secs, lp[0]))
    return text, done[::-1]


def main(a):
    dry = '--dry' in a; a = [x for x in a if x != '--dry']
    min_len = 20.0
    if '--min' in a:
        i = a.index('--min'); min_len = float(a[i + 1]); del a[i:i + 2]
    if a and a[0] == '--all':
        root = a[1]; dirs = [os.path.join(root, d) for d in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, d))]
    else:
        dirs = a
    if not dirs: print(__doc__); return 2
    for d in dirs:
        done = fix(d, min_len, dry)
        if done: print('%s%s: %s' % ('(dry) ' if dry else '', os.path.basename(d.rstrip('/\\')), '; '.join(done)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
