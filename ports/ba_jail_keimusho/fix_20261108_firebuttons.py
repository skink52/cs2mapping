"""ba_jail_keimusho 2026-11-08: fire game hurt with all fires out (per-fire lit flag).

firecaseN picks a fire every 8 s: fireN Start at 0.1 s, but firehurtN Enable + fireNbrush Unlock at 2.0 s and Sweep_firehurtN at 2.1 s.
Those delayed outputs can't be cancelled. If the fire was already burning when picked again and someone put it out inside that
window, they landed after the button's Disable: the half took 4 dps with no fire, and an invisible button stayed usable until the
fire was picked again. The slower team has more fires burning, so more re-picks, so it hit this more often.
(A first try, the button repeating its stop 2.15 s later, still left up to 2 s of damage, and a fire re-picked within 2 s of
being put out lost its flames but kept its hurt; mock_firegame_io.py caught both.)

Fix: a logic_branch fire_litN per fire (InitialValue 0).
  case pick:      fireN Start 0.1 (kept), fire_litN SetValue 1 at 0.1, fire_litN Test at 2.0
                  (replaces firehurtN Enable / fireNbrush Unlock at 2.0 and Sweep_firehurtN at 2.1)
  fire_litN       OnTrue -> firehurtN Enable, fireNbrush Unlock, Sweep_firehurtN, fireN Start (all 0 s)
                  OnFalse -> fireN Stop, firehurtN Disable, fireNbrush Lock, Unsweep_firehurtN (settles a same-tick press/re-pick)
  fireNbrush      + fire_litN SetValue 0 at 0 s and Test at 0.15 s (settles a press in the same tick as the case's Test);
                  button locks itself (fire2/fire3brush had a duplicate Stop instead of Lock)
  fireoff         + fire_lit1-20 SetValue 0 at 0 s and 2.5 s
So the hurt and button only come on 2 s after a pick if the fire is still lit then.
Usage: python fix_20261108_firebuttons.py <path to ba_jail_keimusho.vmap>   (back the vmap up first; Hammer closed)
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import vmapedit, dmx

path = sys.argv[1]
m = vmapedit.Map(path)
by = {}
for e in m.entities(): by.setdefault(m.name(e), []).append(e)
if any(n.startswith('fire_lit') for n in by): sys.exit('fire_lit branches already in the map - already applied')
def one(n):
    assert len(by.get(n, [])) == 1, (n, by.get(n)); return by[n][0]

# 1. the branches, next to their fire
for n in range(1, 21):
    o = m.origin(one('fire%d' % n))
    b = m.new_entity('logic_branch', [o[0], o[1], o[2] + 24], {'targetname': 'fire_lit%d' % n, 'InitialValue': '0'})
    m.add_conn(b, 'OnTrue', 'firehurt%d' % n, 'Enable', '', 0.0)
    m.add_conn(b, 'OnTrue', 'fire%dbrush' % n, 'Unlock', '', 0.0)
    m.add_conn(b, 'OnTrue', 'sweepscript', 'RunScriptInput', 'Sweep_firehurt%d' % n, 0.0)
    # the test settles everything to the flag: a press in the same tick as a re-pick can leave the flames out with the flag
    # set (the button's Stop is delayed 0.1 s) or burning with it clear
    m.add_conn(b, 'OnTrue', 'fire%d' % n, 'Start', '', 0.0)
    for tgt, inp, prm in (('fire%d' % n, 'Stop', ''), ('firehurt%d' % n, 'Disable', ''), ('fire%dbrush' % n, 'Lock', ''),
                          ('sweepscript', 'RunScriptInput', 'Unsweep_firehurt%d' % n)):
        m.add_conn(b, 'OnFalse', tgt, inp, prm, 0.0)

# 2. the cases: delayed Enable/Unlock/Sweep -> SetValue 1 with the Start, Test at 2.0
for case, base in (('firecase1', 0), ('firecase2', 10)):
    c = one(case)
    conns = dmx.geta(m.E[c], b'connectionsData')[2]
    keep, cases = [], set()
    for x in conns:
        t = m.conn_tuple(m.E[x])
        mt = re.match(r'OnCase(\d+)$', t[0])
        if mt:
            n = base + int(mt.group(1)); cases.add((t[0], n))
            if (t[1], t[2]) in (('firehurt%d' % n, 'Enable'), ('fire%dbrush' % n, 'Unlock')): continue
            if t[1] == 'sweepscript' and t[3] == 'Sweep_firehurt%d' % n: continue
        keep.append(x)
    conns[:] = keep
    assert len(cases) == 10, (case, cases)
    for out, n in sorted(cases):
        m.add_conn(c, out, 'fire_lit%d' % n, 'SetValue', '1', 0.1)
        m.add_conn(c, out, 'fire_lit%d' % n, 'Test', '', 2.0)

# 3. the buttons: clear the flag; one Stop; lock itself
for n in range(1, 21):
    b = one('fire%dbrush' % n)
    conns = dmx.geta(m.E[b], b'connectionsData')[2]
    seen, keep = False, []
    for x in conns:
        t = m.conn_tuple(m.E[x])
        if t[1] == 'fire%d' % n and t[2] == 'Stop':
            if seen: continue
            seen = True
        keep.append(x)
    conns[:] = keep
    if not any(m.conn_tuple(m.E[x])[1:3] == ('fire%dbrush' % n, 'Lock') for x in keep):
        m.add_conn(b, 'OnPressed', 'fire%dbrush' % n, 'Lock', '', 0.0)
    m.add_conn(b, 'OnPressed', 'fire_lit%d' % n, 'SetValue', '0', 0.0)
    # settle again after this press's own 0.1 s Stop: a press in the same tick as the case's Test (outputs due together run in
    # no promised order) could otherwise leave the hurt on with the fire out
    m.add_conn(b, 'OnPressed', 'fire_lit%d' % n, 'Test', '', 0.15)

# 4. the stop button
off = one('fireoff')
for d in (0.0, 2.5):
    for n in range(1, 21): m.add_conn(off, 'OnPressed', 'fire_lit%d' % n, 'SetValue', '0', d)

# 5. the map's entity count list (Hammer rewrites it on save anyway)
if m.doc.prefix:
    P = {pa[0]: pa for pa in m.doc.prefix[0]}
    t, nm, ct = (P.get(k) for k in (b'map_subasset_reference_types', b'map_subasset_reference_names', b'map_subasset_reference_counts'))
    if t and nm and ct and len(t[2]) == len(nm[2]) == len(ct[2]):
        idx = [i for i in range(len(nm[2])) if nm[2][i] == b'logic_branch' and t[2][i] == b'entity']
        if idx: ct[2][idx[0]] += 20
        else: t[2].append(b'entity'); nm[2].append(b'logic_branch'); ct[2].append(20)

m.save(path)
chk = vmapedit.Map(path)
names = {chk.name(e): e for e in chk.entities()}
print('20 fire_lit branches added; cases, buttons and fireoff rewired')
for n in ('firecase2', 'fire15brush', 'fire_lit15'):
    print(n + ':'); [print('  ', chk.conn_tuple(c)) for c in chk.conns(names[n]) if n != 'firecase2' or chk.conn_tuple(c)[0] == 'OnCase05']
