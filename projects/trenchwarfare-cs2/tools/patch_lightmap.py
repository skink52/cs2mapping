"""tw34: lightmap charts. Barbed wire placed as prop_static with bakelighting 1 (8 wire_fence_b, 1 wire_fence_a, 9 wire_coil in the
user's map; ~2,000 lightmap charts each) goes to light probes like the rest of the wire (make_map.probed()).
usage: patch_lightmap.py <user vmap> <out vmap>"""
import sys
import dmx

PROBE = ('models/tw/wire_fence_a/', 'models/tw/wire_fence_b/', 'models/tw/wire_coil/')
d = dmx.DMX.load(sys.argv[1]); n = 0
def walk(e):
    global n
    for c in e.get('children') or []:
        if c.type == 'CMapEntity':
            ep = c.get('entity_properties')
            if ep.get('classname') == 'prop_static' and (ep.get('model') or '').startswith(PROBE) and ep.get('bakelighting') == '1':
                for a in ep.attrs:
                    if a[0] == 'bakelighting': a[2] = '0'; n += 1
        walk(c)
walk(d.root.get('world'))
d.elements = [d.root]
d.save(sys.argv[2])
print('%d wire props now light-probed' % n)
