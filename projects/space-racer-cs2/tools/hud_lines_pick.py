"""hud_lines_pick.py: choose the HUD lines that are drawn as one picture instead of one glyph class per letter.

24 Nov 2026: the live JB box crashed when CS2's serializer overflowed the custom HUD's class state, which grows with every
class switched on for every player; a pixel-text row costs one class per letter. A line whose text is known ahead can be one
picture on the row panel (one class). This picks those lines from what the rows really showed in mock runs
(test/mock_cs2.mjs option `strings` -> build/hud_lines_seen.json): no digits (times, counts, positions change), no mock player
names (BOT12, HUMAN3, late40_0: real names can't be known ahead), at least 3 letters; most letters saved first, at most
MAX per title (each picture is a class name, and a layout keeps only ~1024 names).

usage:  python -I tools/hud_lines_pick.py [build/hud_lines_seen.json] [data/hud_lines.json]
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'build', 'hud_lines_seen.json')
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'data', 'hud_lines.json')
MAX = 250
NAMES = re.compile(r'BOT\d|HUMAN\d|LATE\d|_\d')

seen = json.load(open(SRC, encoding='utf-8'))
by = {}
for key, n in seen.items():
    theme, row, text, col = key.split('\t')
    if re.search(r'\d', text) or NAMES.search(text.upper()) or len(text) < 3: continue
    by.setdefault(theme, []).append((n * (len(text) - 1), row, text, col))
out = {}
for theme, lst in sorted(by.items()):
    lst.sort(key=lambda x: (-x[0], x[1], x[2]))
    out[theme] = [[row, text, col] for _, row, text, col in lst[:MAX]]
    print('%s: %d lines (of %d candidates)' % (theme, len(out[theme]), len(lst)))
os.makedirs(os.path.dirname(DST), exist_ok=True)
json.dump(out, open(DST, 'w', encoding='utf-8'), indent=0)
print('->', DST)
