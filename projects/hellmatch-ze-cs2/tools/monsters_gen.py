"""One-off generator: writes src/core/05_monsters.js (monster state and thing tables) from the Doom source tables.

usage: monsters_gen.py <linuxdoom-1.10 dir>

The tables (frame sequences, tic counts, health, speed, radius...) are the shared data every Doom-compatible engine
and WAD relies on; Freedoom's monster sprites and sounds are drawn to exactly these sequences. The behaviour that
uses them is implemented in src/core/35_enemy.js.
"""
import os, re, sys

SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src/core/00_a_monsters.js')

info_h = open(os.path.join(SRC, 'info.h')).read()
info_c = open(os.path.join(SRC, 'info.c')).read()
sounds_h = open(os.path.join(SRC, 'sounds.h')).read()

def enum(text, name):
    body = text.split('typedef enum\n{', 1)
    out = []
    for m in re.finditer(r'typedef enum\s*\{(.*?)\}\s*(\w+);', text, re.S):
        if m.group(2) == name:
            for line in m.group(1).split('\n'):
                line = line.split('//')[0].strip().rstrip(',')
                if line and re.match(r'^[A-Za-z_]\w*$', line): out.append(line)
    return out

STATE_NAMES = enum(info_h, 'statenum_t')
MOBJ_NAMES = enum(info_h, 'mobjtype_t')
SFX_NAMES = enum(sounds_h, 'sfxenum_t')
assert STATE_NAMES[0] == 'S_NULL' and MOBJ_NAMES[0] == 'MT_PLAYER' and SFX_NAMES[0] == 'sfx_None', (STATE_NAMES[:2], MOBJ_NAMES[:2], SFX_NAMES[:2])

# states: {SPR_POSS,0,10,{A_Look},S_POSS_STND2,0,0},	// S_POSS_STND
states = {}
order = []
for m in re.finditer(r'\{SPR_(\w+),(\d+),(-?\d+),\{(\w+)\},(S_\w+),0,0\}', info_c):
    spr, frame, tics, action, nxt = m.groups()
    name = STATE_NAMES[len(order)]
    order.append(name)
    frame = int(frame)
    states[name] = (spr, chr(65 + (frame & 32767)), int(tics), None if action == 'NULL' else action, nxt, 1 if frame & 32768 else 0)
assert len(order) == len(STATE_NAMES) - 1, (len(order), len(STATE_NAMES))   # the enum ends with NUMSTATES

# mobjinfo: 23 fields per block, in enum order
FIELDS = ['doomednum', 'spawnstate', 'spawnhealth', 'seestate', 'seesound', 'reactiontime', 'attacksound', 'painstate',
          'painchance', 'painsound', 'meleestate', 'missilestate', 'deathstate', 'xdeathstate', 'deathsound', 'speed',
          'radius', 'height', 'mass', 'damage', 'activesound', 'flags', 'raisestate']
mobjs = {}
body = info_c[info_c.index('mobjinfo_t mobjinfo[NUMMOBJTYPES]'):]
blocks = re.findall(r'\{\s*//\s*(MT_\w+)\s*(.*?)\n\s*\},?', body, re.S)
for name, blk in blocks:
    vals = [l.split('//')[0].strip().rstrip(',').strip() for l in blk.strip().split('\n')]
    vals = [v for v in vals if v]
    assert len(vals) == 23, (name, len(vals))
    mobjs[name] = dict(zip(FIELDS, vals))

MONSTERS = {   # MT name: our key, Freedoom's name for the creature, roster class
    'MT_POSSESSED': ('ZOMBIE', 'zombie', 'POSS'), 'MT_SHOTGUY': ('SHOTGUY', 'shotgun zombie', 'SPOS'),
    'MT_CHAINGUY': ('CHAINGUY', 'minigun zombie', 'CPOS'), 'MT_TROOP': ('IMP', 'serpentipede', 'TROO'),
    'MT_SERGEANT': ('DEMON', 'flesh worm', 'SARG'), 'MT_SHADOWS': ('SPECTRE', 'stealth worm', 'SARG'),
    'MT_SKULL': ('LOSTSOUL', 'deadflare', 'SKUL'), 'MT_HEAD': ('CACO', 'trilobite', 'HEAD'),
    'MT_KNIGHT': ('KNIGHT', 'pain bringer', 'BOS2'), 'MT_BRUISER': ('BARON', 'pain lord', 'BOSS'),
    'MT_UNDEAD': ('REVENANT', 'dark soldier', 'SKEL'), 'MT_FATSO': ('MANCUBUS', 'combat slug', 'FATT'),
    'MT_BABY': ('ARACHNOTRON', 'technospider', 'BSPI'), 'MT_PAIN': ('PAINELEMENTAL', 'summoner', 'PAIN'),
    'MT_VILE': ('ARCHVILE', 'flame bringer', 'VILE'), 'MT_CYBORG': ('CYBERDEMON', 'assault tripod', 'CYBR'),
    'MT_SPIDER': ('MASTERMIND', 'large technospider', 'SPID'),
}
OTHERS = {  # projectiles and effects the monsters spawn
    'MT_TROOPSHOT': 'IMPBALL', 'MT_HEADSHOT': 'CACOBALL', 'MT_BRUISERSHOT': 'BARONBALL', 'MT_TRACER': 'TRACER',
    'MT_SMOKE': 'SMOKE', 'MT_FATSHOT': 'FATSHOT', 'MT_ARACHPLAZ': 'ARACHPLASMA', 'MT_FIRE': 'VILEFIRE',
}
# things that already exist in 00_defs.js keep their names there
EXISTING_MT = {'MT_ROCKET': 'ROCKET', 'MT_PUFF': 'PUFF', 'MT_BLOOD': 'BLOOD', 'MT_PLAYER': 'PLAYER'}

