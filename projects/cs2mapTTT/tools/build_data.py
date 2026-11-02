"""Bake maps/*.json (written by ttt_convert.py) into ttt.js between the MAP_DATA markers. usage: python3 tools/build_data.py"""
import json, glob, os, re
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
js = os.path.join(root, 'addon', 'maps', 'scripts', 'ttt.js')
data = {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob(os.path.join(root, 'maps', '*.json')))}
body = 'const MAP_DATA = ' + json.dumps(data, separators=(',', ':')) + ';'
s = open(js).read()
s2 = re.sub(r'(// MAP_DATA_BEGIN[^\n]*\n).*?(\n// MAP_DATA_END)', lambda m: m.group(1) + body + m.group(2), s, count=1, flags=re.S)
assert s2 != s or body in s, 'markers not found'
open(js, 'w').write(s2)
print('MAP_DATA: %d map(s): %s' % (len(data), ', '.join(data)))
