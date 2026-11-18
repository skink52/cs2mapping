"""Writes build/hud_strings.json: every fixed HUD line pre-rendered as one image (hud.py draws them, the script indexes
them). Hellmatch's pickup messages and round lines, the ZE lines, every stage name and message from the sidecars
(ze/*.json), and the game side's own list src/core/zz_hud_strings.json (array of strings) when it exists.

usage: hud_strings.py [out.json]
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/hud_strings.json')
src = open(os.path.join(ROOT, 'src/core/00_defs.js'), encoding='utf-8').read()
msgs = re.findall(r"GOT[A-Z0-9]+: '([^']+)'", src)
fixed = msgs + ['FIGHT!', 'RESPAWNING...', 'SPECTATING', '1', '2', '3', 'RED TEAM WINS', 'BLUE TEAM WINS', 'DRAW',
                'Exits are disabled in this game.', 'MOVE OR YOU WILL BE MARKED AFK', 'FREE FOR ALL', 'TEAM DEATHMATCH',
                'TEAM ELIMINATION', 'LAST MAN STANDING', 'BOSS BATTLE', 'VICTORY', 'OVERRUN', 'WAVE CLEARED', 'BOSS INCOMING',
                'TIME UP',
                # Hellmatch ZE
                'ZOMBIE ESCAPE', 'T ESCAPED', 'CT ESCAPED', 'T WIN', 'CT WIN', 'YOU ARE A ZOMBIE', 'YOU ESCAPED',
                'HOLD THE ZONE', 'BOSS DEFEATED', 'THE HUMANS ESCAPED', 'ALL HUMANS DEAD']
for p in sorted(glob.glob(os.path.join(ROOT, 'ze', '*.json'))):
    sc = json.load(open(p, encoding='utf-8'))
    for st in sc.get('stages', []):
        if st.get('name'): fixed.append(st['name'])
        for key in ('on_start', 'on_done'):
            for a in st.get(key, []) or []:
                if 'message' in a: fixed.append(a['message'])
    if sc.get('title'): fixed.append(sc['title'])
game = os.path.join(ROOT, 'src/core/zz_hud_strings.json')
if os.path.exists(game):
    extra = json.load(open(game, encoding='utf-8'))
    if not isinstance(extra, list) or not all(isinstance(s, str) for s in extra):
        raise SystemExit('hud_strings: src/core/zz_hud_strings.json must be an array of strings')
    fixed += extra
out = sorted(set(s.upper() for s in fixed))
os.makedirs(os.path.dirname(OUTP), exist_ok=True)
json.dump(out, open(OUTP, 'w'))
print('hud strings: %d (%s)' % (len(out), 'with the game list' if os.path.exists(game) else 'no src/core/zz_hud_strings.json yet'))