needed = []
seen = set()
def walk(st):
    while st and st != 'S_NULL' and st not in seen:
        seen.add(st); needed.append(st)
        st = states[st][4]
for mt in list(MONSTERS) + list(OTHERS):
    m = mobjs[mt]
    for f in ('spawnstate', 'seestate', 'painstate', 'meleestate', 'missilestate', 'deathstate', 'xdeathstate', 'raisestate'):
        if m[f] != '0': walk(m[f])
# A_VileAttack / A_StartFire etc. reference states by name
for extra in ('S_FIRE1', 'S_SKULL_RUN1', 'S_SMOKE1', 'S_VILE_HEAL1'):
    walk(extra)

def jsname(s): return s[2:]       # S_POSS_STND -> POSS_STND
def sfx(s): return "'%s'" % s[4:] if s != '0' and s != 'sfx_None' else 'null'
def num(v):
    v = v.replace('*FRACUNIT', '')
    return str(eval(v, {}, {}))

lines = ["// ===================================================================================",
         "// Part 0a: monster state and thing tables (generated by tools/monsters_gen.py from the Doom tables;",
         "// the behaviour is in 35_enemy.js). Loaded before 00_defs.js, which merges these into STATE_DEFS / MOBJINFO. Freedoom's creature names are used in messages.",
         "// ===================================================================================",
         "",
         "const MONSTER_STATE_DEFS = {"]
for st in needed:
    spr, fr, tics, act, nxt, bright = states[st]
    lines.append("  %s: ['%s', '%s', %d, %s, '%s'%s]," % (jsname(st), spr, fr.replace('\\', '\\\\'), tics, "'%s'" % act if act else 'null', jsname(nxt) if nxt != 'S_NULL' else 'NULL', ', 1' if bright else ''))
lines.append("};")
lines.append("")
lines.append("// key: [doomednum, name, sprite, fields]")
lines.append("const MONSTER_DEFS = {")
def fields(m, kind, extra=''):
    f = []
    for k in ('spawnstate', 'seestate', 'painstate', 'meleestate', 'missilestate', 'deathstate', 'xdeathstate', 'raisestate'):
        if m[k] not in ('0', 'S_NULL'): f.append("%s: '%s'" % (k, jsname(m[k])))
    for k in ('seesound', 'attacksound', 'painsound', 'deathsound', 'activesound'):
        if m[k] not in ('0', 'sfx_None'): f.append("%s: %s" % (k, sfx(m[k])))
    for k in ('spawnhealth', 'reactiontime', 'painchance', 'speed', 'radius', 'height', 'mass', 'damage'):
        if m[k] != '0': f.append("%s: %s" % (k, num(m[k])))
    f.append("flags: '%s'" % (m['flags'] if m['flags'] != '0' else ''))   # resolved in 00_defs.js (this file loads first)
    return ', '.join(f)
for mt, (key, fdname, spr) in MONSTERS.items():
    m = mobjs[mt]
    lines.append("  %s: { kind: 'monster', doomednum: %s, name: '%s', %s }," % (key, m['doomednum'], fdname, fields(m, 'monster')))
for mt, key in OTHERS.items():
    m = mobjs[mt]
    kind = 'missile' if 'MF_MISSILE' in m['flags'] else 'fx'
    lines.append("  %s: { kind: '%s', %s }," % (key, kind, fields(m, kind)))
lines.append("};")
lines.append("")
open(OUT, 'w', newline='\n').write('\n'.join(lines) + '\n')
print('wrote', OUT, len(needed), 'states,', len(MONSTERS) + len(OTHERS), 'things')
sprites = sorted(set(states[s][0] for s in needed))
print('sprites:', ' '.join(sprites))
sounds = sorted(set(mobjs[mt][k][4:] for mt in list(MONSTERS) + list(OTHERS) for k in ('seesound', 'attacksound', 'painsound', 'deathsound', 'activesound') if mobjs[mt][k] not in ('0', 'sfx_None')))
print('sounds:', ' '.join(sounds))
