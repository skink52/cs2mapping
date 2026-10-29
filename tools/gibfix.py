"""Missing gibs and model materials, from a build log -> a refs file the PC imports with modelsfromrefs.py (run_fixrefs.bat).

  python3 gibfix.py <build log (UTF-16 or UTF-8)> <out refs.txt> [<addon vmdl> ...]

1. Every `Failed loading resource "…"` in the build log:
   - models/…vmdl_c (break pieces of imported models, or of stock CS2 models whose gibs CS2 never shipped, e.g. watermelon01a's
     props_junk/watermelon01_chunk*) -> "file" "models/….mdl" (cs_mdl_import from the CS:GO content, with its materials);
   - materials/…vmat_c (model materials the importer missed) -> "file" "materials/….vmt";
   - materials/…_<ext>_<hash>.vtex_c (a material whose texture never converted) -> the owning .vmt (name minus _color/_normal/… );
     _psd_ ones are Valve source textures (stock CS2 materials) and are only reported.
2. Each <addon vmdl> given (a CS:GO prop that broke into generic chunks: propdata base Metal.* / Wooden.* / Glass.* with no gib
   models of its own, e.g. de_train/barrel) gets a BreakPieceList with CS:GO's generic chunks (models/gibs/metal_gib1-5,
   wood_gib01a-e, glass_shard01-06) and a break_uniform_burst; the chunk models are added to the refs.
"""
import re, sys, os

GENERIC = {'metal': ['models/gibs/metal_gib%d' % i for i in range(1, 6)],
           'wood': ['models/gibs/wood_gib01%s' % c for c in 'abcde'],
           'glass': ['models/gibs/glass_shard%02d' % i for i in range(1, 7)]}
SUFFIX = ('_color', '_normal', '_rough', '_trans', '_selfillum', '_mask', '_ao', '_metal', '_tintmask', '_detail')


def read_log(p):
    b = open(p, 'rb').read()
    for enc in ('utf-16', 'utf-8'):
        try:
            t = b.decode(enc)
            if 'Failed' in t or 'resource' in t: return t
        except UnicodeDecodeError: pass
    return b.decode('utf-8', 'replace')


def from_log(text):
    refs, notes = [], []
    for r in sorted(set(re.findall(r'Failed loading resource "([^"]+)"', text))):
        if r.startswith('scripts/detail_prop_types'): continue
        if r.endswith('.vmdl_c'): refs.append(r[:-7] + '.mdl')
        elif r.endswith('.vmat_c'): refs.append(r[:-7] + '.vmt')
        elif r.endswith('.vtex_c'):
            m = re.match(r'(.*)_(tga|png|psd|jpg|exr)_[0-9a-f]{6,}\.vtex_c$', r)
            if not m: notes.append('%s: no source name' % r); continue
            if m.group(2) == 'psd': notes.append('%s: Valve source texture of a stock material, not importable' % r); continue
            base = m.group(1)
            for s in SUFFIX:
                if base.endswith(s): base = base[:-len(s)]; break
            refs.append(base + '.vmt')
        else: notes.append('%s: not handled' % r)
    return refs, notes


PIECE = '''					{
						_class = "BreakPieceExternal"
						placement_mode = "default"
						placement_bone = ""
						placement_attach = ""
						sound_event_on_spawn = ""
						spawn_entity = "prop_physics"
						ragdoll_applies_bind_pose_root = false
						collision_group = "debris"
						offset = [ 0.0, 0.0, 0.0 ]
						offset_rotation = [ 0.0, 0.0, 0.0 ]
						fadetime = 10.0
						name_mode = "none"
						random_spawn_chance = 1.0
						suppress_creation_on_death = false
						is_essential_piece = false
						can_player_pickup_piece = false
						render_color_mode = "inherit_owner"
						material_group_mode = "none"
						physics_joint_modification_type = "none"
						specific_physics_body_to_replace = ""
						massoverride = -1.0
						model = "%s.vmdl"
						force_motion_disabled = false
						health_override = 10
					},
'''
BURST = '''					{
						_class = "BreakCommand"
						game_class = "break_uniform_burst"
						game_keys =
						{
							offset = [ 0.0, 0.0, 0.0 ]
							attachment_point = ""
							center_on_damage_point = false
							limit_to_piece = ""
							burst_scale = 100.0
							burst_randomize = 0.0
						}
					},
'''


def add_generic(text):
    """returns (new text, gib models) or (text, []) when the model already has gibs / no matching propdata base"""
    if 'BreakPieceList' in text: return text, []
    m = re.search(r'base = "([^"]+)"', text)
    kind = None
    if m:
        b = m.group(1).lower()
        kind = 'metal' if b.startswith('metal') else 'wood' if b.startswith('wood') else 'glass' if b.startswith('glass') else None
    if not kind: return text, []
    gibs = GENERIC[kind]
    block = '\t\t\t{\n\t\t\t\t_class = "BreakPieceList"\n\t\t\t\tchildren = \n\t\t\t\t[\n' + ''.join(PIECE % g for g in gibs) + '\t\t\t\t]\n\t\t\t},\n'
    i = text.index('children = ', text.index('_class = "RootNode"'))
    j = text.index('[', i) + 1
    j = text.index('\n', j) + 1
    text = text[:j] + block + text[j:]
    gd = text.find('_class = "GameDataList"')
    if gd >= 0 and 'break_uniform_burst' not in text:
        k = text.index('[', gd) + 1; k = text.index('\n', k) + 1
        text = text[:k] + BURST + text[k:]
    return text, [g + '.mdl' for g in gibs]


def write_refs(path, entries):
    seen = []
    for e in entries:
        if e not in seen: seen.append(e)
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('// missing gibs / model materials, from gibfix.py; import with run_fixrefs.bat <addon>\n')
        for e in seen: f.write('"file" "%s"\n' % e)
    return seen


if __name__ == '__main__':
    a = sys.argv[1:]
    refs, notes = from_log(read_log(a[0]))
    for vp in a[2:]:
        raw = open(vp, encoding='utf-8', newline='').read()
        crlf = '\r\n' in raw
        t, gibs = add_generic(raw.replace('\r\n', '\n'))
        if gibs:
            open(vp, 'w', encoding='utf-8', newline='').write(t.replace('\n', '\r\n') if crlf else t); refs += gibs
            print('generic gibs added to', vp, '(%d)' % len(gibs))
        else: print('no generic gibs for', vp, '(has gibs already, or no Metal/Wooden/Glass propdata base)')
    out = write_refs(a[1], refs)
    print('\n'.join(out)); print('\n'.join('NOTE: ' + n for n in notes))
