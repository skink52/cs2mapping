"""sndevents.py: writes CS2 sound events (.vsndevts, kv3 text) and merges them into the addon's own
soundevents_addon.vsndevts without touching anything else in it.

Event kinds (each function returns the event's text, tab-indented for the root block):
  event_3d(name, vsnd, range_, volume=0.8)       csgo_mega placed in the world: full volume to 20 % of range_, silent at range_
  event_base(name, base, vsnd)                   an event that takes everything from `base` and only names its file
                                                 (one 3D base event, many sounds; as Hellmatch does it)
  event_music_flat(name, vsnd, volume)           csgo_mega heard everywhere at the same volume (flat 0..100000 curves, no
                                                 occlusion): follows the EFFECTS volume slider
  event_csgo_music(name, vsnd, volume=0.7)       csgo_music with volume_convar "snd_menumusic_volume": plays the same for
                                                 everyone and follows the Main Menu Music slider (the setting that held up
                                                 in Hellmatch; plain csgo_music spams "Unable to acquire convar value:
                                                 snd_musicvolume_<mode>" on some builds). Note: vsnd_files, not _track_01.
  wrap(events)                                   a complete file (kv3 header + root braces)

merge(template_text, events_text, tag) puts the events into the template between
    // ---- <tag> sound events (generated) ----
    ...
    // ---- end <tag> ----
and on a re-run replaces that block only, so it can be run again and again on the live addon file. events_text may
be bare events, a complete .vsndevts, or an earlier merge result (only its <tag> block is taken).

usage (import it):
    import sndevents as E
    ev = [E.event_3d('mygame.beep', 'sounds/mygame/beep.vsnd', 2000), E.event_csgo_music('mygame.music', 'sounds/mygame/m1.vsnd')]
    open('ours.vsndevts', 'w', newline='\\n').write(E.wrap(ev))
    text = E.merge(open(template).read(), E.wrap(ev), 'mygame')
CLI: merge_snd.py <template.vsndevts> <ours.vsndevts> --tag NAME [-o OUT]

From space-racer-cs2/tools/sounds.py and hellmatch-cs2/tools/extras.py (MIT), made project-neutral.
"""
import re

KV3_HEAD = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} '
            'format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->')


def curve(points, indent='\t\t'):
    """a distance -> value curve: [(distance, value), ...]"""
    out = [indent + '[']
    for dist, v in points:
        out += [indent + '\t[', indent + '\t\t%.1f, %.2f, 0.0, 0.0,' % (dist, v), indent + '\t\t2.0, 3.0,', indent + '\t],']
    return out + [indent + ']']


def _event(name, lines):
    return '\n'.join(['\t"%s" =' % name, '\t{'] + ['\t\t' + l if not l.startswith('\t\t') else l for l in lines] + ['\t}'])


def event_3d(name, vsnd, range_, volume=0.8, pitch=1.0, full=0.2, extra=()):
    """world sound: full volume up to full*range_, fading to silence at range_ (units)"""
    return _event(name, ['type = "csgo_mega"', 'volume = %.2f' % volume, 'pitch = %.2f' % pitch,
                         'vsnd_files_track_01 = "%s"' % vsnd, *extra, 'distance_volume_mapping_curve ='] +
                  curve([(0, 1), (range_ * full, 1), (range_, 0)]))


def event_base(name, base, vsnd, extra=()):
    """inherits type, volume and curve from the event `base`"""
    return _event(name, ['base = "%s"' % base, 'vsnd_files_track_01 = "%s"' % vsnd, *extra])


def event_base_3d(name, full_until=200, silent_at=1400, volume=1.0):
    """a base event with no file of its own: full volume to full_until, silent at silent_at (Hellmatch: 200 / 1400)"""
    return _event(name, ['type = "csgo_mega"', 'volume = %.2f' % volume, 'pitch = 1.0', 'distance_volume_mapping_curve ='] +
                  curve([(0, 1), (full_until, 1), (silent_at, 0)]))


def event_music_flat(name, vsnd, volume=0.3):
    """heard everywhere at the same volume, not placed in the world (stereo, no fall-off, no occlusion)"""
    return _event(name, ['type = "csgo_mega"', 'volume = %.2f' % volume, 'pitch = 1.0', 'vsnd_files_track_01 = "%s"' % vsnd,
                         'occlusion_intensity = 0.0', 'distance_effect_mix = 0.0', 'restrict_source_reverb = true',
                         'use_distance_unfiltered_stereo_mapping_curve = true', 'distance_volume_mapping_curve ='] +
                  curve([(0, 1), (100000, 1)]) + ['distance_unfiltered_stereo_mapping_curve ='] + curve([(0, 1), (100000, 1)]))


def event_csgo_music(name, vsnd, volume=0.7, volume_convar='snd_menumusic_volume'):
    """music for everyone at each player's own music volume (volume_convar None = plain csgo_music)"""
    lines = ['type = "csgo_music"', 'volume = %.2f' % volume]
    if volume_convar: lines.append('volume_convar = "%s"' % volume_convar)
    lines.append('vsnd_files = "%s"' % vsnd)
    return _event(name, lines)


def wrap(events):
    """complete .vsndevts text from a list of event texts (or one string)"""
    body = events if isinstance(events, str) else '\n'.join(events)
    return KV3_HEAD + '\n{\n' + body.rstrip('\n') + '\n}\n'


# ---------------------------------------------------------------- merging
def markers(tag):
    return '// ---- %s sound events (generated) ----' % tag, '// ---- end %s ----' % tag


def _block_re(tag):
    t = re.escape(tag)
    return re.compile(r'^[ \t]*// ---- %s( [^\n]*)?\n(.*?)^[ \t]*// ---- end %s ----[ \t]*\n?' % (t, t), re.S | re.M)


def body_of(text, tag=None):
    """the events inside a .vsndevts text: the <tag> block if there is one, else everything inside the root braces,
    else the text itself (bare events)"""
    if tag:
        m = _block_re(tag).search(text)
        if m: return m.group(2)
    if re.search(r'^\{', text, re.M):
        a = re.search(r'^\{[ \t]*\n?', text, re.M).end()      # the first line that is just the root brace
        return text[a:text.rindex('}')]
    return text


def event_names(text):
    return re.findall(r'^[ \t]*"([^"]+)"\s*=', text, re.M)


def merge(template_text, events_text, tag):
    """template with our events in the <tag> block (replacing an older block of ours). Returns the new text.
    Raises ValueError if the template has, outside our block, an event with the same name as one of ours."""
    ours = body_of(events_text, tag).strip('\n')
    start, end = markers(tag)
    block = '\t%s\n%s\n\t%s\n' % (start, ours, end)
    if not template_text.strip():
        return wrap(block.rstrip('\n'))
    rx = _block_re(tag)
    rest = rx.sub('', template_text)
    clash = sorted(set(event_names(ours)) & set(event_names(rest)))
    if clash: raise ValueError('the template already has these events outside the %s block: %s' % (tag, clash))
    if rx.search(template_text):
        return rx.sub(lambda m: block, template_text, count=1)
    m = re.search(r'^\{[ \t]*\n?', template_text, re.M)
    if not m: raise ValueError('no root "{" line in the template')
    return template_text[:m.end()] + block + template_text[m.end():]
