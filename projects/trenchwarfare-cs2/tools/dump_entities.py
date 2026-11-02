"""Writes named point entities + spawns from a vmap as JSON, for the mock engine.  usage: dump_entities.py <vmap> <out.json>"""
import sys, json, dmx
d = dmx.DMX.load(sys.argv[1]); out = []
def walk(n):
    for c in n.get('children') or []:
        if c.type == 'CMapEntity':
            ep = c.get('entity_properties'); cls = ep.get('classname'); nm = ep.get('targetname') or ''
            if nm or cls.startswith('info_player'):
                out.append(dict(name=nm, cls=cls, origin=list(c.get('origin')), angles=list(c.get('angles'))))
        walk(c)
walk(d.root.get('world'))
json.dump(out, open(sys.argv[2], 'w'), indent=0)
print(len(out), 'entities')
