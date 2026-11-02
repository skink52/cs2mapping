"""The world layout, shared by the map writer (vmap.py), the script (as LAYOUT data) and previews.

Everything is a sealed box in the void with its floor at z = 0, so squads move between areas by teleport and a room can be
reused by any squad at any time:
  - lobby: where both teams spawn every CS2 round (64 spawns), the script sorts squads and sends them out
  - vault pool: POOL_COLS x POOL_ROWS vault rooms north of the lobby; a floor is a chain of rooms drawn from the pool
  - staging: 8 small buy rooms (func_buyzone) south of the lobby, one per squad, where quick squads wait for the breach
  - arena: the central showdown, three tiers, 8 balconies the squads land on
  - cache: a sealed room holding one prop per model the script SetModel()s to

usage: layout.py <out.json>   (also imported by vmap.py)
"""
import json, math, random, sys

ROOM_W, ROOM_H = 1024.0, 272.0          # vault footprint and ceiling (pillar base 16 + 128 + 128 = 272: pillars meet the ceiling)
GAP = 512.0
POOL_COLS, POOL_ROWS = 4, 3
LOBBY = dict(cx=0.0, cy=0.0, w=1536.0, d=1536.0, h=320.0)
STAGE_W, STAGE_D, STAGE_H, N_STAGE = 512.0, 384.0, 256.0, 8
ARENA = dict(cx=0.0, cy=-6656.0, w=3072.0, d=3072.0, h=448.0)
CACHE = dict(cx=5632.0, cy=0.0, w=1024.0, d=512.0, h=192.0)
PAD = 96.0                               # entry / exit plate half size
TIER1_H, DAIS_H, BALCONY_H = 48.0, 144.0, 96.0

# vault kinds: what stands in the room besides the walls. pillars are (x, y) offsets from the room centre;
# blocks are basalt cover blocks (stock pillar_block01, 96 x 96 x 64); dais is a raised square (half size, height); statues face the entry.
VAULTS = {
    'colonnade': dict(pillars=[(x, y) for x in (-256, 0, 256) for y in (-224, 224)], blocks=[], dais=None, statues=[]),
    'cross':     dict(pillars=[(-288, -288), (288, -288), (-288, 288), (288, 288)], blocks=[(0, -320), (0, 320)], dais=(160, 48), statues=[]),
    'grid':      dict(pillars=[(x, y) for x in (-256, 0, 256) for y in (-256, 0, 256) if (x, y) != (0, 0)], blocks=[], dais=None, statues=[]),
    'split':     dict(pillars=[(0, -352), (0, 352)], blocks=[(0, -160), (0, -64), (0, 64), (0, 160), (-320, 0), (320, 0)], dais=None, statues=[]),
    'ring':      dict(pillars=[(288 * math.cos(a), 288 * math.sin(a)) for a in [k * math.pi / 4 for k in range(8)]], blocks=[], dais=(96, 48), statues=[]),
    'shrine':    dict(pillars=[(-320, -320), (320, -320), (-320, 320), (320, 320)], blocks=[(-192, 0), (192, 0)], dais=(192, 96), statues=[(0, 0)]),
    # the three kinds below are mostly dressing (tools/dress.py): an overgrown garden court, a data archive, a collapsed vault
    'garden':    dict(pillars=[(-288, -288), (288, -288), (-288, 288), (288, 288)], blocks=[], dais=(128, 48), statues=[]),
    'archive':   dict(pillars=[(x, y) for x in (-192, 192) for y in (-288, 0, 288)], blocks=[(0, -160), (0, 160)], dais=None, statues=[]),
    'ruin':      dict(pillars=[(-256, -192), (256, 192), (0, 320)], blocks=[(-96, 96), (160, -224), (-288, 288)], dais=None, statues=[]),
}
KINDS = list(VAULTS)


def box(cx, cy, w, d, h, z0=0.0):
    return (cx - w / 2, cy - d / 2, z0, cx + w / 2, cy + d / 2, z0 + h)


