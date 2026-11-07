"""ba_jail_keimusho 2026-11-07: fire game stop button (fireoff) fixes.

- fireoff only disabled firehurt1-10 (and only unswept those): firehurt11-20 stayed on after the game was stopped, with their
  particles stopped, so the right half kept hurting with no fire. Now every firehurt1-20 is Disabled + Unswept.
- A fire picked just before Stop enabled its hurt 2 s later (the case outputs are delayed 2 s). Every stop output is sent again
  at 2.5 s so a late Enable is undone.
- Every fireNbrush button is Locked on stop (an unlocked button of an unextinguished fire stayed usable).
- The duplicate fireN Stop outputs (0.0 and 0.1) are reduced to one.
Usage: python fix_20261107_firegame.py <path to ba_jail_keimusho.vmap>   (back the vmap up first; Hammer closed)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import vmapedit, dmx

path = sys.argv[1]
m = vmapedit.Map(path)
off = [e for e in m.entities() if m.name(e) == 'fireoff']
assert len(off) == 1, off
off = off[0]

# drop the old fire stop outputs so the set below is the whole, de-duplicated stop list
FIRE = {'fire%d' % n for n in range(1, 21)} | {'firehurt%d' % n for n in range(1, 21)} | {'fire%dbrush' % n for n in range(1, 21)}
keep, dropped = [], 0
for c in dmx.geta(m.E[off], b'connectionsData')[2]:
    t = m.conn_tuple(m.E[c])
    if t[1] in FIRE or (t[1] == 'sweepscript' and t[3].startswith('Unsweep_firehurt')):
        dropped += 1; continue
    keep.append(c)
dmx.geta(m.E[off], b'connectionsData')[2][:] = keep

added = 0
for delay in (0.0, 2.5):
    for n in range(1, 21):
        for tgt, inp, prm in (('firehurt%d' % n, 'Disable', ''), ('sweepscript', 'RunScriptInput', 'Unsweep_firehurt%d' % n),
                              ('fire%d' % n, 'Stop', ''), ('fire%dbrush' % n, 'Lock', '')):
            m.add_conn(off, 'OnPressed', tgt, inp, prm, delay); added += 1
# the timer can't have queued anything new after it was disabled, but disable it again with the late pass too
m.add_conn(off, 'OnPressed', 'firetimer', 'Disable', '', 2.5); added += 1

m.save(path)
print('fireoff: %d old fire outputs removed, %d added' % (dropped, added))
for c in m.conns(off): print('  ', m.conn_tuple(c))
