"""Atlas of CS2's stock props: search the ~12 000 models in pak01 by words, see their real size, keep your own notes on them.

  python propatlas.py search <words> [--limit 30] [--sizes]          models whose path has every word (sizes read their bounds; Node)
  python propatlas.py info <models/...vmdl> [...]                    bounds, size, materials, your note
  python propatlas.py note <models/...vmdl> --category crate --tags wood,small [--front +x] [--mount floor|wall|ceiling] [--text ...]
  python propatlas.py categories                                     how many stock models fall in each category

Categories come from the model path (crates, barrels, vehicles, foliage, rocks, lights, furniture, signs, doors, fences, debris, ...).
Bounds come from visualcheck.ModelBounds (create/s2/bounds_batch.mjs, cached). Notes are a JSON file outside the repo:
env CS2MAP_ATLAS, else %LOCALAPPDATA%\\cs2mapping\\prop_notes.json (stock model paths only; no Valve files are copied anywhere).
Offline renders of a prop: not here (cs2-map-mcp uses Source2Viewer; open the model in Workshop Tools' Asset Browser instead).

From atlas.py / prop_preview / prop_note in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT); fresh code.
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fgdcat

CATEGORIES = [('vehicle', r'vehicle|car_|cars?/|truck|bus_|van_|forklift|boat|helicopter|train_?car|locomotive|wagon'), ('foliage', r'foliage|tree|bush|plant|grass|shrub|flower|palm'),
              ('rock', r'rock|cliff|boulder|stone'), ('light', r'light|lamp|lantern|chandelier|bulb'), ('door', r'door|gate'),
              ('fence', r'fence|railing|barrier|bollard'), ('crate', r'crate|box|pallet|container'), ('barrel', r'barrel|drum|keg|tank'),
              ('furniture', r'chair|table|desk|sofa|couch|bed|shelf|cabinet|bench|stool|furniture'), ('sign', r'sign|poster|billboard'),
              ('debris', r'debris|rubble|trash|junk|garbage|paper|bottle|can_'), ('pipe', r'pipe|cable|wire|vent|duct'),
              ('electrical', r'electric|transformer|generator|fusebox|panel'), ('kitchen', r'kitchen|fridge|stove|sink|oven'),
              ('building', r'wall|window|roof|stair|pillar|column|arch|balcony|awning|building|facade'), ('weapon', r'weapon|ammo|gun')]
_CAT = [(n, re.compile(r'(?<![a-z])(?:%s)' % rx)) for n, rx in CATEGORIES]     # words start after / _ or a digit: 'terrain' is not 'train'


def notes_path():
    return os.environ.get('CS2MAP_ATLAS') or os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'cs2mapping', 'prop_notes.json')


def category(path):
    p = path.lower()
    for name, rx in _CAT:
        if rx.search(p): return name
    return 'other'


class Atlas:
    def __init__(s, cs2=None, models=None, notes=None, bounds=None):
        s.cs2 = cs2 or fgdcat.cs2_root()
        s._models = models
        s.notes_file = notes or notes_path()
        try:
            with open(s.notes_file, encoding='utf-8') as f: s.notes = json.load(f)
        except (OSError, ValueError):
            s.notes = {}
        s.bounds = bounds

    @property
    def models(s):
        if s._models is None:
            import vpk
            v = vpk.VPK(os.path.join(s.cs2, 'game', 'csgo', 'pak01_dir.vpk'))
            skip = re.compile(r'/(weapons|player|characters|chicken|hostage|anims?|ragdoll)/|_gib|_chunk|_break|_piece|lod\d', re.I)
            s._models = sorted(f[:-2] for f in v.files if f.endswith('.vmdl_c') and f.startswith('models/') and not skip.search(f))
        return s._models

    def search(s, words, limit=30, sizes=False):
        ws = [w.lower() for w in (words.split() if isinstance(words, str) else words)]
        hits = [m for m in s.models if all(w in m or w in ' '.join(s.notes.get(m, {}).get('tags', [])) for w in ws)]
        hits.sort(key=lambda m: (m not in s.notes, len(m)))
        out = [{'model': m, 'category': s.notes.get(m, {}).get('category') or category(m), **({'note': s.notes[m]} if m in s.notes else {})}
               for m in hits[:limit]]
        if sizes: s._add_sizes(out)
        return {'matches': len(hits), 'models': out}

    def _add_sizes(s, rows):
        if s.bounds is None:
            import visualcheck
            s.bounds = visualcheck.ModelBounds(s.cs2)
        got = s.bounds.get_many([r['model'] for r in rows])
        if hasattr(s.bounds, 'save'): s.bounds.save()
        for r in rows:
            b = got.get(r['model'])
            if b: r['bounds'] = b; r['size'] = [round(b[1][i] - b[0][i], 1) for i in range(3)]

    def info(s, models):
        rows = [{'model': m, 'category': category(m), 'stock': m in set(s.models), **({'note': s.notes[m]} if m in s.notes else {})} for m in models]
        s._add_sizes(rows)
        return rows

    def note(s, model, category=None, tags=(), front=None, mount=None, text=None):
        n = s.notes.setdefault(model, {})
        for k, v in (('category', category), ('front', front), ('mount', mount), ('text', text)):
            if v: n[k] = v
        if tags: n['tags'] = sorted(set(n.get('tags', [])) | set(tags))
        os.makedirs(os.path.dirname(s.notes_file), exist_ok=True)
        with open(s.notes_file, 'w', encoding='utf-8') as f: json.dump(s.notes, f, indent=1, sort_keys=True)
        return {model: n}

    def categories(s):
        return dict(collections.Counter(category(m) for m in s.models).most_common())


def main(argv=None):
    ap = argparse.ArgumentParser(description='Stock prop atlas')
    ap.add_argument('cmd', choices=['search', 'info', 'note', 'categories']); ap.add_argument('args', nargs='*')
    ap.add_argument('--limit', type=int, default=30); ap.add_argument('--sizes', action='store_true'); ap.add_argument('--category')
    ap.add_argument('--tags', default=''); ap.add_argument('--front'); ap.add_argument('--mount'); ap.add_argument('--text')
    a = ap.parse_args(argv)
    at = Atlas()
    if a.cmd == 'search': out = at.search(a.args, a.limit, a.sizes)
    elif a.cmd == 'info': out = at.info(a.args)
    elif a.cmd == 'note': out = at.note(a.args[0], a.category, [t for t in a.tags.split(',') if t], a.front, a.mount, a.text)
    else: out = at.categories()
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
