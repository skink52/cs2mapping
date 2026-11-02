"""Nanite Temple sounds: synthesised (no samples) with create/synth primitives, written as 16-bit mono 44.1 kHz wavs, plus the sound
events (create/sndevents) merged into the addon's soundevents_addon.vsndevts.

  SFX (3D, one base curve: full to 200 u, silent at 1600 u): dash, aegis_up, aegis_down, rewind_arm, rewind_snap, sentinel_charge, sentinel_shot,
      bolt_launch, bolt_hit, drone_lunge, golem_slam, enemy_hit, enemy_die, vault_clear, teleport, kiosk
  UI (flat, everyone): temple_open, breach, ring_warn, win, lose
  Ambience loops (3D, long range, one point_soundevent per area, start on spawn): amb_vault, amb_lobby, amb_staging, amb_arena, beacon_loop

usage: sounds.py <addon_out> [--soundevents <live soundevents_addon.vsndevts>]   -> sounds/nt/*.wav, soundevents/soundevents_addon.vsndevts, _gen/sounds.json
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE)
import numpy as np
import synth as S, chiptune as C, sndevents as E

OUT = sys.argv[1]
TEMPLATE = sys.argv[sys.argv.index('--soundevents') + 1] if '--soundevents' in sys.argv else r'C:\source1\cs2port\tools\addon_template\content\soundevents\soundevents_addon.vsndevts'
SND_DIR = os.path.join(OUT, 'sounds', 'nt'); os.makedirs(SND_DIR, exist_ok=True)
C.SR = S.SR
SR = S.SR
rng = np.random.default_rng(11)
IR = S.reverb_ir(seed=3, length=1.1, predelay=0.015)
IR_LONG = S.reverb_ir(seed=5, length=2.4, predelay=0.03)


def n_of(t): return int(round(SR * t))
def t_of(n): return np.arange(n) / SR
def lin(a, b, n): return np.linspace(a, b, n)
def expo(a, b, n): return a * (b / a) ** lin(0, 1, n)
def fit(x, n):
    if len(x) >= n: return x[:n]
    return np.concatenate([x, np.zeros(n - len(x))])
def mix(*parts):
    n = max(len(p) for p in parts); out = np.zeros(n)
    for p in parts: out[:len(p)] += p
    return out
def finish(x, gain=0.9, verb=0.18, ir=None, hp=60):
    """high-pass, a touch of (mono) reverb with room for its tail, normalise, soft clip"""
    x = S.hp(np.concatenate([x, np.zeros(n_of(0.35 if ir is None else 0.8))]), hp)
    if verb > 0:
        wet = S.reverb(np.stack([x, x], 1), IR if ir is None else ir)[:, 0]
        x = x * (1 - verb) + wet * verb
    return S.softclip(x / (np.max(np.abs(x)) + 1e-9) * gain)
def tail(x, t): return np.concatenate([x, np.zeros(n_of(t))])


# ---------------------------------------------------------------- SFX
def sfx_dash():
    n = n_of(0.42)
    whoosh = S.bp(S.noise(n, rng), 600, 4000) * S.env_adsr(0.25, a=0.01, d=0.1, s=0.5, r=0.12, n=n)
    chirp = S.sine(expo(300, 2400, n), n) * S.env_exp(n, 0.08) * 0.5
    shimmer = S.sine(expo(1800, 3600, n), n) * S.env_adsr(0.2, a=0.05, d=0.1, s=0.3, r=0.1, n=n) * 0.2
    return finish(mix(whoosh, chirp, shimmer), verb=0.25)

def sfx_aegis_up():
    n = n_of(0.75)
    f = expo(90, 180, n)
    hum = (S.saw(f, n) * 0.4 + S.sine(f * 2, n) * 0.5 + S.sine(f * 3.01, n) * 0.2) * S.env_adsr(0.55, a=0.12, d=0.1, s=0.9, r=0.15, n=n)
    sweep = S.lp(S.noise(n, rng), 1500) * S.env_adsr(0.3, a=0.2, d=0.1, s=0.2, r=0.2, n=n) * 0.35
    bell = S.sine(np.full(n, 880.0), n) * S.env_exp(n, 0.25, hold=0.3) * 0.25
    return finish(mix(S.lp(hum, 2500), sweep, bell), verb=0.3)

def sfx_aegis_down():
    n = n_of(0.6)
    f = expo(180, 70, n)
    hum = (S.saw(f, n) * 0.4 + S.sine(f * 2, n) * 0.5) * S.env_adsr(0.4, a=0.01, d=0.1, s=0.8, r=0.15, n=n)
    return finish(S.lp(hum, 1800), verb=0.3)

def sfx_rewind_arm():
    n = n_of(0.5)
    parts = []
    for i, fr in enumerate((440, 587, 740, 988)):
        seg = n_of(0.11); x = np.zeros(n); start = int(i * n_of(0.09))
        tone = S.pulse(np.full(seg, float(fr)), seg, 0.3) * S.env_exp(seg, 0.05)
        x[start:start + seg] = tone[:max(0, min(seg, n - start))]; parts.append(x * 0.4)
    tick = S.hp(S.noise(n, rng), 5000) * S.env_exp(n, 0.02) * 0.3
    return finish(mix(*parts, tick), verb=0.2)

def sfx_rewind_snap():
    n = n_of(0.9)
    f = np.concatenate([expo(1200, 150, n // 2), expo(150, 2600, n - n // 2)])
    sweep = S.saw(f, n) * S.env_adsr(0.7, a=0.01, d=0.2, s=0.7, r=0.15, n=n) * 0.5
    grain = S.bp(S.noise(n, rng), 300, 3000) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 28 * t_of(n)))) * S.env_adsr(0.6, a=0.02, d=0.1, s=0.6, r=0.2, n=n) * 0.4
    return finish(mix(S.lp(sweep, 4000), grain), verb=0.35, ir=IR_LONG)

def sfx_sentinel_charge():
    n = n_of(0.65)
    f = expo(180, 1100, n)
    tone = (S.pulse(f, n, 0.2) * 0.5 + S.sine(f * 2, n) * 0.3) * S.env_adsr(0.6, a=0.03, d=0.05, s=1.0, r=0.03, n=n)
    buzz = S.bp(S.noise(n, rng), 2000, 6000) * lin(0, 0.4, n)
    return finish(mix(S.lp(tone, 5000), buzz), verb=0.15)

def sfx_sentinel_shot():
    n = n_of(0.32)
    zap = S.pulse(expo(2200, 220, n), n, 0.4) * S.env_exp(n, 0.07)
    crack = S.hp(S.noise(n, rng), 1500) * S.env_exp(n, 0.015) * 0.9
    thump = S.sine(expo(140, 50, n), n) * S.env_exp(n, 0.08) * 0.6
    return finish(mix(zap * 0.6, crack, thump), verb=0.22)

def sfx_bolt_launch():
    n = n_of(0.4)
    w = S.bp(S.noise(n, rng), 800, 5000) * S.env_adsr(0.25, a=0.03, d=0.1, s=0.4, r=0.1, n=n)
    tone = S.sine(expo(700, 1400, n), n) * S.env_exp(n, 0.1) * 0.35
    return finish(mix(w, tone), verb=0.2)

def sfx_bolt_hit():
    n = n_of(0.35)
    thud = S.sine(expo(220, 60, n), n) * S.env_exp(n, 0.06)
    crackle = S.bp(S.noise(n, rng), 1200, 7000) * S.env_exp(n, 0.05) * 0.7
    return finish(mix(thud, crackle), verb=0.25)

def sfx_drone_lunge():
    n = n_of(0.22)
    click = S.hp(S.noise(n, rng), 3000) * S.env_exp(n, 0.008)
    chirp = S.sine(expo(1800, 900, n), n) * S.env_exp(n, 0.05) * 0.5
    return finish(mix(click, chirp), verb=0.15)

def sfx_golem_slam():
    n = n_of(0.7)
    boom = S.sine(expo(70, 28, n), n) * S.env_exp(n, 0.18)
    rubble = S.lp(S.noise(n, rng), 900) * S.env_adsr(0.3, a=0.005, d=0.15, s=0.3, r=0.25, n=n) * 0.7
    crack = S.hp(S.noise(n, rng), 2500) * S.env_exp(n, 0.02) * 0.5
    return finish(mix(boom, rubble, crack), gain=0.95, verb=0.3, ir=IR_LONG, hp=30)

def sfx_enemy_hit():
    n = n_of(0.14)
    tick = S.sine(expo(2600, 1900, n), n) * S.env_exp(n, 0.03)
    chip = S.hp(S.noise(n, rng), 4000) * S.env_exp(n, 0.012) * 0.8
    return finish(mix(tick * 0.6, chip), verb=0.1)

def sfx_enemy_die():
    n = n_of(0.75)
    parts = [S.hp(S.noise(n, rng), 1500) * S.env_exp(n, 0.04)]
    for i, fr in enumerate((2200, 1700, 1300, 900)):
        x = np.zeros(n); st = int(i * n_of(0.05)); seg = n - st
        x[st:] = S.sine(expo(fr, fr * 0.6, seg), seg) * S.env_exp(seg, 0.12) * 0.3; parts.append(x)
    low = S.sine(expo(160, 50, n), n) * S.env_exp(n, 0.15) * 0.6
    return finish(mix(*parts, low), verb=0.3, ir=IR_LONG)

def sfx_vault_clear():
    n = n_of(1.3)
    chord = sum(S.saw(np.full(n, f), n) * 0.18 + S.sine(np.full(n, f * 2), n) * 0.12 for f in (261.6, 329.6, 392.0, 523.3))
    env = S.env_adsr(0.9, a=0.02, d=0.3, s=0.6, r=0.3, n=n)
    shimmer = S.sine(expo(1046, 2093, n), n) * S.env_exp(n, 0.35, hold=0.1) * 0.15
    return finish(mix(S.lp(chord, 3500) * env, shimmer), verb=0.35, ir=IR_LONG)

def sfx_teleport():
    n = n_of(0.8)
    sweep = S.sine(expo(200, 3000, n), n) * S.env_adsr(0.5, a=0.1, d=0.1, s=0.8, r=0.2, n=n) * 0.4
    air = S.bp(S.noise(n, rng), 400, 6000) * S.env_adsr(0.45, a=0.2, d=0.1, s=0.7, r=0.25, n=n) * 0.6
    pop = S.sine(expo(900, 200, n), n) * S.env_exp(n, 0.05, hold=0.5) * 0.5
    return finish(mix(sweep, air, pop), verb=0.3, ir=IR_LONG)

def sfx_kiosk():
    n = n_of(0.3)
    a = S.sine(np.full(n, 880.0), n) * S.env_exp(n, 0.08); b = np.zeros(n); b[n_of(0.1):] = S.sine(np.full(n - n_of(0.1), 1320.0), n - n_of(0.1)) * S.env_exp(n - n_of(0.1), 0.1)
    return finish(mix(a, b) * 0.6, verb=0.15)

def ui_temple_open():
    n = n_of(2.2)
    drone = sum(S.saw(np.full(n, f), n) * 0.15 for f in (65.4, 98.0, 130.8)) * S.env_adsr(1.6, a=0.4, d=0.4, s=0.7, r=0.5, n=n)
    hit = S.sine(expo(120, 40, n), n) * S.env_exp(n, 0.3) * 0.7
    bell = sum(S.sine(np.full(n, f), n) * S.env_exp(n, 0.6, hold=0.2 * i) * 0.12 for i, f in enumerate((523.3, 784.0, 1046.5)))
    return finish(mix(S.lp(drone, 1200), hit, bell), verb=0.4, ir=IR_LONG, hp=30)

def ui_breach():
    n = n_of(1.6)
    tone = np.zeros(n); seg = n_of(0.4)
    for i in range(4):
        f = 440.0 if i % 2 == 0 else 311.1
        tone[i * seg:(i + 1) * seg] = S.pulse(np.full(seg, f), seg, 0.35) * S.env_adsr(0.3, a=0.01, d=0.05, s=0.9, r=0.06, n=seg)
    sub = S.sine(np.full(n, 55.0), n) * S.env_adsr(1.3, a=0.02, d=0.3, s=0.7, r=0.3, n=n) * 0.5
    return finish(mix(S.lp(tone, 3000) * 0.5, sub), verb=0.3, ir=IR_LONG, hp=30)

def ui_ring_warn():
    n = n_of(0.9)
    tone = S.pulse(np.full(n, 196.0), n, 0.25) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 6 * t_of(n)))) * S.env_adsr(0.7, a=0.01, d=0.1, s=0.8, r=0.15, n=n)
    return finish(S.lp(tone, 2500) * 0.5, verb=0.25)

def ui_win():
    n = n_of(2.4)
    notes = [(0.0, 392.0), (0.18, 523.3), (0.36, 659.3), (0.54, 784.0), (0.9, 1046.5)]
    parts = []
    for st, f in notes:
        x = np.zeros(n); i0 = n_of(st); seg = n - i0
        x[i0:] = (S.saw(np.full(seg, f), seg) * 0.2 + S.sine(np.full(seg, f * 2), seg) * 0.1) * S.env_adsr(0.9, a=0.01, d=0.3, s=0.6, r=0.6, n=seg); parts.append(x)
    return finish(S.lp(mix(*parts), 3800), verb=0.4, ir=IR_LONG)

def ui_lose():
    n = n_of(1.8)
    f = expo(220, 110, n)
    x = (S.saw(f, n) * 0.3 + S.sine(f * 0.5, n) * 0.4) * S.env_adsr(1.3, a=0.05, d=0.4, s=0.6, r=0.4, n=n)
    return finish(S.lp(x, 1500), verb=0.4, ir=IR_LONG, hp=30)


# ---------------------------------------------------------------- loops (seamless: built periodic in the loop length)
def loop_amb(kind, seconds=8.0):
    n = n_of(seconds); t = t_of(n)
    cyc = lambda hz: np.sin(2 * np.pi * hz * t)      # whole cycles over the loop stay seamless when hz * seconds is an integer
    per = lambda k: k / seconds
    if kind == 'vault':
        drone = (S.sine(np.full(n, 55.0), n) * 0.5 + S.sine(np.full(n, 82.5), n) * 0.25 + S.saw(np.full(n, 110.0), n) * 0.08) * (0.8 + 0.2 * cyc(per(1)))
        hum = S.sine(np.full(n, 120.0), n) * 0.08 * (0.6 + 0.4 * cyc(per(3)))                     # the conduits
        air = S.lp(S.noise(n, rng), 500) * 0.12 * (0.7 + 0.3 * cyc(per(2)))
        x = S.lp(mix(drone, hum, air), 900)
    elif kind == 'lobby':
        water = S.bp(S.noise(n, rng), 1200, 6000) * 0.08 * (0.75 + 0.25 * cyc(per(5)) * cyc(per(7)))   # the fountain
        drone = S.sine(np.full(n, 65.4), n) * 0.35 * (0.85 + 0.15 * cyc(per(1)))
        x = mix(S.lp(drone, 600), water)
    elif kind == 'staging':
        hum = (S.saw(np.full(n, 60.0), n) * 0.12 + S.sine(np.full(n, 120.0), n) * 0.2) * (0.9 + 0.1 * cyc(per(4)))   # racks
        fans = S.bp(S.noise(n, rng), 300, 1500) * 0.1
        x = S.lp(mix(hum, fans), 2500)
    elif kind == 'arena':
        wind = S.bp(S.noise(n, rng), 150, 900) * 0.2 * (0.6 + 0.4 * cyc(per(1)))
        drone = (S.sine(np.full(n, 41.2), n) * 0.5 + S.sine(np.full(n, 61.7), n) * 0.2) * (0.85 + 0.15 * cyc(per(2)))
        choir = sum(S.sine(np.full(n, f), n) * 0.04 for f in (164.8, 246.9, 329.6)) * (0.5 + 0.5 * cyc(per(1)))
        x = S.lp(mix(wind, drone, choir), 1200)
    else:   # beacon: a bright pulse
        x = (S.sine(np.full(n, 220.0), n) * 0.3 + S.sine(np.full(n, 440.0), n) * 0.2) * (0.55 + 0.45 * cyc(per(8)))
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.7
    return x


SFX = dict(dash=sfx_dash, aegis_up=sfx_aegis_up, aegis_down=sfx_aegis_down, rewind_arm=sfx_rewind_arm, rewind_snap=sfx_rewind_snap,
           sentinel_charge=sfx_sentinel_charge, sentinel_shot=sfx_sentinel_shot, bolt_launch=sfx_bolt_launch, bolt_hit=sfx_bolt_hit,
           drone_lunge=sfx_drone_lunge, golem_slam=sfx_golem_slam, enemy_hit=sfx_enemy_hit, enemy_die=sfx_enemy_die, vault_clear=sfx_vault_clear,
           teleport=sfx_teleport, kiosk=sfx_kiosk)
UI = dict(temple_open=ui_temple_open, breach=ui_breach, ring_warn=ui_ring_warn, win=ui_win, lose=ui_lose)
AMB = ['vault', 'lobby', 'staging', 'arena', 'beacon']

events = [E.event_base_3d('nt.base', full_until=200, silent_at=1600, volume=1.0)]
manifest = dict(sfx=[], ui=[], amb={})
for name, fn in SFX.items():
    x = fn(); C.write_wav(os.path.join(SND_DIR, name + '.wav'), x)
    events.append(E.event_base('nt.' + name, 'nt.base', 'sounds/nt/%s.vsnd' % name)); manifest['sfx'].append(name)
for name, fn in UI.items():
    x = fn(); C.write_wav(os.path.join(SND_DIR, 'ui_' + name + '.wav'), x)
    events.append(E.event_music_flat('nt.ui.' + name, 'sounds/nt/ui_%s.vsnd' % name, volume=0.55)); manifest['ui'].append(name)
for kind in AMB:
    x = loop_amb(kind, 2.0 if kind == 'beacon' else 8.0); C.write_wav(os.path.join(SND_DIR, 'amb_%s.wav' % kind), x, loop=True)
    rng_ = 700 if kind == 'beacon' else 1500
    events.append(E.event_3d('nt.amb.' + kind, 'sounds/nt/amb_%s.vsnd' % kind, rng_, volume=0.45 if kind != 'beacon' else 0.6, full=0.4)); manifest['amb'][kind] = 'nt.amb.' + kind
ours = E.wrap(events)
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
open(os.path.join(OUT, '_gen', 'nanite_sounds.vsndevts'), 'w', newline='\n').write(ours)
tpl = open(TEMPLATE, encoding='utf-8', errors='replace').read()
os.makedirs(os.path.join(OUT, 'soundevents'), exist_ok=True)
open(os.path.join(OUT, 'soundevents', 'soundevents_addon.vsndevts'), 'w', newline='\n', encoding='utf-8').write(E.merge(tpl, ours, 'nanite'))
json.dump(manifest, open(os.path.join(OUT, '_gen', 'sounds.json'), 'w'), indent=0)
print('sounds: %d sfx, %d ui, %d loops -> %s; events merged into soundevents_addon.vsndevts' % (len(SFX), len(UI), len(AMB), SND_DIR))
