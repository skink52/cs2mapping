"""Hat candidate finder: GMod Workshop (app 4000) items that look like hat / accessory packs (Pointshop hats, PAC3 accessories,
hat model packs), from the Workshop browse pages (the item list they embed as JSON; same reader as playermodels/browse.py).

usage: python3 -I browse.py <catalog.json> [--out candidates.json] [--pages N]

Searches "hat", "hats", "pointshop hats", "pointshop accessories", "pac3 hats", "accessories", "cosmetics", "masks", "glasses"
(top rated all time, most subscribed) and prints the items not in the catalog yet whose title looks like a hat/accessory item,
most subscribed first. Writes them all to --out (default <work>/logs/candidates.json). Downloads nothing.
"""
import json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'playermodels'))
import hatpaths
from browse import page_items                     # playermodels/browse.py: the embedded-JSON reader

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
URL = ('https://steamcommunity.com/workshop/browse/?appid=4000&browsesort={sort}&section=readytouseitems&p={p}&num_per_page=30'
       '&days=-1&searchtext={q}')
WORDS = ['hat', 'hats', 'pointshop hats', 'pointshop accessories', 'pointshop', 'pac3 hats', 'accessories', 'cosmetics',
         'masks', 'glasses', 'helmet pack', 'tf2 hats']
LOOKS = re.compile(r'(?i)hat|cap\b|helmet|mask|glasses|sunglass|accessor|cosmetic|pointshop|crown|halo|horn|beanie|headphone|ears|pac3|wearable|costume')


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    have = {it['id'] for it in cat['items']}
    pages = int(sys.argv[sys.argv.index('--pages') + 1]) if '--pages' in sys.argv else 3
    out_path = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(hatpaths.paths(cat)['work'], 'logs', 'candidates.json')
    found = {}
    for w in WORDS:
        for sort in ('toprated', 'totaluniquesubscribers'):
            for p in range(1, pages + 1):
                req = urllib.request.Request(URL.format(sort=sort, p=p, q=w.replace(' ', '+')), headers={'User-Agent': 'Mozilla/5.0'})
                try: text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
                except OSError as x: print('  %s %s p%d: %s' % (sort, w, p, x)); continue
                n = 0
                for it in page_items(text):
                    n += 1
                    it.setdefault('found_by', []).append('%s:%s' % (sort, w))
                    if it['id'] in found: found[it['id']]['found_by'] += it['found_by']
                    else: found[it['id']] = it
                time.sleep(0.6)
                if n < 30: break
    items = sorted(found.values(), key=lambda x: -x['subscribers'])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(items, open(out_path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for it in items:
        if it['id'] in have or not LOOKS.search(it['title']): continue
        print('%-11d %7.1f MB %8d  %s  [%s]' % (it['id'], it['mb'], it['subscribers'], it['title'], it['author']))
    print('%d items, written to %s' % (len(items), out_path))


if __name__ == '__main__':
    main()
