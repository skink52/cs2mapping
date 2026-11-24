"""mem_soak.py: measure the LOCAL test server's memory on an IRONFRAME map against de_dust2, GOTV on, with player churn.

Made 23 Nov 2026 after the live JB box's cs2 was OOM-killed 2 min after loading mg_ironframe_dunes (21 h up, 12 GiB RSS,
HLTVServerAsync made the last allocation). It answers: does an IRONFRAME map spike the server's memory, and does memory climb
from one map visit to the next (a leak that survives map changes)?

Phases: de_dust2 baseline, the map, de_dust2, the map, de_dust2 (each map visit with tv_enable 1, tv_delay 30 and bot churn:
bot_quota swings 8 <-> 12 every 15 s, i.e. bots connecting and leaving the whole time). A sample every 5 s of the cs2 server's
private bytes and working set; one progress line per sample; a CSV and a JSON summary in logs/.

usage:  python -I tools/mem_soak.py [--map mg_ironframe_dunes] [--visit 300] [--base 90] [--tv 1] [--delay 30] [--restart-every 0] [--no-script] [--off hud,render,...] [--cvars file]
Needs the map on the local server first (tools/server_copy.py copy <map>). Restarts C:\\cs2server; holds its lock.
"""
import csv, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, r'C:\source1\slime-mg-gm\tests')
import harness as h  # noqa: E402
import subprocess  # noqa: E402

# RCON reads server/local.cfg; the server's own copy (cfg/slime_local.cfg) can be edited after deploy (it was on 19 Nov 2026),
# and that is the password the running server uses
_SRV_CFG = os.path.join(h.CSGO, 'cfg', 'slime_local.cfg')
if os.path.exists(_SRV_CFG): h.rcon.LOCAL_CFG = _SRV_CFG

OWNER = 'ironframe_mem_soak'


