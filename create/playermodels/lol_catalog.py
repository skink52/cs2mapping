"""Add League of Legends champion GLBs (from lol_export.py) to catalog.json, one item per <dir>/<champion>.glb not yet in it.

    python lol_catalog.py <catalog.json> <glb dir> [--batch 12]

Item: slug lol_<champion>, "fbx" = the GLB, "id": 0, "url" = the model viewer page, name = the champion's name, "fold_bones" for
champions with known tails/wings (FOLD below; extend it after a review). Then: pipeline.py catalog.json --batch=12 --compile --jobs N.
"""
import json, os, re, sys

NAMES = ("Aatrox Ahri Akali Akshan Alistar Ambessa Amumu Anivia Annie Aphelios Ashe|Aurelion Sol|Aurora Azir Bard|Bel'Veth|Blitzcrank Brand "
         "Braum Briar Caitlyn Camille Cassiopeia|Cho'Gath|Corki Darius Diana|Dr. Mundo|Draven Ekko Elise Evelynn Ezreal Fiddlesticks Fiora "
         "Fizz Galio Gangplank Garen Gnar Gragas Graves Gwen Hecarim Heimerdinger Hwei Illaoi Irelia Ivern Janna|Jarvan IV|Jax Jayce Jhin "
         "Jinx|K'Sante|Kai'Sa|Kalista Karma Karthus Kassadin Katarina Kayle Kayn Kennen|Kha'Zix|Kindred Kled|Kog'Maw|LeBlanc|Lee Sin|Leona "
         "Lillia Lissandra Locke Lucian Lulu Lux Malphite Malzahar Maokai|Master Yi|Mel Milio|Miss Fortune|Mordekaiser Morgana Naafiri Nami "
         "Nasus Nautilus Neeko Nidalee Nilah Nocturne|Nunu & Willump|Olaf Orianna Ornn Pantheon Poppy Pyke Qiyana Quinn Rakan Rammus|Rek'Sai|"
         "Rell|Renata Glasc|Renekton Rengar Riven Rumble Ryze Samira Sejuani Senna Seraphine Sett Shaco Shen Shyvana Singed Sion Sivir Skarner "
         "Smolder Sona Soraka Swain Sylas Syndra|Tahm Kench|Taliyah Talon Taric Teemo Thresh Tristana Trundle Tryndamere|Twisted Fate|Twitch "
         "Udyr Urgot Varus Vayne Veigar|Vel'Koz|Vex Vi Viego Viktor Vladimir Volibear Warwick Wukong Xayah Xerath|Xin Zhao|Yasuo Yone Yorick "
         "Yunara Yuumi Zaahen Zac Zed Zeri Ziggs Zilean Zoe Zyra")
FOLD = {'ahri': '.*Tail.*'}


def names():
    out = {}
    for chunk in NAMES.split('|'):
        parts = [chunk] if ' ' in chunk.strip() and chunk == chunk.strip() and chunk in ('Aurelion Sol', 'Dr. Mundo', 'Jarvan IV', 'Lee Sin',
                 'Master Yi', 'Miss Fortune', 'Nunu & Willump', 'Renata Glasc', 'Tahm Kench', 'Twisted Fate', 'Xin Zhao') else chunk.split()
        for n in parts: out[re.sub(r'[^a-z0-9]', '', n.lower())] = n
    return out


def main():
    cat_path, d = sys.argv[1], sys.argv[2]
    batch = int(sys.argv[sys.argv.index('--batch') + 1]) if '--batch' in sys.argv else 12
    cat = json.load(open(cat_path, encoding='utf-8'))
    have = {i.get('slug') for i in cat['items']}
    nm = names()
    log = {}
    lp = os.path.join(d, 'export_log.json')
    if os.path.exists(lp): log = json.load(open(lp, encoding='utf-8'))
    added = []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.glb'): continue
        k = f[:-4]; slug = 'lol_' + k
        if slug in have: continue
        m = re.search(r'\((/model-viewer\?id=\d+)\)', log.get(k, ''))
        it = {'id': 0, 'title': 'League of Legends - %s' % nm.get(k, k), 'author': 'Riot Games (export: modelviewer.lol)', 'chosen': True,
              'batch': batch, 'slug': slug, 'mdl': slug + '.npz', 'name': nm.get(k, k.title()), 'fbx': os.path.join(d, f).replace('\\', '/'),
              'url': 'https://modelviewer.lol' + (m.group(1) if m else '/champions/' + k), 'note': 'League of Legends model: private testing only'}
        if k in FOLD: it['fold_bones'] = FOLD[k]
        it['drop_orphans'] = True
        cat['items'].append(it); added.append(slug)
    open(cat_path, 'w', encoding='utf-8', newline='\n').write(json.dumps(cat, indent=1, ensure_ascii=False) + '\n')
    print('added %d: %s' % (len(added), ', '.join(added)))


if __name__ == '__main__':
    main()
