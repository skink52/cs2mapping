"""Mock run of ba_jail_keimusho's fire game I/O, read straight from the .vmap (every entity and output, not a copy of the wiring).

  python mock_firegame_io.py <ba_jail_keimusho.vmap> [games=200] [seed=1] [--shuffle]
  --shuffle: outputs due at the same moment run in random order (CS2 doesn't promise their order)

An event queue runs the map's own outputs (delays, times-to-fire) through models of the entities involved: func_button (Lock/Unlock,
spawnflag 2048 starts locked), logic_timer (Enable: first OnTimer after RefireTime), logic_relay, logic_case (PickRandom over the
cases with outputs), logic_branch, trigger_hurt (Enable/Disable), info_particle_system (Start/Stop), the sweep script
(Sweep_/Unsweep_<trigger>), func_brush and point_servercommand. Inputs it doesn't model are reported.

Players: one team per half. When a fire is burning and its button is unlocked, the team presses it after a reaction time
(fast team 0.2-2 s, slow team 0.5-12 s, swapped every other game). Only visible fires get pressed. Each game runs fireon,
plays 3-6 minutes, presses fireoff, then runs 10 s more. Plus scripted races: a burning fire re-picked, then put out
0.05..1.95 s later.

Checked every 0.05 s, per fire N: firehurtN enabled or its sweep active while fireN isn't burning (damage with no fire),
fireNbrush unlocked while fireN isn't burning (invisible usable button); after fireoff + 3 s: anything still on.
"""
import heapq, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import vmapedit  # noqa: E402

DT = 0.05
SETTLE = 0.2   # a mismatch must clear within this (a press in the very tick of the 2 s test is settled by the button's 0.15 s Test)
SHUFFLE = False


