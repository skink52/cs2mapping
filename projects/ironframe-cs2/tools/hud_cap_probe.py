"""hud_cap_probe.py: find the custom HUD limit that crashed the live JB box (Space Racer 20 + 24 Nov, IRONFRAME Dunes 24 Nov 2026:
CCSCustomHudLayout m_vecPanelIds / m_vecClassNames overflow in PackEntity, segfault).

The layout (s2v.app schema) has two shared string tables (m_vecPanelIds, m_vecClassNames: every id / class name used this map, never
removed), one state per player (m_vecPlayerLayoutStates: the player's switched-on classes and dialog-variable texts, sent to that player
and its spectators) and a global state. The overflow may be a table's size, or the whole entity's packed size (Source's classic limit
for one entity is 16 KB) reached while writing the field after the per-player states. Bots and GOTV alone never overflowed locally, so
a real player has to be connected.

Needs a Dunes build with CONFIG.SOAK_SWITCHES on (src/cs2/90_main.js "HUD cap probe"). Each variant: restart the LOCAL server on Dunes,
GOTV on, no bots; wait (up to 20 min) for a player to join and pick a team; then a flood step every --gap s until the console shows an
overflow / PackEntity line or the server dies; the last logged total is the answer. Variants:
  humans  64 more switched-on classes a step on the human player(s), few distinct names     -> per-player class entries
  vars    32 more 48-character dialog texts a step on the human player(s)                    -> per-player dialog text bytes
  long    128 more distinct 48-character class names a step                                  -> class-name table bytes
  uniq    512 more distinct short class names a step                                         -> class-name table count
  (plain) / gotv / gotvmany: the older bot / GOTV floods

usage:  python -I tools/hud_cap_probe.py [--variant humans] [--variants humans,vars,long] [--steps 60] [--gap 3]
"""
import os, re, sys, time

sys.path.insert(0, r'C:\source1\slime-mg-gm\tests')
import harness as h  # noqa: E402

_SRV_CFG = os.path.join(h.CSGO, 'cfg', 'slime_local.cfg')
if os.path.exists(_SRV_CFG): h.rcon.LOCAL_CFG = _SRV_CFG
OWNER = 'ironframe_hud_cap_probe'
ARG = lambda f, d: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d
STEPS = int(ARG('--steps', 60))
GAP = float(ARG('--gap', 3))
VARIANTS = [v for v in ARG('--variants', ARG('--variant', '')).split(',')] if ('--variants' in sys.argv or '--variant' in sys.argv) else ['']
BAD = re.compile(r'overflow|PackEntity|m_vecClassNames|m_vecPanelIds|maximum number', re.I)


def wait_player():
    print('WAITING for a player: connect to this PC on port 27015 (LAN IP:27015 or localhost:27015), pick a team, stay in the map', flush=True)
    t_end = time.time() + 1200
    while time.time() < t_end:
        try: st = h.probe_state(15)
        except h.Fail: st = {'humans': 0}
        if st.get('humans', 0) >= 1: print(f"player in: {st['humans']} human(s)", flush=True); return True
        time.sleep(5)
    print('no player joined in 20 min', flush=True); return False


def run(variant):
    name = 'ifr_dbg_hudflood' + ('_' + variant if variant else '')
    print(f'==== variant {variant or "plain"} ({name})', flush=True)
    mb = h.restart(); h.wait_ready(mb, 'de_dust2', 180)
    h.cmd('tv_enable 1', 'tv_delay 0', 'bot_quota 0')
    m = h.Mark(); h.change_level(m, 'mg_ironframe_dunes', timeout=180)
    if variant in ('humans', 'vars', 'long', 'uniq'):
        h.cmd('bot_kick', 'bot_quota 0')
        if not wait_player(): return 'no player'
        time.sleep(25)   # the player's own HUD comes up first (it counts too)
    else:
        h.cmd('bot_quota_mode normal', 'bot_quota 40'); time.sleep(20)
    con = h.Mark(); last = '?'
    for i in range(STEPS):
        if not h.setup.running(): return f'SERVER GONE after step {i}: last "{last}"'
        h.cmd('slime_probe io ifr_script RunScriptInput ' + name)
        time.sleep(GAP)
        text = con.console()
        fl = re.findall(r'hud flood: (.*)', text)
        if fl: last = fl[-1].strip()
        print(f'step {i + 1}: {last}', flush=True)
        bad = [l for l in text.splitlines() if BAD.search(l)]
        if bad:
            print('ENGINE: ' + '\n        '.join(x[:220] for x in bad[:6]), flush=True)
            time.sleep(5)
            return f'engine message at step {i + 1} ("{last}"), server ' + ('running' if h.setup.running() else 'GONE')
    return f'no overflow in {STEPS} steps ("{last}")'


def main():
    h.take_lock(OWNER, 'hud cap probe')
    results = []
    try:
        for v in VARIANTS:
            r = run(v); results.append((v or 'plain', r)); print(f'RESULT {v or "plain"}: {r}', flush=True)
    finally:
        h.drop_lock(OWNER)
        print('\nSUMMARY')
        for v, r in results: print(f'  {v}: {r}')


if __name__ == '__main__':
    main()
