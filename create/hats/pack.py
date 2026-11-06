"""The hat collection to hand to a server manager: every kept hat, compiled and as source, with its list and pictures.

usage: python3 -I pack.py <catalog.json> [--prune] [--no-zip]

--prune   deletes the dropped hats (catalog `chosen: false`) from the gmod_hats addon, both halves (content: vmdl/dmx/vmat/png,
          game: compiled), so the addon holds exactly the kept ones. Only folders named after catalog hat ids are touched.
Then writes <work>/dist/gmod_hats_collection_<date>.zip:
    gmod_hats/game/csgo_addons/gmod_hats/      the compiled hats  -> <CS2>/game/csgo_addons/gmod_hats
    gmod_hats/content/csgo_addons/gmod_hats/   the source (vmdl, dmx, vmat, png) -> <CS2>/content/csgo_addons/gmod_hats
    gmod_hats/HATS.md + img/                   the list, a picture of each hat
    gmod_hats/README.txt                       what to do with it (the manager's steps are slime-mg-gm docs/hats.md#adding-hats)
The player models go the same way: their library is the gmod_playermodels addon (create/playermodels, MODELS.md).
"""
import json, os, shutil, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hatpaths

README = """Hat collection: {n} hats for CS2, converted from Garry's Mod Workshop items (cs2mapping create/hats).
Every hat is skinned to CS2's agent skeleton on head_0: the SlimeMG plugin bone-merges it onto any player model.

1. Copy game/csgo_addons/gmod_hats    -> <CS2>/game/csgo_addons/gmod_hats      (compiled: what ship_models.py copies from)
        content/csgo_addons/gmod_hats -> <CS2>/content/csgo_addons/gmod_hats   (source: only needed to rebuild or open them in the tools)
2. Look through HATS.md (a picture of each, its id and the Workshop item it came from). Rights: the authors keep theirs and
   several are from commercial games; get the author's permission before putting one on a public server.
3. To put hats on the server: slime-mg-gm docs/hats.md, "Adding hats" (nominate the ids in server/ship_models.json, run
   tools/ship_models.py, upload, add them to SlimeMG.json Hats).
"""


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    p = hatpaths.paths(cat)
    out = p['out']                                                     # content/csgo_addons/gmod_hats
    game = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(out))), 'game', 'csgo_addons', os.path.basename(out))
    kept = [h['id'] for h in cat['hats'] if h.get('chosen', True)]
    dropped = {h['id'] for h in cat['hats'] if h.get('chosen', True) is False}
    sides = {'content': out, 'game': game}
    if '--prune' in sys.argv:
        n = 0
        for side, root in sides.items():
            for sub in (os.path.join(root, 'models', 'hats'), os.path.join(root, 'materials', 'models', 'hats')):
                if not os.path.isdir(sub): continue
                for d in os.listdir(sub):
                    if d in dropped: shutil.rmtree(os.path.join(sub, d)); n += 1
        print('pruned %d dropped-hat folders' % n)
    missing = [i for i in kept if not os.path.exists(os.path.join(game, 'models', 'hats', i, i + '.vmdl_c'))]
    if missing: sys.exit('not compiled: %s (hat2cs2.py --compile --only ...)' % ','.join(missing))
    if '--no-zip' in sys.argv: return
    dist = os.path.join(p['work'], 'dist'); os.makedirs(dist, exist_ok=True)
    zp = os.path.join(dist, 'gmod_hats_collection_%s.zip' % time.strftime('%Y%m%d'))
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for side, root in sides.items():
            for rel in [r for i in kept for r in (os.path.join('models', 'hats', i), os.path.join('materials', 'models', 'hats', i))]:
                for d, _, fs in os.walk(os.path.join(root, rel)):
                    for f in fs:
                        full = os.path.join(d, f)
                        z.write(full, os.path.join('gmod_hats', side, 'csgo_addons', 'gmod_hats', os.path.relpath(full, root)))
            # shared defaults the materials reference (compiled default textures)
            dflt = os.path.join(root, 'materials', 'default')
            for d, _, fs in os.walk(dflt):
                for f in fs:
                    full = os.path.join(d, f)
                    z.write(full, os.path.join('gmod_hats', side, 'csgo_addons', 'gmod_hats', os.path.relpath(full, root)))
        z.write(os.path.join(HERE, 'HATS.md'), 'gmod_hats/HATS.md')
        for i in kept:
            im = os.path.join(HERE, 'img', i + '.jpg')
            if os.path.exists(im): z.write(im, 'gmod_hats/img/%s.jpg' % i)
        z.writestr('gmod_hats/README.txt', README.format(n=len(kept)))
    print('%s: %d hats, %.1f MB' % (zp, len(kept), os.path.getsize(zp) / 1e6))


if __name__ == '__main__':
    main()
