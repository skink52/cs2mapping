"""Candidate finder: GMod Workshop (app 4000) items tagged Model that aren't in the catalog yet, from the Workshop browse pages.

usage: python3 -I browse.py <catalog.json> [--out candidates.json] [--all]

Reads the browse pages the way a browser gets them (top rated over 7/30/90/365 days, then "playermodel" searches: top rated,
trending, most subscribed) and keeps the item list each page embeds as JSON (id, title, author, size, subscribers). Prints the
items whose title looks like a player model (PM, playermodel, ragdoll; --all prints every item), newest list first, and writes
them all to --out (default <work>/logs/candidates.json). Then: add the picks to catalog.json (chosen false, looked_at <batch>) and
run `fetch.py --scan --suggest --only <ids>`. Nothing is downloaded here. About 1 s per page, 41 pages.
"""
import json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch

if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Workshop titles: any script
BS = chr(92)
URL = ('https://steamcommunity.com/workshop/browse/?appid=4000&browsesort={sort}&section=readytouseitems&p={p}&num_per_page=30'
       '&days={days}&searchtext={q}&requiredtags%5B%5D=Model')
QUERIES = [('toprated', d, '', n) for d, n in ((7, 3), (30, 5), (90, 5), (365, 4))] + \
          [('toprated', 365, 'playermodel', 8), ('toprated', 90, 'playermodel', 5), ('trend', 30, 'playermodel', 5),
           ('totaluniquesubscribers', -1, 'playermodel', 6)]
LOOKS_PM = re.compile(r'(?i)\bpm\b|player\s*model|playermodel|ragdoll')


def unesc(s):
    """a value from the page's embedded JSON (a JS string literal holding JSON: one extra level of escaping)"""
    s = s.replace(BS + BS, BS)
    try: return ' '.join(json.loads('"' + s + '"').split())
    except ValueError: return ' '.join(s.split())


def page_items(text):
    text = text.replace(BS + '"', '"')
    names = dict(re.findall(r'"steamid":"(\d+)".{0,300}?"persona_name":"(.*?)"', text, re.S))
    for blk in text.split('{"publishedfileid":"')[1:]:
        def g(k, d=''):
            m = re.search(r'"%s":"?(.*?)"?[,}]' % k, blk, re.S)
            return m[1] if m else d
        creator = g('creator')
        yield {'id': int(blk[:blk.index('"')]), 'title': unesc(g('title')), 'author': unesc(names.get(creator, creator)),
               'mb': round(int(g('file_size', '0') or 0) / 1e6, 1), 'subscribers': int(g('subscriptions', '0') or 0),
               'description': unesc(g('short_description'))[:200]}


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    have = {it['id'] for it in cat['items']}
    out_path = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(fetch.paths(cat)['work'], 'logs', 'candidates.json')
    found = {}
    for sort, days, q, pages in QUERIES:
        for p in range(1, pages + 1):
            req = urllib.request.Request(URL.format(sort=sort, p=p, days=days, q=q), headers={'User-Agent': 'Mozilla/5.0'})
            try: text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
            except OSError as x: print('  %s %s p%d: %s' % (sort, q or days, p, x)); continue
            for it in page_items(text):
                if it['id'] not in have: found.setdefault(it['id'], it)
            time.sleep(0.5)
        print('  %-24s %-12s %d new so far' % (sort, q or '%d days' % days, len(found)), flush=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(list(found.values()), open(out_path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    shown = [it for it in found.values() if '--all' in sys.argv or LOOKS_PM.search(it['title'])]
    for it in shown:
        print('%11d %7.1f MB %8d subs  %s  (%s)' % (it['id'], it['mb'], it['subscribers'], it['title'][:80], it['author'][:24]))
    print('%d new items, %d look like player models; all in %s' % (len(found), len(shown), out_path))


if __name__ == '__main__':
    main()