class World:
    def __init__(s, m, rng):
        s.rng, s.t, s.q, s.seq = rng, 0.0, [], 0
        s.ents = {}      # name -> [ {cls, keys, outs, state} ]
        s.unknown = {}
        for e in m.entities():
            n = m.name(e)
            if not n: continue
            keys = {a[0].decode(): a[2].decode('utf-8', 'replace') for a in m.props(e)['attrs'] if isinstance(a[2], bytes)}
            outs = [list(m.conn_tuple(c)) for c in m.conns(e)]
            ent = {'name': n, 'cls': m.cls(e), 'keys': keys, 'outs': outs}
            s.reset_state(ent)
            s.ents.setdefault(n, []).append(ent)
        s.sweeps = set()
        s.log = []

    def reset_state(s, ent):
        k, c = ent['keys'], ent['cls']
        sf = int(k.get('spawnflags', '0') or 0)
        ent['locked'] = c == 'func_button' and bool(sf & 2048)
        ent['enabled'] = k.get('StartDisabled', '0') != '1'
        ent['on'] = c == 'info_particle_system' and k.get('start_active', '0') == '1'
        ent['value'] = k.get('InitialValue', '0') == '1'
        ent['timer_next'] = None

    def fire(s, ent, output, param_override=None):
        for o in ent['outs']:
            if o[0] != output: continue
            if o[5] == 0: continue
            if o[5] > 0: o[5] -= 1
            s.push(s.t + o[4], o[1], o[2], o[3], id(ent))

    def push(s, t, target, inp, param, src=None):
        # same-time outputs: in order sent, or (SHUFFLE) in random order - CS2 doesn't promise an order
        s.seq += 1
        heapq.heappush(s.q, (round(t, 6), s.rng.random() if SHUFFLE else s.seq, target, inp, param, src))

    def deliver(s, target, inp, param):
        if target == 'sweepscript' and inp == 'RunScriptInput':
            nm = param.split('_', 1)
            if nm[0] == 'Sweep': s.sweeps.add(nm[1])
            elif nm[0] == 'Unsweep': s.sweeps.discard(nm[1])
            return
        for ent in s.ents.get(target, []):
            c = ent['cls']
            key = (c, inp)
            if c == 'func_button':
                if inp == 'Lock': ent['locked'] = True
                elif inp == 'Unlock': ent['locked'] = False
                elif inp == 'Press': s.press(ent)
                else: s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c in ('trigger_hurt', 'func_brush', 'trigger_teleport'):
                if inp == 'Enable': ent['enabled'] = True
                elif inp == 'Disable': ent['enabled'] = False
                elif inp == 'Toggle': ent['enabled'] = not ent['enabled']
                else: s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c == 'info_particle_system':
                if inp == 'Start': ent['on'] = True
                elif inp in ('Stop', 'DestroyImmediately', 'StopPlayEndCap'): ent['on'] = False
                else: s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c == 'logic_timer':
                rt = float(ent['keys'].get('RefireTime', '0') or 0)
                if inp == 'Enable':
                    if not ent['enabled'] or ent['timer_next'] is None: ent['timer_next'] = s.t + max(rt, 0.01)
                    ent['enabled'] = True
                elif inp == 'Disable': ent['enabled'] = False; ent['timer_next'] = None
                elif inp == 'RefireTime': ent['keys']['RefireTime'] = param or '0'
                else: s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c == 'logic_relay':
                if inp == 'Trigger' and ent['enabled']: s.fire(ent, 'OnTrigger')
                elif inp == 'Enable': ent['enabled'] = True
                elif inp == 'Disable': ent['enabled'] = False
                elif inp == 'CancelPending': s.q = [x for x in s.q if x[5] != id(ent)]; heapq.heapify(s.q)
                elif inp != 'Trigger': s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c == 'logic_case':
                if inp == 'PickRandom':
                    cases = sorted({o[0] for o in ent['outs'] if o[0].startswith('OnCase')})
                    if cases: s.fire(ent, s.rng.choice(cases))
                else: s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c == 'logic_branch':
                if inp == 'SetValue': ent['value'] = param.strip() not in ('', '0')
                elif inp == 'SetValueTest': ent['value'] = param.strip() not in ('', '0'); s.fire(ent, 'OnTrue' if ent['value'] else 'OnFalse')
                elif inp == 'Test': s.fire(ent, 'OnTrue' if ent['value'] else 'OnFalse')
                elif inp == 'Toggle': ent['value'] = not ent['value']
                else: s.unknown[key] = s.unknown.get(key, 0) + 1
            elif c == 'point_servercommand':
                pass
            else:
                s.unknown[key] = s.unknown.get(key, 0) + 1

    def press(s, ent):
        if ent['locked']: return False
        s.fire(ent, 'OnPressed'); return True

    def press_name(s, name):
        return any(s.press(e) for e in s.ents.get(name, []))

    def step_to(s, t_end):
        while True:
            nxt_timer = min([e['timer_next'] for es in s.ents.values() for e in es if e['cls'] == 'logic_timer' and e['timer_next'] is not None] or [1e18])
            nxt_q = s.q[0][0] if s.q else 1e18
            nxt = min(nxt_timer, nxt_q)
            if nxt > t_end: s.t = t_end; return
            s.t = nxt
            if nxt_q <= nxt_timer:
                _, _, tg, inp, prm, _src = heapq.heappop(s.q)
                s.deliver(tg, inp, prm)
            else:
                for es in s.ents.values():
                    for e in es:
                        if e['cls'] == 'logic_timer' and e['timer_next'] == nxt:
                            e['timer_next'] = nxt + max(float(e['keys'].get('RefireTime', '0') or 0), 0.01)
                            s.fire(e, 'OnTimer')

    # state helpers
    def one(s, n): return s.ents[n][0]
    def burning(s, i): return s.one('fire%d' % i)['on']
    def hurting(s, i): return s.one('firehurt%d' % i)['enabled'] or ('firehurt%d' % i) in s.sweeps
    def unlocked(s, i): return not s.one('fire%dbrush' % i)['locked']


class Stats:
    def __init__(s):
        s.ghost_hurt = 0.0; s.ghost_hurt_events = 0; s.ghost_btn = 0.0; s.after_stop = []; s.longest = 0.0
        s.presses = 0; s.lit = 0; s.max_burning = 0; s.stuck = 0.0; s.longest_btn = 0.0


def check(w, st, prev, run):
    for i in range(1, 21):
        g = w.hurting(i) and not w.burning(i)
        if g:
            st.ghost_hurt += DT
            run[i] = run.get(i, 0.0) + DT
            st.longest = max(st.longest, run[i])
            if not prev.get(i): st.ghost_hurt_events += 1
        else:
            run[i] = 0.0
        prev[i] = g
        if w.unlocked(i) and not w.burning(i): st.ghost_btn += DT
        kb = ('btn', i)
        run[kb] = run.get(kb, 0.0) + DT if (w.unlocked(i) and not w.burning(i)) else 0.0
        st.longest_btn = max(st.longest_btn, run[kb])
        k = ('stuck', i)
        run[k] = run.get(k, 0.0) + DT if (w.burning(i) and not w.unlocked(i)) else 0.0
        st.stuck = max(st.stuck, run[k])


