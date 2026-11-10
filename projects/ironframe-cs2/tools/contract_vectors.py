"""Writes data/contract_vectors.json: the shared test vectors for SERVER_CONTRACT.md section 5 (loadout validation), the XP/rank
maths (DESIGN.md section 7) and the pilot payload (section 4). Both sides run them: the core's test/contract.cjs and the plugin's
`slime_ifr_test vectors` (slime-mg-gm tests/run.py --only ironframe). Regenerate after a parts.json change:

  python3 tools/contract_vectors.py          # writes data/contract_vectors.json (and prints a summary)

Rules (the single statement of them; the C# in slime-mg-gm plugins/SlimeMG/IronFrame/Loadout.cs says the same):
  validate(loadout, pilot) -> (deny, ref)
    7 ref 0   not exactly nine comma-separated fields, or a field that isn't 1-4 decimal digits
    7 ref p   position p (1-9) is 0 where 0 isn't allowed (only the four weapon slots 2-5 may be 0), or the id doesn't exist,
              or its kind isn't the slot's kind (frame, arm, arm, shoulder, shoulder, generator, booster, fcs, paint),
              or a left_only arm (the shield, 111) is in the right arm (position 2)
    1 ref id  (server mode) a non-zero id the pilot doesn't own, lowest position first. Rank is NOT checked here: it gates
              buy/upg (deny 2) only (DESIGN 7 "a part needs rank R and credits"; SERVER_CONTRACT 5 lists ownership, kinds,
              the shield and weight), so a starter or gifted part above the pilot's rank is usable (starter.owned has the
              rank-2 decoy, 209).
    4 ref 0   sum of weight of every non-zero part > classes[frame.class].load + booster.b.load_bonus (0 if none)
    5 ref 0   sum of en of every non-zero part > generator.g.output * en_factor (1.5)
    0         valid
  xpFor(rank) = sum for n = 1 .. rank-1 of floor(rank_base + rank_mult * n ** rank_pow)   (xpFor(1) = 0)
  rankFor(xp) = the largest rank in 1..max_rank with xpFor(rank) <= xp
  owned hex   = hex digits (lower case, no 0x, no leading zeros) of the integer sum(2 ** id for id in owned)

Customisation and server -> map information (SERVER_CONTRACT.md sections 8-10; data/career.json; the C# is IronFrame/Career.cs, the
map side src/core/70_progress.js IF_Career):
  clean(text, max)   a-z to upper case (ASCII only), '_' -> ' ', characters outside career.alphabet dropped, runs of spaces to one, trimmed, cut to max, trimmed
  wire(text)         ' ' -> '_' (payload strings carry no spaces)
  pairs(text, n)     n ints: code(c[2i]) + 40 * code(c[2i+1]); code = alphabet index + 1, 0 past the end
  profile (kind 3)   q1.<callsign>.<title>.<badge>.<earned hex>.<prefs>.<fav>.<place>.<accents: 6 hex digits>.<L4>.<L5>.<L6>.<6 names , joined>.<daily>
                     daily = code-progress-goal-reward joined by ',' or 0; earned hex = hex of sum(2 ** honour id)
                     ints [2, title, badge, earned & 8191, earned >> 13, prefs, fav, place, acc1 | acc2 << 4 | acc3 << 8, acc4.., callsign pairs x 6,
                           n daily, (code, progress, goal, reward) x n, mask of L4-L6 present, 9 ids each, mask of names present (6 bits), 5 pairs each]
  rules (kind 4)     r1.<rotation: mode keys , joined or 0>.<round seconds>.<ai min x 10>.<ai max x 10>.<xp percent>.<flags>
                     ints [1, rot lo, rot hi, round seconds, ai min x 10, ai max x 10, xp percent, flags]; rot: 3 bits a mode code, 4 per int
  board (kind 5)     t1.<total pilots>.<NAME>,<rank>,<xp> per row; ints [1, rows, total, (name pairs x 6, rank, xp & 8191, xp >> 13) per row]
  honours            earned = every honour whose career stat >= goal
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARTS = json.load(open(os.path.join(ROOT, 'data', 'parts.json'), encoding='utf-8'))
EN_FACTOR = 1.5
KINDS = ['frame', 'arm', 'arm', 'shoulder', 'shoulder', 'generator', 'booster', 'fcs', 'paint']
BY_ID = {p['id']: p for p in PARTS['parts']}


def validate(loadout, pilot):
    fields = loadout.split(',')
    if len(fields) != 9 or any(not (1 <= len(f) <= 4 and f.isdigit() and f.isascii()) for f in fields): return 7, 0
    ids = [int(f) for f in fields]
    for pos, (pid, kind) in enumerate(zip(ids, KINDS), 1):
        if pid == 0:
            if 2 <= pos <= 5: continue
            return 7, pos
        p = BY_ID.get(pid)
        if p is None or p['kind'] != kind: return 7, pos
        if p.get('left_only') and pos == 2: return 7, pos
    if pilot is not None:
        for pid in ids:
            if pid and pid not in pilot['owned']: return 1, pid
    frame = BY_ID[ids[0]]
    load = PARTS['classes'][frame['class']]['load'] + BY_ID[ids[6]].get('b', {}).get('load_bonus', 0)
    if sum(BY_ID[i].get('weight', 0) for i in ids if i) > load: return 4, 0
    if sum(BY_ID[i].get('en', 0) for i in ids if i) > BY_ID[ids[5]]['g']['output'] * EN_FACTOR: return 5, 0
    return 0, 0


X = PARTS['xp']
def step(n): return math.floor(X['rank_base'] + X['rank_mult'] * n ** X['rank_pow'])
def xp_for(rank): return sum(step(n) for n in range(1, rank))
def rank_for(xp):
    r = 1
    while r < X['max_rank'] and xp_for(r + 1) <= xp: r += 1
    return r


def owned_hex(ids): return format(sum(1 << i for i in set(ids)), 'x')


def payload(p):
    ups = ','.join(f'{i}-{l}' for i, l in sorted(p['upgrades'].items()) if l > 0) or '0'
    return '.'.join(['p1', str(p['rank']), str(p['xp']), str(p['credits']), str(p['active']), owned_hex(p['owned']), ups, *p['loadouts'], str(p['flags'])])


def pages(kind, values, entities=4):
    """Origin fallback (SERVER_CONTRACT section 4): ints 0..8191, 3 per entity; entity 0 of each page = (page, pages, kind)."""
    per = (entities - 1) * 3
    chunks = [values[i:i + per] for i in range(0, max(1, len(values)), per)] or [[]]
    out = []
    for i, ch in enumerate(chunks):
        ch = ch + [0] * (per - len(ch))
        out.append([i, len(chunks), kind] + ch)
    return out


def pilot_ints(p):
    ups = sorted((i, l) for i, l in p['upgrades'].items() if l > 0)
    v = [p['rank'], p['active'], p['flags'], p['xp'] & 8191, (p['xp'] >> 13) & 8191, p['credits'] & 8191, (p['credits'] >> 13) & 8191, len(ups)]
    for i, l in ups: v += [i, l]
    for lo in p['loadouts']:
        ids = [int(x) for x in lo.split(',')] if lo != '0' else [0] * 9
        v += ids
    return [min(8191, max(0, x)) for x in v]


# ---------------------------------------------------------------- customisation, rules, leaderboard (data/career.json)
CAREER = json.load(open(os.path.join(ROOT, 'data', 'career.json'), encoding='utf-8'))
ALPHA = CAREER['alphabet']
MODES = CAREER['modes']
KIND_PROFILE, KIND_RULES, KIND_BOARD = 3, 4, 5


def clip(v): return [min(8191, max(0, int(x))) for x in v]
def clean(text, n):
    t = ''.join(chr(ord(c) - 32) if 'a' <= c <= 'z' else c for c in str(text))      # ASCII letters only: no locale rules
    t = ''.join(c for c in t.replace('_', ' ') if c in ALPHA)
    t = ' '.join(x for x in t.split(' ') if x)
    return t[:n].strip()
def wire(text): return text.replace(' ', '_')
def pairs(text, n):
    c = [ALPHA.index(ch) + 1 for ch in text] + [0] * (2 * n)
    return [c[2 * i] + 40 * c[2 * i + 1] for i in range(n)]
def bits(ids): return sum(1 << i for i in set(ids))


def profile_str(p):
    daily = ','.join('%d-%d-%d-%d' % (d['code'], d['progress'], d['goal'], d['reward']) for d in p['daily']) or '0'
    return '.'.join(['q1', wire(p['callsign']), str(p['title']), str(p['badge']), format(bits(p['earned']), 'x'), str(p['prefs']), str(p['fav']), str(p['place']),
                     ''.join(format(a, 'x') for a in p['accents']), *p['loadouts'], ','.join(wire(n) for n in p['names']), daily])


def profile_ints(p):
    e, a = bits(p['earned']), p['accents']
    v = [2, p['title'], p['badge'], e & 8191, (e >> 13) & 8191, p['prefs'], p['fav'], p['place'], a[0] | a[1] << 4 | a[2] << 8, a[3] | a[4] << 4 | a[5] << 8]
    v += pairs(p['callsign'], 6)
    v.append(len(p['daily']))
    for d in p['daily']: v += [d['code'], d['progress'], d['goal'], d['reward']]
    v.append(sum(1 << k for k, lo in enumerate(p['loadouts']) if lo != '0'))
    for lo in p['loadouts']:
        if lo != '0': v += [int(x) for x in lo.split(',')]
    v.append(sum(1 << k for k, n in enumerate(p['names']) if n))
    for n in p['names']:
        if n: v += pairs(n, 5)
    return clip(v)


def rules_str(r):
    return '.'.join(['r1', ','.join(r['rotation']) or '0', str(r['round_s']), str(round(r['ai_min'] * 10)), str(round(r['ai_max'] * 10)), str(r['xp_pct']), str(r['flags'])])
def rules_ints(r):
    c = [MODES.index(m) + 1 for m in r['rotation']][:8] + [0] * 8
    rot = [c[0] | c[1] << 3 | c[2] << 6 | c[3] << 9, c[4] | c[5] << 3 | c[6] << 6 | c[7] << 9]
    return clip([1] + rot + [r['round_s'], round(r['ai_min'] * 10), round(r['ai_max'] * 10), r['xp_pct'], r['flags']])


def board_str(b): return '.'.join(['t1', str(b['total'])] + ['%s,%d,%d' % (wire(r['name']), r['rank'], r['xp']) for r in b['rows']])
def board_ints(b):
    v = [1, len(b['rows']), b['total']]
    for r in b['rows']: v += pairs(r['name'], 6) + [r['rank'], r['xp'] & 8191, (r['xp'] >> 13) & 8191]
    return clip(v)


def earned(stats): return [h['id'] for h in CAREER['honours'] if stats.get(h['stat'], 0) >= h['goal']]


def career_vectors():
    L1 = PARTS['starter']['loadouts'][0]
    p_new = {'callsign': '', 'title': 0, 'badge': 0, 'earned': [], 'prefs': 0, 'fav': 0, 'place': 0, 'accents': [0] * 6, 'loadouts': ['0', '0', '0'],
             'names': [''] * 6, 'daily': []}
    p_typ = {'callsign': 'RAVEN 7', 'title': 5, 'badge': 13, 'earned': [1, 2, 5, 13, 14], 'prefs': 3 | 8, 'fav': 4, 'place': 12, 'accents': [6, 0, 12, 0, 0, 0],
             'loadouts': ['0', '0', '0'], 'names': ['DUELIST', '', '', '', '', ''],
             'daily': [{'code': 1, 'progress': 1, 'goal': 2, 'reward': 600}, {'code': 2, 'progress': 7, 'goal': 15, 'reward': 800}, {'code': 3, 'progress': 300, 'goal': 300, 'reward': 900}]}
    p_max = {'callsign': 'ZZ-TOP 99 ZZ', 'title': 12, 'badge': 20, 'earned': list(range(1, 25)), 'prefs': 4 | 8, 'fav': 24, 'place': 8191, 'accents': [1, 2, 3, 10, 11, 12],
             'loadouts': [L1, '8,105,105,204,203,303,403,502,601', '14,110,107,210,207,304,404,504,612'],
             'names': ['ALPHA', 'BIG GUN', 'SNIPER-2', 'CQC', 'FLAG RUN', 'ABCDEFGHIJ'],
             'daily': [{'code': 8, 'progress': 5, 'goal': 5, 'reward': 1200}, {'code': 0, 'progress': 8000, 'goal': 8191, 'reward': 8191}, {'code': 9, 'progress': 0, 'goal': 1, 'reward': 500}]}
    profiles = []
    for name, p in (('new pilot: nothing set', p_new), ('typical: callsign, title, badge, one named loadout, three contracts', p_typ),
                    ('everything: six loadouts, six names, every honour, the largest values', p_max)):
        iv = profile_ints(p)
        profiles.append({'name': name, 'profile': p, 'payload': profile_str(p), 'values': iv, 'entities': 4, 'pages': pages(KIND_PROFILE, iv)})
    r_def = {'rotation': [], 'round_s': 0, 'ai_min': 0.0, 'ai_max': 2.0, 'xp_pct': 100, 'flags': 0}
    r_evt = {'rotation': ['cq', 'ctf', 'kh', 'tb'], 'round_s': 480, 'ai_min': 0.5, 'ai_max': 1.5, 'xp_pct': 200, 'flags': 1}
    r_all = {'rotation': ['tb', 'cq', 'kh', 'ctf', 'sk', 'so', 'tb', 'so'], 'round_s': 3600, 'ai_min': 2.0, 'ai_max': 2.0, 'xp_pct': 1000, 'flags': 3}
    rules = [{'name': n, 'rules': r, 'payload': rules_str(r), 'values': rules_ints(r), 'entities': 4, 'pages': pages(KIND_RULES, rules_ints(r))}
             for n, r in (('map defaults', r_def), ('double XP event, four modes, 8 minute rounds', r_evt), ('eight rotation entries, the limits', r_all))]
    b0 = {'total': 0, 'rows': []}
    b5 = {'total': 1234, 'rows': [{'name': 'RAVEN 7', 'rank': 50, 'xp': 1270507}, {'name': 'SKINK52', 'rank': 41, 'xp': 800123}, {'name': 'ZZ-TOP 99 ZZ', 'rank': 20, 'xp': 132236},
                                  {'name': 'A', 'rank': 2, 'xp': 780}, {'name': 'PILOT', 'rank': 1, 'xp': 0}]}
    boards = [{'name': n, 'board': b, 'payload': board_str(b), 'values': board_ints(b), 'entities': 4, 'pages': pages(KIND_BOARD, board_ints(b))}
              for n, b in (('nobody yet', b0), ('five pilots', b5))]
    texts = [{'in': t, 'max': n, 'out': clean(t, n)} for t, n in (
        ('Raven 7', 12), ('  the   quick_brown fox  ', 12), ('xX_$n1per_Xx', 12), ('\u00e9t\u00e9-42!', 12), ('', 12), ('___', 12), ('abcdefghijklmnop', 10), ('abcdefghi jk', 10),
        ('a.b;c"d', 10), ('-', 12), ('ALREADY OK', 10))]
    top = {}
    for h in CAREER['honours']: top[h['stat']] = max(top.get(h['stat'], 0), h['goal'])
    hon = [{'name': n, 'stats': s, 'earned': earned(s)} for n, s in (
        ('no rounds', {}),
        ('one round', {'mech_rounds': 1}),
        ('a regular who wins', {'mech_rounds': 30, 'mech_wins': 12, 'mech_damage': 999, 'best_round_kills': 10, 'best_streak': 7}),
        ('everything', top))]
    return {'career_version': CAREER['version'], 'kinds': {'pilot': 1, 'deny': 2, 'profile': KIND_PROFILE, 'rules': KIND_RULES, 'board': KIND_BOARD},
            'profiles': profiles, 'server_rules': rules, 'boards': boards, 'texts': texts, 'honours': hon}


def main():
    starter = PARTS['starter']
    all_owned = sorted(p['id'] for p in PARTS['parts'] if not p.get('pve'))
    pilots = {
        'starter': {'rank': 1, 'owned': sorted(starter['owned'])},
        'starter_gifted': {'rank': 1, 'owned': sorted(starter['owned'] + [102])},           # owns a rank-2 part (an admin gift)
        'veteran': {'rank': 20, 'owned': sorted(i for i in all_owned if BY_ID[i]['rank'] <= 20)},
        'ace': {'rank': 50, 'owned': all_owned},
    }
    L1, L2, L3 = starter['loadouts']
    cases = [
        ('starter loadout 1', 'starter', L1),
        ('starter loadout 2: 402/503 are not in starter.owned (catalog inconsistency, see notes)', 'starter', L2),
        ('starter loadout 3: 105/208/303/403 not owned', 'starter', L3),
        ('eight fields', 'starter', '4,101,103,201,209,301,401,501'),
        ('ten fields', 'starter', L1 + ',1'),
        ('a word', 'starter', '4,101,103,201,209,301,401,501,abc'),
        ('a negative id', 'starter', '-1,101,103,201,209,301,401,501,601'),
        ('a space', 'starter', '4, 101,103,201,209,301,401,501,601'),
        ('trailing comma', 'starter', L1 + ','),
        ('five digits', 'starter', '4,10100,103,201,209,301,401,501,601'),
        ('frame 0', 'starter', '0,101,103,201,209,301,401,501,601'),
        ('every weapon slot empty', 'starter', '4,0,0,0,0,301,401,501,601'),
        ('generator 0', 'starter', '4,101,103,201,209,0,401,501,601'),
        ('booster 0', 'starter', '4,101,103,201,209,301,0,501,601'),
        ('fcs 0', 'starter', '4,101,103,201,209,301,401,0,601'),
        ('paint 0', 'starter', '4,101,103,201,209,301,401,501,0'),
        ('unknown id', 'starter', '4,999,103,201,209,301,401,501,601'),
        ('shoulder in an arm slot', 'starter', '4,201,103,201,209,301,401,501,601'),
        ('arm in a shoulder slot', 'starter', '4,101,103,101,209,301,401,501,601'),
        ('arm as frame', 'starter', '101,101,103,201,209,301,401,501,601'),
        ('paint as fcs', 'starter', '4,101,103,201,209,301,401,601,601'),
        ('shield in the right arm', 'veteran', '4,111,101,201,209,301,401,501,601'),
        ('shield in the left arm', 'veteran', '4,101,111,201,209,301,401,501,601'),
        ('two shields', 'veteran', '4,111,111,201,209,301,401,501,601'),
        ('structure before ownership: shield right, unowned too', 'starter', '4,111,101,201,209,301,401,501,601'),
        ('owned part above the pilot rank is usable (rank gates buying only)', 'starter_gifted', '4,102,103,201,209,301,401,501,601'),
        ('unowned rank-2 part', 'starter', '4,102,103,201,209,301,401,501,601'),
        ('over weight on a medium (5800 > 4600 + 600)', 'veteran', '4,105,105,204,203,303,403,502,601'),
        ('the same build on a heavy fits', 'veteran', '8,105,105,204,203,303,403,502,601'),
        ('max EN build stays under 1.5x gen_std (1980 <= 2100)', 'ace', '8,104,104,203,203,301,404,504,601'),
        ('light frame at its load limit', 'veteran', '2,105,107,201,209,301,401,501,601'),
        ('ace top build', 'ace', '14,110,107,210,207,304,404,504,612'),
        ('the boss ai_loadout has shoulders in the arm slots', 'ace', '19,203,204,210,210,303,403,502,601'),
        ('pve boss frame is never owned', 'ace', '19,101,101,201,201,303,403,502,601'),
        ('ace with every weapon slot empty', 'ace', '11,0,0,0,0,303,403,502,612'),
        ('two of the same arm', 'starter', '1,101,101,201,209,301,401,501,601'),
        ('frame 0 and bad kind: the first bad position wins', 'starter', '0,201,103,201,209,301,401,501,601'),
    ]
    validate_cases = []
    for name, who, lo in cases:
        d, ref = validate(lo, pilots[who])
        validate_cases.append({'name': name, 'pilot': who, 'loadout': lo, 'deny': d, 'ref': ref})
    xp_cases = [{'rank': r, 'xp': xp_for(r)} for r in [1, 2, 3, 4, 5, 6, 10, 20, 30, 40, 50]]
    rank_cases = []
    for r in [2, 3, 10, 50]:
        x = xp_for(r)
        rank_cases += [{'xp': x - 1, 'rank': r - 1}, {'xp': x, 'rank': r}]
    rank_cases += [{'xp': 0, 'rank': 1}, {'xp': xp_for(50) * 10, 'rank': 50}]
    p_new = {'rank': 1, 'xp': 0, 'credits': 0, 'active': 1, 'owned': pilots['starter']['owned'], 'upgrades': {}, 'loadouts': starter['loadouts'], 'flags': 3}
    p_vet = {'rank': 20, 'xp': xp_for(20) + 123, 'credits': 4321, 'active': 2, 'owned': pilots['veteran']['owned'], 'upgrades': {'101': 2, '1': 5, '301': 1},
             'loadouts': [L1, '4,101,111,201,209,301,401,501,601', '0'], 'flags': 0}
    payloads = [{'name': 'new pilot', 'pilot': p_new, 'payload': payload(p_new)},
                {'name': 'veteran, empty slot 3', 'pilot': p_vet, 'payload': payload(p_vet)}]
    origin = [{'name': 'deny 3 part 105', 'kind': 2, 'values': [3, 105], 'entities': 4, 'pages': pages(2, [3, 105])},
              {'name': 'new pilot', 'kind': 1, 'entities': 4, 'values': pilot_ints(p_new), 'pages': pages(1, pilot_ints(p_new))}]
    out = {
        'version': 1,
        'parts_version': PARTS['version'],
        'notes': 'Generated by tools/contract_vectors.py from data/parts.json: the shared vectors for SERVER_CONTRACT.md sections 4-5. '
                 'validate: (deny, ref) per the rules in the script header; a deny payload is d1.<deny>.<ref>. '
                 'xp: xpFor(rank) totals; rank_for: rankFor(xp). payloads: the pilot payload string for a pilot state. '
                 'origin: the origin-encoding fallback pages (plugin IronFrame/Payload.cs; entity 0 = page, pages, kind; then 3 ints per entity).',
        'rules': {'en_factor': EN_FACTOR, 'kinds': KINDS, 'zero_allowed_positions': [2, 3, 4, 5], 'left_only_position': 3, 'xp': X},
        'pilots': pilots,
        'validate': validate_cases,
        'xp': xp_cases,
        'rank_for': rank_cases,
        'payloads': payloads,
        'origin': origin,
    }
    out.update(career_vectors())
    path = os.path.join(ROOT, 'data', 'contract_vectors.json')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, indent=1); f.write('\n')
    codes = {}
    for c in validate_cases: codes[c['deny']] = codes.get(c['deny'], 0) + 1
    print(f'{path}: {len(validate_cases)} validate cases (deny codes {dict(sorted(codes.items()))}), {len(xp_cases)} xp, {len(rank_cases)} rank_for, '
          f'{len(payloads)} payloads, {len(origin)} origin, {len(out["profiles"])} profiles ({", ".join(str(len(c["pages"])) for c in out["profiles"])} pages), '
          f'{len(out["server_rules"])} rules, {len(out["boards"])} boards ({", ".join(str(len(c["pages"])) for c in out["boards"])} pages), {len(out["texts"])} texts, {len(out["honours"])} honours')
    print('xpFor:', ', '.join(f"{c['rank']}={c['xp']}" for c in xp_cases))
    bad = [c for c in validate_cases if c['name'].startswith('starter loadout') and c['deny']]
    print('rank is a buy gate only: validate never returns 2 (see the header)')
    if bad: print('NOTE: starter loadouts that fail for a starter pilot:', '; '.join(f"{c['name'].split(':')[0]} -> deny {c['deny']} part {c['ref']}" for c in bad))
    return 0


if __name__ == '__main__':
    sys.exit(main())
