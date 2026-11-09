"""env_global + logic_auto "Global State to Read" -> io script (stage D `envglobal` pass).

CS2 has no env_global, so a logic_auto that reads a global state never fires. CS:GO maps use the pair for state that outlives a
round (mg_arcs_multigames, 9 Nov 2026: 43 globals give each mini-game a 3-round cooldown; the game's relay turns global_<game>_1 on,
and next round that global's logic_auto locks the game's button and hands on to global_<game>_2, ...). The io script keeps the
states instead, since script state survives a round restart while map entities respawn:

- env_global TurnOn / TurnOff / Toggle / Remove -> RunScriptInput Global_<On|Off|Toggle>_<n> (n = index of the global state name);
  initial state from "Initial State" when the "Set Initial State" flag (1) is on. The env_globals are removed.
- each logic_auto with a globalstate (other than is_pc, which stage C clears) becomes a logic_relay `port_globalauto_<k>`; its
  OnMapSpawn / OnNewGame / OnMultiNewMap / OnMultiNewRound outputs become OnTrigger. At every round start the script triggers the
  relays whose state is on (0.1 s in, once the round's entities exist), which is when CS:GO's logic_auto fired.
SetCounter / AddToCounter / GetCounter (counter globals) are listed, not converted.
"""
import json, re
import dmx

HEAD_LINE = '//   Global_<On|Off|Toggle>_<n> replaces env_global (states kept across rounds; logic_autos reading them -> port_globalauto_<k>)'
AUTO_OUTS = ('onmapspawn', 'onnewgame', 'onmultinewmap', 'onmultinewround')
JS = r'''// ---------------------------------------------------------------- env_global replacement (not in CS2)
// Global states live here, so they survive a round restart like CS:GO's env_global. Each logic_auto that read one is now a
// logic_relay; at round start the script triggers the ones whose state is on.
const GLOBAL_NAMES = __NAMES__;
const GLOBAL_ON = new Set(__INITIAL__);
/** @type {[string, number][]} relay name, global index */
const GLOBAL_AUTOS = __AUTOS__;
GLOBAL_NAMES.forEach((_, i) => {
    Instance.OnScriptInput("Global_On_" + i, () => { GLOBAL_ON.add(i); });
    Instance.OnScriptInput("Global_Off_" + i, () => { GLOBAL_ON.delete(i); });
    Instance.OnScriptInput("Global_Toggle_" + i, () => { if (GLOBAL_ON.has(i)) GLOBAL_ON.delete(i); else GLOBAL_ON.add(i); });
});
Instance.OnRoundStart(() => {
    const on = GLOBAL_AUTOS.filter(([, i]) => GLOBAL_ON.has(i)).map(([relay]) => relay);   // states as the round began
    for (const relay of on) Instance.EntFireAtName({ name: relay, input: "Trigger", delay: 0.1 });
});'''

def run(m, c):
    c.globals = None
    gl = m.by_class('env_global')
    autos = [e for e in m.by_class('logic_auto') if (m.P(e, 'globalstate', '') or '').strip() and (m.P(e, 'globalstate') or '').strip().lower() != 'is_pc']
    if not gl and not autos: return
    names = []
    def idx(state):
        s = state.strip()
        if s.lower() not in [x.lower() for x in names]: names.append(s)
        return [x.lower() for x in names].index(s.lower())
    initial = set(); byname = {}
    for e in gl:
        i = idx(m.P(e, 'globalstate', '') or m.name(e) or 'global_%d' % e)
        try: sf = int(float(m.P(e, 'spawnflags', '0') or 0))
        except ValueError: sf = 0
        if sf & 1 and (m.P(e, 'initialstate', '0') or '0').strip() == '1': initial.add(i)
        if m.name(e): byname.setdefault(m.name(e).lower(), i)
    n = 0; counters = []
    for src, cc in list(m.all_conns()):
        t = dmx.get(cc, b'targetName').decode().lower(); inp = dmx.get(cc, b'inputName').decode().lower()
        if t not in byname: continue
        op = {'turnon': 'On', 'turnoff': 'Off', 'toggle': 'Toggle', 'remove': 'Off'}.get(inp)
        if not op: counters.append('%s.%s' % (t, inp)); continue
        dmx.set_(cc, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
        dmx.set_(cc, b'overrideParam', dmx.T_STR, ('Global_%s_%d' % (op, byname[t])).encode()); n += 1
    for e in gl: m.remove_node(e)
    relays = []
    for k, e in enumerate(autos):
        i = idx(m.P(e, 'globalstate'))
        name = 'port_globalauto_%d' % k
        m.setp(e, 'classname', 'logic_relay'); m.delp(e, 'globalstate'); m.setp(e, 'targetname', name); m.setp(e, 'spawnflags', '0')
        for cc in m.conns(e):
            if dmx.get(cc, b'outputName').decode().lower() in AUTO_OUTS: dmx.set_(cc, b'outputName', dmx.T_STR, b'OnTrigger')
        relays.append([name, i])
    c.globals = {'names': names, 'initial': sorted(initial), 'autos': relays}
    c.log.append('envglobal: removed %d env_global (not in CS2); %d TurnOn/TurnOff/Toggle -> script Global_<op>_<n>; %d logic_autos reading a global state -> '
                 'logic_relays port_globalauto_<k> the script triggers at round start while the state is on (%d states)' % (len(gl), n, len(autos), len(names)))
    c.todo.append('envglobal: check the global-state logic over a few rounds in game (states kept by the io script across round restarts)')
    if counters: c.todo.append('envglobal: counter inputs on env_global not converted: %s' % ', '.join(sorted(set(counters))))


def patch_script(js, g):
    if not js.startswith('import'):
        js = 'import { Instance } from "cs_script/point_script";\n\n' + js
    js = re.sub(r'\n// -{10,} env_global replacement.*?\n\}\);(?=\n|$)', '', js, flags=re.S)
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if HEAD_LINE not in lines and last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    body = JS.replace('__NAMES__', json.dumps(g['names'])).replace('__INITIAL__', json.dumps(g['initial'])).replace('__AUTOS__', json.dumps(g['autos']))
    return '\n'.join(lines) + '\n\n' + body + '\n'
