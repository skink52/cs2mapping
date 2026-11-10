"""Release one map in its own clean addon: find every addon file the map uses, plan the new addon, write PUBLISH.md. Dry run by default.

  python release.py <content addon>/maps/<map>.vmap [--name NEWADDON] [--json]                 plan + PUBLISH.md text, writes nothing
  python release.py <map.vmap> --apply [--name NEWADDON] [--root CS2] [--force]                copy into content/ and game/csgo_addons/<name>

What goes in: the map (and the 3D skybox maps its skybox_reference entities name), then every addon-local file reachable from it:
entity keys and mesh materials, the map's asset references, and inside text resources (.vmat, .vmdl, .vpcf, .vsndevts, .vpost, .vsmart,
.vdata, panorama .xml / .css / .js) any quoted path with a known extension, recursively; sources map to their compiled _c in the game
folder. Also: soundevents_addon.vsndevts, the radar (resource/overviews/<map>.txt + materials/overviews/<map>_radar*), loading slides and
icons (panorama/images/map_icons/**/<map>*), and addoninfo.txt. Stock files (in CS2's VPKs) stay out; files found nowhere are listed.
The compiled .vpk and _c files are copied as they are: build the new addon again (rcompile.py map ... --preset final) if PUBLISH.md says
compiled files are missing or older than their sources.

Never uploads. PUBLISH.md has the Workshop Manager steps; skink52 uploads by hand.

From release.py / releaserun.py in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): map_build(name, "release") and PUBLISH.md.
Fresh code on skink52's vmapedit, fgdcheck asset lookup and rcompile path rules.
"""
import argparse, glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, fgdcheck, fgdcat

TEXT_EXT = ('.vmat', '.vmdl', '.vpcf', '.vsndevts', '.vpost', '.vsmart', '.vdata', '.xml', '.css', '.js', '.vsnap', '.txt', '.vmorf')
REF = re.compile(r'''["'=\s]((?:[\w\-. ]+/)+[\w\-. ]+\.(?:vmat|vmdl|vpcf|vtex|vsnd|vsndevts|vpost|vsmart|vdata|vjs|vxml|vcss|png|tga|psd|jpg|jpeg|exr|'''
                 r'''fbx|smd|dmx|obj|wav|mp3|xml|css|js|vmap|svg|vanmgrph|vnmskel|vmdl_c))(?=["'\s;,)}\]]|$)''', re.I)
COMPILED = {'.js': '.vjs', '.xml': '.vxml', '.css': '.vcss', '.wav': '.vsnd', '.mp3': '.vsnd', '.png': '.vtex', '.tga': '.vtex', '.psd': '.vtex'}
RAW = ('.fbx', '.smd', '.dmx', '.obj', '.png', '.tga', '.psd', '.jpg', '.jpeg', '.wav', '.mp3', '.exr')
SOURCE_OF = {'.vjs': ('.js',), '.vxml': ('.xml',), '.vcss': ('.css',), '.vsnd': ('.wav', '.mp3')}


