"""Sounds (wav + sound events) and the sky material."""
import os, sys, math, wave, struct, json
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import assets

OUT = sys.argv[1]
SKY = sys.argv[2] if len(sys.argv) > 2 else 'SKY1'

MUSIC_VOLUME = 0.7          # music loudness (each player's own music volume setting scales it too)
MUSIC_MODE = 'menuconvar'   # see sounds(): menuconvar | music | mega

SOUNDS = ('barexp bdcls bdopn bfg dbcls dbload dbopn dorcls doropn dshtgn firxpl getpow itemup itmbk noway oof pdiehi pistol '
          'plasma pldeth plpain pstart pstop punch rlaunc rxplod sawful sawhit sawidl sawup shotgn slop stnmov telept wpnup '
          'swtchn swtchx '
          # monsters (sight, attack, pain, death, idle)
          'posit1 posit2 posit3 popain podth1 podth2 podth3 posact bgsit1 bgsit2 bgdth1 bgdth2 bgact dmpain dmact '
          'sgtsit sgtatk sgtdth cacsit cacdth kntsit kntdth brssit brsdth skesit skedth skeact skeatk skeswg skepch '
          'pesit pepain pedth mansit mnpain mandth manatk bspsit bspdth bspact bspwlk vilsit vipain vildth vilact vilatk '
          'flame flamst cybsit cybdth hoof metal spisit spidth sklatk claw firsht').split()

def convert_wav(src, dst):
    with wave.open(src) as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    if sw == 1:
        a = (np.frombuffer(data, np.uint8).astype(np.int16) - 128) * 256
    else:
        a = np.frombuffer(data, np.int16)
    if ch == 2: a = a.reshape(-1, 2).mean(1).astype(np.int16)
    # resample to 44.1 kHz (linear) so every platform plays it the same
    t = np.arange(0, len(a), rate / 44100.0)
    b = np.interp(t, np.arange(len(a)), a).astype(np.int16)
    with wave.open(dst, 'wb') as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(44100)
        o.writeframes(b.tobytes())

