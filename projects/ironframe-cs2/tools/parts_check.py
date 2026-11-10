"""Checks data/parts.json (DESIGN.md section 3, SERVER_CONTRACT.md section 5): schema per kind, unique ids and keys, the
upgrade caps (anti-stomp: a fully upgraded loadout stays within caps.ap_pct AP and caps.dps_pct DPS of stock), the starter
loadouts (valid for a starter pilot), the AI loadouts (valid structure and budgets; the boss list may put shoulder weapons
in its arms), and prints the balance tables (weight / EN / DPS per weapon, budgets per frame class). Exit 1 on problems.

  python -I tools/parts_check.py [-q]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_FACTOR = 1.5
KINDS = ['frame', 'arm', 'arm', 'shoulder', 'shoulder', 'generator', 'booster', 'fcs', 'paint']
WTYPES = {'proj', 'lob', 'hitscan', 'melee', 'missile', 'shield', 'ability'}
problems = []


def bad(msg): problems.append(msg)


def dps(w, mult=1.0):
    if not w.get('damage'): return 0.0
    per = w['damage'] * w.get('pellets', 1) * w.get('count', 1) * mult
    period = 1 / w['rate'] if w.get('rate') else w.get('cd', 1)
    if w.get('windup'): period = max(period, w['windup'])
    if w.get('mag') and w.get('reload'): period = (w['mag'] * period + w['reload']) / w['mag']
    if w.get('heat_time'): period *= (w['heat_time'] + w['cool_time']) / w['heat_time']
    return per / period


def main():
    quiet = '-q' in sys.argv
    P = json.load(open(os.path.join(ROOT, 'data', 'parts.json'), encoding='utf-8'))
    for k in ('caps', 'xp', 'classes', 'leg_types', 'move', 'parts', 'starter', 'ai_loadouts'):
        if k not in P: bad('missing top-level key ' + k)
    caps, classes, legs = P['caps'], P['classes'], P['leg_types']
    by_id, keys = {}, set()
    for p in P['parts']:
        pid = p.get('id')
        if not isinstance(pid, int) or not (0 < pid < 1024): bad(f'bad id {pid!r}'); continue
        if pid in by_id: bad(f'duplicate id {pid}')
        if p.get('key') in keys: bad(f'duplicate key {p.get("key")}')
        by_id[pid] = p; keys.add(p.get('key'))
        for f in ('kind', 'key', 'name', 'cost', 'rank'):
            if f not in p: bad(f'{pid}: missing {f}')
        kind = p.get('kind')
        if kind not in set(KINDS): bad(f'{pid}: unknown kind {kind}'); continue
        if kind != 'paint':
            for f in ('weight', 'en', 'upgrade'):
                if f not in p: bad(f'{pid}: missing {f}')
        if kind == 'frame':
            if p.get('class') not in classes: bad(f'{pid}: unknown class {p.get("class")}')
            if p.get('legs') not in legs: bad(f'{pid}: unknown legs {p.get("legs")}')
        elif kind in ('arm', 'shoulder'):
            w = p.get('w') or {}
            if w.get('type') not in WTYPES: bad(f'{pid}: weapon type {w.get("type")}')
            if w.get('type') in ('proj', 'lob', 'hitscan', 'melee', 'missile'):
                for f in ('damage', 'range', 'impact'):
                    if f not in w: bad(f'{pid}: weapon missing {f}')
                if not (w.get('rate') or w.get('cd')): bad(f'{pid}: weapon has neither rate nor cd')
            if w.get('type') in ('proj', 'lob', 'missile') and not w.get('speed'): bad(f'{pid}: projectile without speed')
            if w.get('type') == 'missile' and w.get('lock') not in ('soft', 'hard'): bad(f'{pid}: missile lock soft|hard')
            if w.get('type') == 'shield' and kind != 'arm': bad(f'{pid}: shield must be an arm')
            if p.get('left_only') and kind != 'arm': bad(f'{pid}: left_only on a non-arm')
        elif kind == 'generator':
            if not all(k in p.get('g', {}) for k in ('capacity', 'regen', 'output', 'stall')): bad(f'{pid}: generator fields')
        elif kind == 'booster':
            if not all(k in p.get('b', {}) for k in ('thrust', 'qb_mult', 'qb_cost_mult', 'hover', 'drain_mult')): bad(f'{pid}: booster fields')
        elif kind == 'fcs':
            if not all(k in p.get('f', {}) for k in ('cone', 'range', 'soft', 'hard', 'gimbal')): bad(f'{pid}: fcs fields')
        up = p.get('upgrade')
        if up and kind != 'paint':
            full = up['pct'] * caps['levels']
            if up['stat'] == 'ap' and full > caps['ap_pct']: bad(f'{pid}: AP upgrade {full} % > cap {caps["ap_pct"]} %')
            if up['stat'] == 'damage' and full > caps['dps_pct']: bad(f'{pid}: damage upgrade {full} % > cap {caps["dps_pct"]} %')
            if up['stat'] == 'efficiency' and full > caps['mobility_pct'] * 2: bad(f'{pid}: booster efficiency {full} % beyond 2x the mobility cap')

    def validate(lo, owned=None, boss=False):
        f = lo.split(',')
        if len(f) != 9 or any(not (1 <= len(x) <= 4 and x.isdigit()) for x in f): return 7, 0
        ids = [int(x) for x in f]
        for pos, (pid, kind) in enumerate(zip(ids, KINDS), 1):
            if pid == 0:
                if 2 <= pos <= 5: continue
                return 7, pos
            p = by_id.get(pid)
            if p is None: return 7, pos
            if boss and 2 <= pos <= 5 and p['kind'] in ('arm', 'shoulder') and not (p.get('left_only') and pos == 2): continue
            if p['kind'] != kind or (p.get('left_only') and pos == 2): return 7, pos
        if owned is not None:
            for pid in ids:
                if pid and pid not in owned: return 1, pid
        frame = by_id[ids[0]]
        load = classes[frame['class']]['load'] + by_id[ids[6]].get('b', {}).get('load_bonus', 0)
        if sum(by_id[i].get('weight', 0) for i in ids if i) > load: return 4, 0
        if sum(by_id[i].get('en', 0) for i in ids if i) > by_id[ids[5]]['g']['output'] * EN_FACTOR: return 5, 0
        return 0, 0

    starter = P['starter']
    owned = set(starter['owned'])
    for pid in owned:
        if pid not in by_id: bad(f'starter owns unknown id {pid}')
    for k in ('frame', 'arm', 'shoulder', 'generator', 'booster', 'fcs', 'paint'):
        if not any(by_id.get(i, {}).get('kind') == k for i in owned): bad(f'starter owns no {k}')
    for lo in starter['loadouts']:
        d = validate(lo, owned)
        if d != (0, 0): bad(f'starter loadout {lo} -> deny {d}')
    for tier, lst in P['ai_loadouts'].items():
        for lo in lst:
            d = validate(lo, None, boss=(tier == 'boss'))
            if d != (0, 0): bad(f'ai_loadouts.{tier} {lo} -> deny {d}')
    # anti-stomp: the best upgradable AP and DPS stay inside the caps
    for p in P['parts']:
        if p.get('pve') or p['kind'] == 'paint' or not p.get('upgrade'): continue
        up = p['upgrade']
        if up['stat'] == 'ap' and min(caps['ap_pct'], up['pct'] * caps['levels']) > 15: bad(f'{p["id"]}: AP cap above +15 %')
        if up['stat'] == 'damage' and p.get('w'):
            d0, d5 = dps(p['w']), dps(p['w'], 1 + min(caps['dps_pct'], up['pct'] * caps['levels']) / 100)
            if d0 and d5 / d0 > 1.10 + 1e-9: bad(f'{p["id"]}: upgraded DPS +{(d5 / d0 - 1) * 100:.1f} % > +10 %')
    if not quiet:
        print('weapons: id key type dmg dps weight en range')
        for p in P['parts']:
            if p.get('w') and p['w'].get('damage'):
                w = p['w']
                print(f'  {p["id"]:>3} {p["key"]:<14} {w["type"]:<8} {w["damage"]:>5}{("x" + str(w.get("pellets") or w.get("count"))) if (w.get("pellets") or w.get("count")) else "":<4} '
                      f'{dps(w):>7.0f} {p["weight"]:>5} {p["en"]:>4} {w.get("range", 0):>5}')
        print('classes: load | lightest full kit (rifle, rifle, vm6, decoy, std internals) weight')
        kit = sum(by_id[i]['weight'] for i in (101, 101, 201, 209, 301, 401, 501))
        for k, c in classes.items(): print(f'  {k:<7} AP {c["ap"]:>6} load {c["load"]:>6}  kit {kit} -> {"ok" if kit <= c["load"] else "OVER"}')
    for msg in problems: print('PROBLEM ' + msg)
    print(f'parts_check: {len(P["parts"])} parts, {sum(len(v) for v in P["ai_loadouts"].values())} ai loadouts, {len(starter["loadouts"])} starter loadouts: '
          + ('ok' if not problems else f'{len(problems)} problem(s)'))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
