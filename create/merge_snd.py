"""Puts the FreeDM sound events into the addon's own soundevents_addon.vsndevts, keeping everything already in it.

usage: merge_snd.py <template.vsndevts> <ours.vsndevts>   (ours is rewritten in place)
"""
import sys
tpl, ours = sys.argv[1], sys.argv[2]
t = open(tpl, encoding='utf-8').read()
o = open(ours, encoding='utf-8').read()
if '"fdm.base"' in t:
    sys.exit('template already has FreeDM events; nothing to merge')
start = o.index('\n{') + 2                         # first line that is just the root brace (the header line has braces too)
body = o[start:o.rindex('}')]                      # our events without the outer braces
first = t.index('\n{') + 2                         # just inside the template's root block
open(ours, 'w', encoding='utf-8', newline='\n').write(t[:first] + '\n\t// ---- FreeDM sound events (generated) ----' + body + '\t// ---- end FreeDM ----\n' + t[first:])
print('merged %d FreeDM events into the addon sound events' % body.count('\n\t"fdm.'))
