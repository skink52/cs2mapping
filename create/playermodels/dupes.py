"""Duplicate characters: the same character from two Workshop items (or two models of one) is kept once, the better one winning.

usage: python3 -I dupes.py <catalog.json> [--fix]      (run after each batch, before listmodels.py)

Groups the chosen models by character (their name with the packaging words removed: "PM", "playermodel", "NPC", "ragdoll", "HD",
"remastered", brackets...; one name's words all inside the other's counts too). In each group the score decides:
    quality  min(vertices, 40k) / 40k, minus 0.5 if a material came out flat grey (missing texture)
    ratings  log10(1 + lifetime subscribers) / 6 + log10(1 + lifetime favourites) / 8   (Steam's public Workshop details)
Prints the groups (best first) and writes each member's `possible_dupes` in the catalog: the other models of its group, so
MODELS.md and the server's catalog flag them in their warnings (skink52, 6 Nov: duplicates are kept and pointed at, not removed).
--fix (not used now) would instead un-choose all but the best. A model marked "distinct": true in the catalog (another outfit or unit, not a repeat) is never grouped. Exact skins of one character (colour variants in a pack) are not duplicates: only different items, or models
with the same name, are compared.
"""
import json, math, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fetch

DROP = set('pm pms playermodel playermodels player model models npc npcs ragdoll ragdolls hd hq v1 v2 v3 remaster remastered enhanced '
           'improved custom the and with c_hands hands arms pack edition version new old updated fixed working'.split())


def char_key(name):
    s = re.sub(r'\[[^\]]*\]|\{[^}]*\}', ' ', name.lower())
    s = re.sub(r'\(([^)]*)\)', r' \1 ', s)
    words = [w for w in re.findall(r'[a-z0-9]+', s) if w not in DROP and not w.isdigit()]
    return tuple(words)


def same(a, b):
    if not a or not b: return False
    sa, sb = set(a), set(b)
    if sa == sb: return True
    small, big = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return len(small) >= 2 and small <= big           # "agent smith" inside "agent smith path neo"


def workshop_stats(ids):
    """{id: (lifetime subscribers, lifetime favourites)} from ISteamRemoteStorage/GetPublishedFileDetails (no key)"""
    out = {}
    ids = sorted(set(x for x in ids if int(x) > 0))          # 0: not a Workshop item (an FBX import)
    for k in range(0, len(ids), 100):
        chunk = ids[k:k + 100]
        data = {'itemcount': len(chunk)}
        for i, x in enumerate(chunk): data['publishedfileids[%d]' % i] = x
        req = urllib.request.Request('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/',
                                     data=urllib.parse.urlencode(data).encode(), headers={'User-Agent': 'Mozilla/5.0'})
        try: res = json.load(urllib.request.urlopen(req, timeout=30))
        except OSError as x: print('  stats:', x); continue
        for d in res.get('response', {}).get('publishedfiledetails', []):
            out[int(d['publishedfileid'])] = (int(d.get('lifetime_subscriptions', d.get('subscriptions', 0)) or 0),
                                             int(d.get('lifetime_favorited', d.get('favorited', 0)) or 0))
    return out


def score(verts, flat, stats):
    subs, fav = stats
    return min(verts, 40000) / 40000 - (0.5 if flat else 0) + math.log10(1 + subs) / 6 + math.log10(1 + fav) / 8


def groups(entries):
    """entries: [{'key', 'id', ...}] -> lists of entries that are the same character from different items (or the same name)"""
    gs = []
    for e in entries:
        for g in gs:
            if any(same(e['key'], o['key']) and (e['id'] != o['id'] or e['key'] == o['key']) for o in g): g.append(e); break
        else: gs.append([e])
    return [g for g in gs if len(g) > 1]


def main():
    cat_path = sys.argv[1]
    cat = json.load(open(cat_path, encoding='utf-8'))
    p = fetch.paths(cat)
    entries = []
    for it in cat['items']:
        if not it.get('chosen') or it.get('distinct'): continue     # "distinct": true = a different look, never a duplicate
        rp = os.path.join(p['work'], 'reports', it['slug'] + '.json')
        r = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
        entries.append({'slug': it['slug'], 'id': it['id'], 'key': char_key(it.get('name') or it['slug']), 'item': it,
                        'verts': r.get('vertices', 0), 'flat': any(m.get('flat') for m in r.get('materials', []))})
    for it in cat['items']: it.pop('possible_dupes', None)
    gs = groups(entries)
    stats = workshop_stats([e['id'] for g in gs for e in g])
    for g in gs:
        for e in g: e['score'] = round(score(e['verts'], e['flat'], stats.get(e['id'], (0, 0))), 3)
        g.sort(key=lambda e: -e['score'])
        print('%s: keep %s (%.2f); %s' % (' '.join(g[0]['key']), g[0]['slug'], g[0]['score'], ', '.join('%s %.2f' % (e['slug'], e['score']) for e in g[1:])))
        for e in g:
            e['item']['possible_dupes'] = [o['slug'] for o in g if o is not e]
        if '--fix' in sys.argv:
            for e in g[1:]:
                it = e['item']; it['chosen'] = False; it['dropped_after'] = it.pop('batch', None)
                it['skip_reason'] = 'duplicate of %s (lower quality + ratings: %.2f vs %.2f)' % (g[0]['slug'], e['score'], g[0]['score'])
    if True:
        open(cat_path, 'w', encoding='utf-8', newline='\n').write(json.dumps(cat, indent=1, ensure_ascii=False) + '\n')
    print('%d duplicate groups' % len(gs))


if __name__ == '__main__':
    main()