def rooms():
    out = []
    total_w = POOL_COLS * ROOM_W + (POOL_COLS - 1) * GAP
    x_first = -total_w / 2 + ROOM_W / 2
    y_first = LOBBY['d'] / 2 + GAP + ROOM_W / 2
    for r in range(POOL_ROWS):
        for c in range(POOL_COLS):
            i = r * POOL_COLS + c
            cx, cy = x_first + c * (ROOM_W + GAP), y_first + r * (ROOM_W + GAP)
            kind = KINDS[i % len(KINDS)]
            mirror = (i // len(KINDS)) % 2 == 1          # the second use of a kind is mirrored in y
            v = VAULTS[kind]
            m = -1.0 if mirror else 1.0
            out.append(dict(
                id=i, kind=kind, mirror=mirror, cx=cx, cy=cy, box=box(cx, cy, ROOM_W, ROOM_W, ROOM_H),
                entry=(cx - ROOM_W / 2 + 128, cy, 0.0), exit=(cx + ROOM_W / 2 - 128, cy, 0.0),
                pillars=[(cx + x, cy + m * y) for x, y in v['pillars']],
                blocks=[(cx + x, cy + m * y) for x, y in v['blocks']],
                dais=None if v['dais'] is None else dict(cx=cx, cy=cy, half=v['dais'][0], h=v['dais'][1]),
                statues=[(cx + x, cy + m * y) for x, y in v['statues']],
                name='nt_room_%02d' % i))
    for rm in out:
        rm['spots'] = enemy_spots(rm)
    return out


def enemy_spots(rm):
    """free floor points on a 128 grid, clear of pillars, blocks, the dais and the two plates"""
    cx, cy = rm['cx'], rm['cy']
    pts = []
    for gx in range(-3, 4):
        for gy in range(-3, 4):
            x, y = cx + gx * 128, cy + gy * 128
            if any(math.hypot(x - px, y - py) < 100 for px, py in rm['pillars'] + rm['blocks']): continue
            if rm['dais'] and abs(x - cx) < rm['dais']['half'] + 40 and abs(y - cy) < rm['dais']['half'] + 40: continue
            if any(math.hypot(x - sx, y - sy) < 120 for sx, sy in rm['statues']): continue
            if math.hypot(x - rm['entry'][0], y - rm['entry'][1]) < 200: continue
            if math.hypot(x - rm['exit'][0], y - rm['exit'][1]) < 160: continue
            pts.append((x, y))
    return pts


def stagings():
    total = N_STAGE * STAGE_W + (N_STAGE - 1) * 256
    x0 = -total / 2 + STAGE_W / 2
    cy = -(LOBBY['d'] / 2 + GAP + STAGE_D / 2)
    return [dict(id=k, cx=x0 + k * (STAGE_W + 256), cy=cy, box=box(x0 + k * (STAGE_W + 256), cy, STAGE_W, STAGE_D, STAGE_H),
                 pad=(x0 + k * (STAGE_W + 256), cy, 0.0), name='nt_stage_%d' % k) for k in range(N_STAGE)]


def arena():
    A = dict(ARENA)
    cx, cy, w, d = A['cx'], A['cy'], A['w'], A['d']
    A['box'] = box(cx, cy, w, d, A['h'])
    A['tier1'] = box(cx, cy, 2048, 2048, TIER1_H)
    A['dais'] = box(cx, cy, 640, 640, DAIS_H)
    A['dais_pillars'] = [(cx + sx * 224, cy + sy * 224) for sx in (-1, 1) for sy in (-1, 1)]
    # steps up to the dais on all four sides: two 48-unit risers
    A['steps'] = []
    for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for k, (reach, hgt) in enumerate(((448, 48), (384, 96))):
            if dx:
                A['steps'].append((cx + dx * (reach - 64) if dx > 0 else cx + dx * reach, cy - 128, 0.0,
                                   cx + dx * reach if dx > 0 else cx + dx * (reach - 64), cy + 128, hgt))
            else:
                A['steps'].append((cx - 128, cy + dy * (reach - 64) if dy > 0 else cy + dy * reach, 0.0,
                                   cx + 128, cy + dy * reach if dy > 0 else cy + dy * (reach - 64), hgt))
    # eight balconies against the walls, two per wall, the squads land on them
    bal = []
    for k in range(8):
        wall, side = divmod(k, 2)
        off = (-768.0, 768.0)[side]
        if wall == 0: b = (cx - w / 2, cy + off - 192, 0.0, cx - w / 2 + 384, cy + off + 192, BALCONY_H); yaw = 0
        elif wall == 1: b = (cx + w / 2 - 384, cy + off - 192, 0.0, cx + w / 2, cy + off + 192, BALCONY_H); yaw = 180
        elif wall == 2: b = (cx + off - 192, cy - d / 2, 0.0, cx + off + 192, cy - d / 2 + 384, BALCONY_H); yaw = 90
        else: b = (cx + off - 192, cy + d / 2 - 384, 0.0, cx + off + 192, cy + d / 2, BALCONY_H); yaw = 270
        bal.append(dict(id=k, box=b, pad=((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, BALCONY_H), yaw=yaw, name='nt_arena_%d' % k))
    A['balconies'] = bal
    # cover blocks on the outer floor, seeded so every build matches
    rng = random.Random(7)
    blocks = []
    while len(blocks) < 20:
        x, y = cx + rng.uniform(-w / 2 + 160, w / 2 - 160), cy + rng.uniform(-d / 2 + 160, d / 2 - 160)
        if abs(x - cx) < 1024 + 96 and abs(y - cy) < 1024 + 96: continue               # not on the tier
        if any(b['box'][0] - 96 < x < b['box'][3] + 96 and b['box'][1] - 96 < y < b['box'][4] + 96 for b in bal): continue
        if any(math.hypot(x - bx, y - by) < 220 for bx, by in blocks): continue
        blocks.append((x, y))
    A['blocks'] = blocks
    return A


def world():
    L = dict(LOBBY); L['box'] = box(L['cx'], L['cy'], L['w'], L['d'], L['h']); L['name'] = 'nt_lobby'
    C = dict(CACHE); C['box'] = box(C['cx'], C['cy'], C['w'], C['d'], C['h'])
    return dict(room_w=ROOM_W, room_h=ROOM_H, lobby=L, rooms=rooms(), stagings=stagings(), arena=arena(), cache=C,
                tier1_h=TIER1_H, dais_h=DAIS_H, balcony_h=BALCONY_H, pad=PAD)


def all_boxes(W):
    return [W['lobby']['box'], W['cache']['box'], W['arena']['box']] + [r['box'] for r in W['rooms']] + [s['box'] for s in W['stagings']]


if __name__ == '__main__':
    W = world()
    json.dump(W, open(sys.argv[1], 'w'), indent=0)
    bb = all_boxes(W)
    print('%d rooms, %d stagings, arena at %s; map %s .. %s' % (len(W['rooms']), len(W['stagings']), (ARENA['cx'], ARENA['cy']),
          tuple(int(min(b[k] for b in bb)) for k in range(3)), tuple(int(max(b[k + 3] for b in bb)) for k in range(3))))