def play_game(m, rng, st, slow_half, length):
    w = World(m, rng)
    lo_hi = {1: (0.2, 2.0), 2: (0.2, 2.0)}
    lo_hi[slow_half] = (0.5, 12.0)
    due = {}                     # fire -> press time
    prev, run = {}, {}
    w.press_name('fireon')
    t = 0.0
    stop_at = length
    stopped = False
    while t < stop_at + 10.0:
        t += DT
        w.step_to(t)
        if not stopped and t >= stop_at:
            # fireoff is unlocked 5 s after fireon; press until it takes
            if w.press_name('fireoff'): stopped = True; stop_t = t
            else: stop_at += DT
        for i in range(1, 21):
            if w.burning(i) and w.unlocked(i):
                if i not in due:
                    half = 1 if i <= 10 else 2
                    due[i] = t + rng.uniform(*lo_hi[half])
                elif t >= due[i]:
                    if w.press_name('fire%dbrush' % i): st.presses += 1
                    del due[i]
            else:
                due.pop(i, None)
        st.max_burning = max(st.max_burning, sum(w.burning(i) for i in range(1, 21)))
        check(w, st, prev, run)
        if stopped and t >= stop_t + 3.0:
            left = [n for i in range(1, 21) for n, on in (('firehurt%d' % i, w.hurting(i)), ('fire%d' % i, w.burning(i)), ('fire%dbrush' % i, w.unlocked(i))) if on]
            tm = w.one('firetimer')
            if tm['enabled']: left.append('firetimer')
            if left: st.after_stop.append(left)
    return w


def race(m, rng, gap):
    """fire N burning with its button unlocked; the case picks N again at T; the team puts it out at T + gap"""
    w = World(m, rng)
    case, n = ('firecase2', 15)
    out = [o for o in w.one(case)['outs'] if o[2] in ('Enable', 'Start', 'Unlock', 'RunScriptInput', 'SetValue', 'Test', 'SetValueTest', 'Trigger')]
    caseN = 'OnCase%02d' % (n - 10)
    w.fire(w.one(case), caseN); w.step_to(3.0)                      # first pick: lit, unlocked at 2 s
    assert w.burning(n) and w.unlocked(n), 'setup failed'
    T = 10.0
    w.step_to(T); w.fire(w.one(case), caseN)                         # re-pick while burning
    w.push(T + gap, 'fire%dbrush' % n, 'Press', '')                  # queued, so it shares its tick with any output due then
    worst, t = 0.0, T + gap
    ghost = 0.0
    while t < T + gap + 6.0:
        t += DT / 5; w.step_to(t)
        if w.hurting(n) and not w.burning(n): ghost += DT / 5
    end = (w.hurting(n), w.burning(n), w.unlocked(n))
    return ghost, end


def main():
    path = sys.argv[1]
    global SHUFFLE
    SHUFFLE = '--shuffle' in sys.argv
    sys.argv = [a for a in sys.argv if a != '--shuffle']
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    m = vmapedit.Map(path)
    rng = random.Random(seed)
    st = Stats()
    unknown = {}
    for g in range(games):
        w = play_game(m, rng, st, 1 + g % 2, rng.uniform(180, 360))
        for k, v in w.unknown.items(): unknown[k] = unknown.get(k, 0) + v
    print('map: %s' % path)
    print('%d games, %d button presses, up to %d fires burning at once' % (games, st.presses, st.max_burning))
    print('damage with no fire:       %.1f s total, %d times, longest %.2f s' % (st.ghost_hurt, st.ghost_hurt_events, st.longest))
    print('usable button with no fire: %.1f s total, longest %.2f s' % (st.ghost_btn, st.longest_btn))
    print('longest a fire burned with its button locked: %.2f s (2.0 s expected: the button unlocks 2 s after a pick)' % st.stuck)
    print('still on 3 s after fireoff: %d games%s' % (len(st.after_stop), (' e.g. ' + ', '.join(st.after_stop[0][:8])) if st.after_stop else ''))
    print('race (burning fire15 re-picked at T, put out at T+gap):')
    bad = 0
    tries = 50 if SHUFFLE else 1
    for gap in (0.05, 0.1, 0.5, 1.0, 1.5, 1.9, 1.95, 2.0, 2.05, 3.0):
        fails, worst, ends = 0, 0.0, set()
        for k in range(tries):
            ghost, end = race(m, random.Random(k), gap)
            ok = ghost <= SETTLE and end[0] == end[1] and (end[1] or not end[2])   # no fire-less hurt or button; relit = all on
            fails += not ok; worst = max(worst, ghost); ends.add(end)
        bad += fails
        print('   gap %.2f s: damage with no fire up to %.2f s; 6 s later (hurt, fire, button unlocked) %s  %s' % (
            gap, worst, ' / '.join(str(e) for e in sorted(ends)), 'OK' if not fails else 'FAIL %d/%d' % (fails, tries)))
    if unknown: print('inputs not modelled:', unknown)
    print('pass rule: every mismatch clears within %.2f s; end states consistent; nothing on after fireoff' % SETTLE)
    ok = st.stuck <= 2.2 and st.longest <= SETTLE and st.longest_btn <= SETTLE and not st.after_stop and not bad
    print('RESULT:', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