def sounds():
    d = os.path.join(OUT, 'sounds/fdm'); os.makedirs(d, exist_ok=True)
    ev = ['<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->',
          '{',
          '\t"fdm.base" =', '\t{', '\t\ttype = "csgo_mega"', '\t\tvolume = 1.0', '\t\tpitch = 1.0',
          '\t\tdistance_volume_mapping_curve =', '\t\t[',
          '\t\t\t[', '\t\t\t\t0.0, 1.0, 0.0, 0.0,', '\t\t\t\t2.0, 3.0,', '\t\t\t],',
          '\t\t\t[', '\t\t\t\t200.0, 1.0, 0.0, 0.0,', '\t\t\t\t2.0, 3.0,', '\t\t\t],',
          '\t\t\t[', '\t\t\t\t1400.0, 0.0, 0.0, 0.0,', '\t\t\t\t2.0, 3.0,', '\t\t\t],',
          '\t\t]', '\t}']
    found = []
    for s in SOUNDS:
        src = os.path.join(assets.FD, 'sounds', 'ds%s.wav' % s)
        if not os.path.exists(src):
            print('missing sound', s); continue
        convert_wav(src, os.path.join(d, 'ds%s.wav' % s))
        found.append(s)
        ev += ['\t"fdm.%s" =' % s, '\t{', '\t\tbase = "fdm.base"', '\t\tvsnd_files_track_01 = "sounds/fdm/ds%s.vsnd"' % s, '\t}']
    # music (tools/music.py): csgo_music plays the same for everyone, at each player's own music volume (snd_musicvolume
    # applies by itself; a volume_convar line makes CS2 look for snd_musicvolume_rush/_casual/... and spam the console)
    # MUSIC_MODE (env FDM_MUSIC_MODE):
    #   menuconvar: csgo_music with volume_convar snd_menumusic_volume (Valve's own music-box example; the stack still
    #               follows the music volume slider, and may stop looking up snd_musicvolume_<mode>, which spams the
    #               console with "Unable to acquire convar value: snd_musicvolume_rush")
    #   music:      plain csgo_music (follows snd_musicvolume; spams the console on some builds)
    #   mega:       csgo_mega with a flat distance curve: no console spam, but the music follows the effects volume,
    #               not the music slider
    mj = os.path.join(OUT, '_gen/music.json')
    mode = os.environ.get('FDM_MUSIC_MODE', MUSIC_MODE)
    for t in (json.load(open(mj)) if os.path.exists(mj) else []):
        if mode == 'mega':
            ev += ['\t"fdm_music.%s" =' % t['id'], '\t{', '\t\ttype = "csgo_mega"', '\t\tvolume = %.2f' % MUSIC_VOLUME, '\t\tpitch = 1.0',
                   '\t\tvsnd_files_track_01 = "sounds/fdm/music/%s.vsnd"' % t['id'],
                   '\t\tdistance_volume_mapping_curve =', '\t\t[',
                   '\t\t\t[', '\t\t\t\t0.0, 1.0, 0.0, 0.0,', '\t\t\t\t2.0, 3.0,', '\t\t\t],',
                   '\t\t\t[', '\t\t\t\t100000.0, 1.0, 0.0, 0.0,', '\t\t\t\t2.0, 3.0,', '\t\t\t],',
                   '\t\t]', '\t}']
        else:
            ev += ['\t"fdm_music.%s" =' % t['id'], '\t{', '\t\ttype = "csgo_music"', '\t\tvolume = %.2f' % MUSIC_VOLUME]
            if mode == 'menuconvar': ev.append('\t\tvolume_convar = "snd_menumusic_volume"')
            ev += ['\t\tvsnd_files = "sounds/fdm/music/%s.vsnd"' % t['id'], '\t}']
    ev.append('}')
    os.makedirs(os.path.join(OUT, 'soundevents'), exist_ok=True)
    open(os.path.join(OUT, 'soundevents/soundevents_addon.vsndevts'), 'w', newline='\n').write('\n'.join(ev) + '\n')
    return found

def sky():
    tex = assets.texture(SKY)[..., :3].astype(np.float32)
    H, W = 1024, 2048
    out = np.zeros((H, W, 3), np.float32)
    lat = (0.5 - (np.arange(H) + 0.5) / H) * math.pi          # +pi/2 top
    lon = (np.arange(W) + 0.5) / W * 2 * math.pi
    row = 100 - np.tan(np.clip(lat, -1.4, 1.4)) * 160 / 1.2
    # Doom players can't look up this far; CS2 players can, so keep the pattern going by mirroring the texture
    row = np.floor(row).astype(int) % 256
    row = np.where(row > 127, 255 - row, row)
    col = (lon / (2 * math.pi) * 1024).astype(int) % 256
    # Doom's sky turns the other way from the equirect longitude
    col = (255 - col) % 256
    out[:] = tex[row[:, None], col[None, :]]
    # soften the zenith/nadir pinch into the sky's average colour
    avg = tex.reshape(-1, 3).mean(0)
    k = np.clip((np.abs(lat) - 1.25) / 0.3, 0, 1)[:, None, None]
    out = out * (1 - k) + avg * k
    d = os.path.join(OUT, 'materials/fdm/sky'); os.makedirs(d, exist_ok=True)
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(os.path.join(d, 'sky_color.png'))
    vm = ['// FreeDM sky (%s)' % SKY, 'Layer0', '{', '\tshader "sky.vfx"', '\tF_TEXTURE_FORMAT2 1',
          '\tSkyTexture "materials/fdm/sky/sky_color.png"', '\tg_flBrightnessExposureBias "0.000"', '}']
    open(os.path.join(d, 'sky.vmat'), 'w', newline='\n').write('\n'.join(vm) + '\n')

if __name__ == '__main__':
    print('sounds', len(sounds()))
    sky()
    print('sky done')