def opt(flag, default):
    return type(default)(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


MAP = opt('--map', 'mg_ironframe_dunes')
VISIT = opt('--visit', 300)
BASE = opt('--base', 90)
DELAY = opt('--delay', 30)   # tv_delay: GOTV holds this many seconds of snapshots
RESTART = opt('--restart-every', 0)   # >0: mp_restartgame 1 every this many seconds of a map visit (round restarts)
CVARS = [l.strip() for l in open(opt('--cvars', ''), encoding='utf-8') if l.strip()] if '--cvars' in sys.argv else []   # sent after each map load (e.g. a map's game cvars on a stock map)
OFF = [x for x in opt('--off', '').split(',') if x]   # script parts to switch off after each load (CONFIG.SOAK_SWITCHES builds)
NOSCRIPT = '--no-script' in sys.argv   # remove the map's point_script right after load (map entities only)
TV = opt('--tv', 1)   # 0: GOTV off, to split the engine's broadcast buffers from the map's own growth
STAMP = time.strftime('%Y%m%d_%H%M%S')
CSV = os.path.join(PROJ, 'logs', f'mem_soak_{STAMP}_{MAP}_tv{TV}_d{DELAY}_r{RESTART}{"_noscript" if NOSCRIPT else ""}{"_off-" + "-".join(OFF) if OFF else ""}{"_cvars" if CVARS else ""}.csv')
SUMMARY = CSV[:-4] + '.json'

phase = {'name': 'boot'}
rows, stop = [], threading.Event()
t0 = time.time()


PS = ("Get-Process cs2 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '%s\\*' } | "
      "ForEach-Object { '{0} {1} {2}' -f $_.PrivateMemorySize64, $_.WorkingSet64, $_.TotalProcessorTime.TotalSeconds }"
      ) % h.setup.SERVER_DIR


def sampler():
    """psutil is not in the isolated (-I) interpreter's site-packages: the server's counters come from PowerShell."""
    last = None
    while not stop.is_set():
        out = subprocess.run(['powershell', '-NoProfile', '-Command', PS], capture_output=True, text=True).stdout.split()
        if len(out) >= 3:
            now = time.time(); cpu_s = float(out[2])
            cpu = 0 if last is None else 100 * (cpu_s - last[1]) / max(0.1, now - last[0]); last = (now, cpu_s)
            r = {'t': round(now - t0, 1), 'phase': phase['name'], 'private_mib': int(out[0]) // 2**20,
                 'wset_mib': int(out[1]) // 2**20, 'cpu': round(cpu)}
            rows.append(r)
            print(f"[{r['t']:7.1f} s] {r['phase']:<22} private {r['private_mib']:6d} MiB  wset {r['wset_mib']:6d} MiB  "
                  f"cpu {r['cpu']:5d} %", flush=True)
        else:
            last = None
        stop.wait(5)


def hold(name, seconds, churn=False):
    phase['name'] = name
    end = time.time() + seconds; hi = True; nxt = time.time() + RESTART
    while time.time() < end:
        if churn:
            h.cmd(f'bot_quota {12 if hi else 8}'); hi = not hi
        if churn and RESTART and time.time() >= nxt:
            h.cmd('mp_restartgame 1'); nxt = time.time() + RESTART; print(f'[{time.time() - t0:7.1f} s] mp_restartgame', flush=True)
        time.sleep(min(15, max(0, end - time.time())))


def visit(_m, name, map_name, seconds, churn):
    phase['name'] = name + ' load'
    m = h.Mark()
    try: h.change_level(m, map_name, timeout=120)
    except h.Fail:   # a lost RCON packet: send it once more
        m = h.Mark(); h.change_level(m, map_name, timeout=180)
    if churn and CVARS: h.cmd(*CVARS); print(f'cvars: {len(CVARS)} sent', flush=True)
    if churn and OFF:
        time.sleep(3); h.cmd(*('slime_probe io ifr_script RunScriptInput ifr_dbg_off_' + x for x in OFF))   # ent_fire from RCON reaches no entity on CS2 (24 Nov 2026); print('switched off: ' + ','.join(OFF), flush=True)
    if churn and NOSCRIPT: h.cmd('sv_cheats 1', 'ent_fire ifr_script kill'); print('script removed', flush=True)
    if churn: h.cmd('bot_quota_mode normal', 'bot_quota 12')
    hold(name, seconds, churn)
    return m


def summarise():
    out = {}
    for r in rows:
        p = out.setdefault(r['phase'], {'n': 0, 'private_first': r['private_mib'], 'private_max': 0, 'wset_max': 0})
        p['n'] += 1; p['private_last'] = r['private_mib']
        p['private_max'] = max(p['private_max'], r['private_mib']); p['wset_max'] = max(p['wset_max'], r['wset_mib'])
    return out


def main():
    h.take_lock(OWNER, f'mem_soak {MAP}')
    th = threading.Thread(target=sampler, daemon=True)
    try:
        print(f'restarting the local server (de_dust2); then {BASE} s base / {VISIT} s {MAP} x2', flush=True)
        mb = h.restart()
        h.wait_ready(mb, 'de_dust2', 180)   # RCON commands sent while the boot map loads are lost (23 Nov 2026)
        th.start()
        h.cmd(f'tv_enable {TV}', f'tv_delay {DELAY}', 'bot_quota 0')   # tv_enable takes effect at the next map load
        visit(None, 'dust2 base 1', 'de_dust2', BASE, False)
        visit(None, 'map visit 1', MAP, VISIT, True)
        h.cmd('bot_quota 0'); visit(None, 'dust2 base 2', 'de_dust2', BASE, False)
        visit(None, 'map visit 2', MAP, VISIT, True)
        h.cmd('bot_quota 0'); visit(None, 'dust2 base 3', 'de_dust2', BASE, False)
    finally:
        stop.set()
        if th.is_alive(): th.join(10)
        h.cmd('bot_quota 0')
        h.drop_lock(OWNER)
        with open(CSV, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['t', 'phase', 'private_mib', 'wset_mib', 'cpu']); w.writeheader(); w.writerows(rows)
        s = summarise()
        json.dump({'map': MAP, 'tv': TV, 'delay': DELAY, 'restart_every': RESTART, 'off': OFF, 'visit_s': VISIT, 'base_s': BASE, 'phases': s}, open(SUMMARY, 'w'), indent=1)
        print('\nphase                    private first/last/max MiB   wset max MiB')
        for k, p in s.items():
            print(f"{k:<24} {p['private_first']:6d} {p['private_last']:6d} {p['private_max']:6d}       {p['wset_max']:6d}")
        print(f'csv {CSV}\nsummary {SUMMARY}', flush=True)


if __name__ == '__main__':
    main()