class Plan:
    def __init__(s, vmap, name=None, cs2=None):
        s.cs2 = cs2 or fgdcat.cs2_root()
        s.vmap = os.path.realpath(vmap)                  # through C:\source1\links junctions to the real addon folder
        s.addon = fgdcheck.addon_of(s.vmap)
        if not s.addon: raise ValueError('the map must be in <addon>/maps/')
        s.map = os.path.splitext(os.path.basename(vmap))[0]
        s.name = name or s.map
        s.content = os.path.realpath(os.path.join(s.cs2, 'content', 'csgo_addons', s.addon))
        s.game = os.path.join(s.cs2, 'game', 'csgo_addons', s.addon)
        if not os.path.isdir(s.content) or not s.vmap.lower().startswith(s.content.lower() + os.sep):
            s.content = os.path.dirname(os.path.dirname(s.vmap))
        s.assets = fgdcheck.Assets(s.cs2, None)          # stock only (VPKs and game/csgo loose files)
        s.sources, s.stock, s.missing, s.compiled, s.compiled_missing, s.stale = set(), set(), set(), set(), set(), set()
        s.maps = []
        s.raw_elsewhere = set()

    def rel(s, p): return os.path.relpath(p, s.content).replace('\\', '/')

    def _src(s, rel):
        """addon source file for a reference (a compiled extension maps back to its source), or None"""
        rel = rel.replace('\\', '/').lstrip('/')
        if rel.lower().endswith('_c'): rel = rel[:-2]
        base, ext = os.path.splitext(rel)
        for cand in [rel] + [base + e for e in SOURCE_OF.get(ext.lower(), ())]:
            if os.path.isfile(os.path.join(s.content, cand)): return cand
        return None

    def add_ref(s, rel, queue):
        rel = rel.strip().replace('\\', '/').lstrip('/')
        if not rel or '://' in rel: return
        src = s._src(rel)
        if src:
            if src not in s.sources: s.sources.add(src); queue.append(src)
        elif s.assets.exists(rel[:-2] if rel.endswith('_c') else rel): s.stock.add(rel)
        elif rel.lower().endswith(RAW):
            s.raw_elsewhere.add(rel)       # a source image / mesh not in this addon (compiled into a stock or already built resource)
        else:
            s.missing.add(rel)

    def walk_map(s, path, queue):
        m = V.Map(path)
        s.maps.append(s.rel(path))
        for e in m.entities():
            for a in m.props(e)['attrs']:
                v = a[2].decode('utf-8', 'replace') if isinstance(a[2], (bytes, bytearray)) else str(a[2])
                if v.lower().endswith(fgdcheck.ASSET_EXT + ('.vsndevts',)): s.add_ref(v, queue)
            if m.cls(e).lower() == 'skybox_reference':
                sky = m.P(e, 'targetMapName', '')
                if sky:
                    p = os.path.join(s.content, sky.replace('/', os.sep))
                    if os.path.isfile(p) and s.rel(p) not in s.maps: s.walk_map(p, queue)
        for mat in fgdcheck._mesh_materials(m): s.add_ref(mat, queue)
        refs = m.g(m.root, b'map_asset_references') if hasattr(m, 'root') else None
        for r in refs or []:
            s.add_ref(r.decode('utf-8', 'replace') if isinstance(r, (bytes, bytearray)) else str(r), queue)

    def build(s):
        queue = []
        s.walk_map(s.vmap, queue)
        for extra in ['soundevents/soundevents_addon.vsndevts', 'addoninfo.txt', 'resource/overviews/%s.txt' % s.map]:
            if os.path.isfile(os.path.join(s.content, extra)) and extra not in s.sources: s.sources.add(extra); queue.append(extra)
        for pat in ['materials/overviews/%s_radar*' % s.map, 'panorama/images/map_icons/*%s*' % s.map,
                    'panorama/images/map_icons/screenshots/*/%s*' % s.map, 'panorama/images/map_icons/screenshots/%s*' % s.map]:
            for p in glob.glob(os.path.join(s.content, pat)):
                r = s.rel(p)
                if os.path.isfile(p) and r not in s.sources: s.sources.add(r); queue.append(r)
        while queue:
            rel = queue.pop()
            if not rel.lower().endswith(TEXT_EXT): continue
            try:
                with open(os.path.join(s.content, rel), encoding='utf-8', errors='replace') as f: text = f.read()
            except OSError:
                continue
            for ref in REF.findall(text):
                if ref.lower() != rel.lower(): s.add_ref(ref, queue)
        for rel in sorted(s.sources | set(s.maps)):
            base, ext = os.path.splitext(rel)
            if rel.lower().endswith('.vmap'):
                out = base + '.vpk'
            elif ext.lower() in ('.fbx', '.smd', '.dmx', '.obj', '.txt', '.exr', '.jpg', '.jpeg', '.svg'):
                continue                                     # inputs of other resources, or plain files the game reads as they are
            else:
                out = base + COMPILED.get(ext.lower(), ext) + '_c'
            src_t = os.path.getmtime(os.path.join(s.content, rel))
            p = os.path.join(s.game, out)
            if os.path.isfile(p):
                s.compiled.add(out)
                if os.path.getmtime(p) + 2 < src_t and not rel.lower().endswith('.vmap'): s.stale.add(out)
            elif ext.lower() in ('.png', '.tga', '.psd'):
                continue                                     # images compile inside the material's own vtex: no file of their own
            else:
                s.compiled_missing.add(out)
        for extra in ['resource/overviews/%s.txt' % s.map]:
            if os.path.isfile(os.path.join(s.game, extra)): s.compiled.add(extra)
        return s

    def size(s, root, files):
        return sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))

    def summary(s):
        return {'map': s.map, 'from_addon': s.addon, 'new_addon': s.name, 'maps': sorted(s.maps), 'sources': sorted(s.sources),
                'compiled': sorted(s.compiled), 'compiled_missing': sorted(s.compiled_missing), 'compiled_stale': sorted(s.stale),
                'missing': sorted(s.missing), 'stock_refs': len(s.stock), 'raw_sources_elsewhere': len(s.raw_elsewhere),
                'content_mb': round(s.size(s.content, list(s.sources) + s.maps) / 1e6, 2), 'upload_mb': round(s.size(s.game, s.compiled) / 1e6, 2),
                'publish_md': s.publish_md()}

    def publish_md(s):
        lines = ['# Publishing %s' % s.name, '',
                 'Release addon **%s** made from map `%s` of addon `%s` by tools/release.py. Nothing was uploaded.' % (s.name, s.map, s.addon), '',
                 '- Files: %d sources, %d compiled; upload size about %.1f MB.' % (len(s.sources) + len(s.maps), len(s.compiled), s.size(s.game, s.compiled) / 1e6)]
        if s.compiled_missing or s.stale:
            lines.append('- **Build first**: %d compiled files are missing and %d are older than their sources. Open the new addon in Workshop Tools '
                         'or run `python tools/rcompile.py map <CS2>/content/csgo_addons/%s/maps/%s.vmap --preset final` (under the watchdog).'
                         % (len(s.compiled_missing), len(s.stale), s.name, s.map))
        if s.missing: lines.append('- **Missing**: %d referenced files exist nowhere (listed in the plan); fix or remove them first.' % len(s.missing))
        lines += ['', '## Upload (by hand)', '',
                  '1. Steam -> Counter-Strike 2 -> Launch CS2 Workshop Tools -> choose **%s** -> Launch Tools.' % s.name,
                  '2. Asset Browser -> Tools -> Counter-Strike 2 Workshop Manager -> **New** (or select the item and **Re-Upload** after changes).',
                  '3. Title, description (how to play, the keys), tags (game mode), visibility: Hidden first, then Friends, then Public.',
                  '4. Preview image: the loading picture (16:9, under 1 MB; `create/loading.py workshop` makes one).',
                  '5. Content folder: the release addon **%s**, not `%s`.' % (s.name, s.addon),
                  '6. Submit. The first upload asks you to accept the Steam Workshop agreement.', '',
                  'Write the Steam description in `%s STEAM DESCRIPTION.txt` in the content addon folder.' % s.name]
        return '\n'.join(lines) + '\n'

    def apply(s, root=None, force=False):
        root = root or s.cs2
        dst_c = os.path.join(root, 'content', 'csgo_addons', s.name)
        dst_g = os.path.join(root, 'game', 'csgo_addons', s.name)
        same = lambda a, b: os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
        if same(dst_c, s.content) or same(dst_g, s.game): raise ValueError('the release addon must have a new name')
        for d in (dst_c, dst_g):
            if os.path.exists(d) and os.listdir(d) and not force: raise FileExistsError('%s exists (use --force to add to it)' % d)
        n = 0
        for rel in sorted(s.sources | set(s.maps)):
            os.makedirs(os.path.dirname(os.path.join(dst_c, rel)), exist_ok=True); shutil.copy2(os.path.join(s.content, rel), os.path.join(dst_c, rel)); n += 1
        for rel in sorted(s.compiled):
            os.makedirs(os.path.dirname(os.path.join(dst_g, rel)), exist_ok=True); shutil.copy2(os.path.join(s.game, rel), os.path.join(dst_g, rel)); n += 1
        with open(os.path.join(dst_c, 'PUBLISH.md'), 'w', encoding='utf-8') as f: f.write(s.publish_md())
        return {'content': dst_c, 'game': dst_g, 'files': n}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Plan (and optionally copy) a one-map release addon; never uploads')
    ap.add_argument('vmap'); ap.add_argument('--name'); ap.add_argument('--apply', action='store_true'); ap.add_argument('--root')
    ap.add_argument('--force', action='store_true'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    try:
        p = Plan(a.vmap, a.name).build()
        out = p.summary()
        if a.apply: out['applied'] = p.apply(a.root, a.force)
    except (OSError, ValueError) as ex:
        print('release: %s' % ex, file=sys.stderr); return 2
    if a.json: print(json.dumps(out, indent=1))
    else:
        print(out['publish_md'])
        for k in ('maps', 'sources', 'compiled_missing', 'compiled_stale', 'missing'):
            for x in out[k]: print('%s\t%s' % (k, x))
        if 'applied' in out: print('applied\t%s' % json.dumps(out['applied']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
