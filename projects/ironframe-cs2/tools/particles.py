"""IRONFRAME particles: text .vpcf sources for every effect, adapted from the household's Dogfight particles
(C:/source2/projects/dogfight: df_thrust_*, df_jet_boom*, df_hit_sparks, df_missile_*, df_smoke_*, df_flare_*,
poc/df_cannon_tracer_fwd), retuned for mechs, plus the pool / effect table for the map generator and the adapter.

usage: python -I tools/particles.py <addon out dir>
Writes <out>/particles/ifr/ifr_*.vpcf and <out>/_gen/fx_particles.json:
  {"pools": {"boost": {"count": 128, "effect": "particles/ifr/ifr_boost_medium.vpcf"}, "muzzle": {...}, "boom": {...},
             "spark": {...}, "gboom": {...}, "trail": {...}},
   "effects": {"<key>": "particles/ifr/<file>.vpcf", ...}, "stock": {...}, "notes": {...}}

Format: the vpcf54 text layout Dogfight's particles compile and run with (CParticleSystemDefinition, behaviour version 5,
the editor's field names: C_INIT_CreateWithinSphereTransform, C_INIT_InitFloat with m_nOutputField 1 lifetime / 3 radius /
4 rotation / 7 alpha / 10 trail length, m_vecTexturesInput on the renderer). docs/reference/cs2-gotchas.md: large
translucent sprites cost overdraw, so every emitter here is small and short-lived (64 mechs boosting at once).
Axes: a booster / thruster effect blows along its entity's local +X (Dogfight convention), so parent the
info_particle_system at the nozzle with its forward axis pointing out of the nozzle.
Textures are stock CS2 (materials/particle/..., materials/effects/...), so nothing but the .vpcf files ship.
"""
import os, sys, json

HDR = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} '
       'format:vpcf54:version{326b1595-45e8-4004-aa5a-3e08655ff51f} -->')
LIFE, RADIUS, ROT, ALPHA, TRAIL = 1, 3, 4, 7, 10
FLARE = 'materials/particle/particle_flares/particle_flare_001.vtex'
FIRE = 'materials/particle/fire_burning_character/fire_burning_character.vtex'
SMOKE = 'materials/particle/particle_smokegrenade.vtex'
SPARK = 'materials/effects/yellowflare.vtex'
STREAK = 'materials/effects/spark.vtex'
DEBRIS = 'materials/particle/particle_debris_burst/particle_debris_burst_001.vtex'
GLOWSQ = 'materials/particle/glow_square_01.vtex'
DIR = 'particles/ifr/'


def f(v):
    v = float(v)
    return '%.1f' % v if v == int(v) else ('%.4f' % v).rstrip('0')


def vec(v): return '[ %s ]' % ', '.join(f(x) for x in v)
def col(c): return '[ %d, %d, %d, %s ]' % (c[0], c[1], c[2], 'null' if len(c) < 4 else str(c[3]))


def block(cls, *lines, ind='\t\t'):
    out = [ind + '{', ind + '\t_class = "%s"' % cls]
    for l in lines:
        if isinstance(l, (list, tuple)): out += [ind + '\t' + x for x in l]
        else: out.append(ind + '\t' + l)
    return out + [ind + '},']


def pf(kind, value=None, lo=None, hi=None, flip=False):
    """a particle-float input: literal or uniform random"""
    out = ['{']
    if kind == 'lit': out += ['\tm_nType = "PF_TYPE_LITERAL"', '\tm_flLiteralValue = %s' % f(value)]
    else: out += ['\tm_nType = "PF_TYPE_RANDOM_UNIFORM"', '\tm_flRandomMin = %s' % f(lo), '\tm_flRandomMax = %s' % f(hi), '\tm_nRandomMode = "PF_RANDOM_MODE_CONSTANT"']
    if flip: out.append('\tm_bHasRandomSignFlip = true')
    return out + ['}']


# ---- initializers
def init_float(field, lo, hi=None, flip=False):
    inp = pf('lit', lo, flip=flip) if hi is None else pf('rnd', lo=lo, hi=hi, flip=flip)
    lines = ['m_InputValue = '] + inp
    if field != RADIUS: lines.append('m_nOutputField = %d' % field)
    return block('C_INIT_InitFloat', lines)


def life(lo, hi=None): return init_float(LIFE, lo, hi)
def radius(lo, hi=None): return init_float(RADIUS, lo, hi)
def alpha(lo, hi=None): return init_float(ALPHA, lo, hi)
def spin(): return init_float(ROT, 0.0, 360.0, flip=True)
def color(cmin, cmax): return block('C_INIT_RandomColor', 'm_ColorMin = %s' % col(cmin), 'm_ColorMax = %s' % col(cmax))
def seq(lo, hi): return block('C_INIT_RandomSequence', 'm_nSequenceMin = %d' % lo, 'm_nSequenceMax = %d' % hi)


def sphere(rmax=0.0, speed=None, local=None, bias=None, local_coords=False):
    """spawn within a sphere: speed=(min,max) radial, local=((x,y,z),(x,y,z)) local-axis speed"""
    lines = []
    if rmax: lines.append('m_fRadiusMax = %s' % f(rmax))
    if speed: lines += ['m_fSpeedMin = %s' % f(speed[0]), 'm_fSpeedMax = %s' % f(speed[1])]
    if bias: lines.append('m_vecDistanceBias = %s' % vec(bias))
    if local_coords: lines.append('m_bLocalCoords = true')
    if local: lines += ['m_LocalCoordinateSystemSpeedMin = %s' % vec(local[0]), 'm_LocalCoordinateSystemSpeedMax = %s' % vec(local[1])]
    return block('C_INIT_CreateWithinSphereTransform', *lines)


def box(vmin, vmax):
    return block('C_INIT_CreateWithinBox', 'm_vecMin = %s' % vec(vmin), 'm_vecMax = %s' % vec(vmax))


# ---- operators
def op(cls, **kv): return block(cls, *['%s = %s' % (k, v) for k, v in kv.items()])
def decay(): return op('C_OP_Decay')
def move(drag=None, gravity=None):
    kv = {}
    if drag is not None: kv['m_fDrag'] = f(drag)
    if gravity is not None: kv['m_Gravity'] = vec(gravity)
    return op('C_OP_BasicMovement', **kv)
def lock(): return op('C_OP_PositionLock')
def fade_in(t=None): return op('C_OP_FadeIn', **({'m_flFadeInTimeMin': f(t), 'm_flFadeInTimeMax': f(t)} if t else {}))
def fade_out(t=None, prop=True):
    kv = {}
    if t is not None: kv.update(m_flFadeOutTimeMin=f(t), m_flFadeOutTimeMax=f(t))
    if not prop: kv['m_bProportional'] = 'false'
    return op('C_OP_FadeOut', **kv)
def fade_kill(in_end=0.01): return op('C_OP_FadeAndKill', m_flEndFadeInTime=f(in_end), m_flStartAlpha='0.0')
def grow(start=None, end=None):
    kv = {}
    if start is not None: kv['m_flStartScale'] = f(start)
    if end is not None: kv['m_flEndScale'] = f(end)
    return op('C_OP_InterpolateRadius', **kv)
def tint(c, start=None, end=None, ease=None):
    kv = {'m_ColorFade': col(c)}
    if start is not None: kv['m_flFadeStartTime'] = f(start)
    if end is not None: kv['m_flFadeEndTime'] = f(end)
    if ease is not None: kv['m_bEaseInOut'] = 'true' if ease else 'false'
    return op('C_OP_ColorInterpolate', **kv)
def flicker(fmin=12, fmax=20, rmin=0.5, rmax=1.0, field=RADIUS):
    return op('C_OP_OscillateScalar', m_FrequencyMax=f(fmax), m_FrequencyMin=f(fmin), m_RateMax=f(rmax), m_RateMin=f(rmin), m_nField=str(field))


# ---- emitters, renderers, children
def emit(rate, duration=None, start=None):
    lines = ['m_flEmitRate = '] + pf('lit', rate)
    if duration is not None: lines.append('m_flEmissionDuration = %s' % f(duration))
    if start is not None: lines.append('m_flStartTime = %s' % f(start))
    return block('C_OP_ContinuousEmitter', lines)
def burst(n): return block('C_OP_InstantaneousEmitter', ['m_nParticlesToEmit = '] + pf('lit', n))


def sprites(tex, additive=False, overbright=None, anim=None, add_self=False, fade_size=None, orient=None):
    lines = []
    if fade_size: lines += ['m_flStartFadeSize = %s' % f(fade_size[0]), 'm_flEndFadeSize = %s' % f(fade_size[1])]
    if overbright: lines.append('m_flOverbrightFactor = %s' % f(overbright))
    if add_self: lines += ['m_flAddSelfAmount = 1.0', 'm_bSaturateColorPreAlphaBlend = false']
    if anim: lines += ['m_flAnimationRate = %s' % f(anim), 'm_bAnimateInFPS = true']
    if orient is not None: lines.append('m_nOrientationType = %d' % orient)
    lines += ['m_vecTexturesInput = ', '[', '\t{', '\t\tm_hTexture = resource:"%s"' % tex, '\t},', ']']
    if additive: lines.append('m_nOutputBlendMode = "PARTICLE_OUTPUT_BLEND_MODE_ADD"')
    return block('C_OP_RenderSprites', *lines)


def trails(tex, max_len, fade_in_t=0.05, radius_scale=1.0, additive=True):
    lines = ['m_flMaxLength = %s' % f(max_len), 'm_flLengthFadeInTime = %s' % f(fade_in_t), 'm_flMinSize = 0.01', 'm_flMaxSize = 0.01', 'm_bClampV = true',
             'm_flRadiusScale = '] + pf('lit', radius_scale)
    lines += ['m_vecTexturesInput = ', '[', '\t{', '\t\tm_hTexture = resource:"%s"' % tex, '\t},', ']']
    if additive: lines.append('m_nOutputBlendMode = "PARTICLE_OUTPUT_BLEND_MODE_ADD"')
    return block('C_OP_RenderTrails', *lines)


def child(path, delay=None, detail=None):
    lines = ['m_ChildRef = resource:"%s"' % path]
    if delay: lines.append('m_flDelay = %s' % f(delay))
    if detail: lines.append('m_nDetailLevel = "%s"' % detail)
    return block('', *lines)[0:1] + ['\t\t\t' + l for l in lines] + ['\t\t},']


def system(maxp, renderers=(), ops=(), inits=(), emitters=(), children=(), radius_=None, bbox=None, draw_dist=None, sort=True, pre=()):
    out = [HDR, '{', '\t_class = "CParticleSystemDefinition"', '\tm_bShouldHitboxesFallbackToRenderBounds = false', '\tm_nMaxParticles = %d' % maxp]
    if radius_ is not None: out.append('\tm_flConstantRadius = %s' % f(radius_))
    if bbox: out += ['\tm_BoundingBoxMin = %s' % vec(bbox[0]), '\tm_BoundingBoxMax = %s' % vec(bbox[1])]
    if draw_dist: out.append('\tm_flMaxDrawDistance = %s' % f(draw_dist))
    if not sort: out.append('\tm_bShouldSort = false')
    if pre: out += ['\tm_PreEmissionOperators = ', '\t['] + [l for p in pre for l in p] + ['\t]']
    for name, items in (('m_Renderers', renderers), ('m_Operators', ops), ('m_Initializers', inits), ('m_Emitters', emitters), ('m_Children', children)):
        if items: out += ['\t%s = ' % name, '\t['] + [l for it in items for l in it] + ['\t]']
    out += ['\tm_nBehaviorVersion = 5', '}']
    return '\n'.join(out) + '\n'


# ================================================================ the effects
FILES = {}      # name -> text
NOTES = {}      # name -> (source, note)


def put(name, text, src, note): FILES[name] = text; NOTES[name] = (src, note)


def P(name): return DIR + name + '.vpcf'


BLUE_HOT = ((190, 225, 255), (255, 255, 255))
BLUE_FLAME = ((120, 190, 255), (60, 120, 255))


def boosters():
    """blue-white thruster: additive glow core (df_thrust_boost) + an animated flame tongue (df_thrust_boost_flame) tinted
    blue + a sparse spark spit; three sizes. The flame blows along local +X."""
    for cls, core_r, flame_r, speed, rate_f, maxf, sp_rate in (('light', (26, 34), (9, 13), (650, 900), 150, 24, 14),
                                                              ('medium', (34, 46), (13, 18), (800, 1100), 180, 32, 18),
                                                              ('heavy', (46, 62), (18, 26), (900, 1250), 210, 44, 24)):
        flame = system(maxf, [sprites(FIRE, overbright=3.2, anim=45, add_self=True, fade_size=(0.45, 0.575))],
                       [decay(), move(), fade_in(), fade_out(0.5), lock(), grow(end=0.35), tint((30, 50, 140), start=0.45)],
                       [sphere(3.0, local=((speed[0], 0, 0), (speed[1], 0, 0))), seq(3, 5), spin(), alpha(0.55, 0.85), radius(*flame_r), life(0.1, 0.14), color(*BLUE_FLAME)],
                       [emit(rate_f)], sort=False)
        put('ifr_boost_%s_flame' % cls, flame, 'df_thrust_boost_flame', 'blue flame tongue, %s class' % cls)
        core = system(12, [sprites(FLARE, additive=True, overbright=3.0)],
                      [lock(), move(), decay(), fade_in(), fade_out(), flicker(12, 20, 0.5, 1.0)],
                      [sphere(), life(0.08, 0.12), radius(*core_r), color(*BLUE_HOT), alpha(0.7, 0.9)],
                      [emit(90)], [child(P('ifr_boost_%s_flame' % cls)), child(P('ifr_boost_sparks'))], radius_=core_r[1], sort=False)
        put('ifr_boost_%s' % cls, core, 'df_thrust_boost', 'thruster glow core + children, %s class' % cls)
    sparks = system(24, [sprites(SPARK, additive=True, overbright=2.0)],
                    [move(0.02, (0, 0, -300)), decay(), grow(end=0.3), tint((80, 140, 255), start=0.2, end=0.7), fade_out()],
                    [color((220, 240, 255), (255, 255, 255)), life(0.25, 0.45), sphere(4.0, speed=(80, 220), local=((500, 0, 0), (900, 0, 0))), radius(2.5, 4.5), alpha(1.0)],
                    [emit(18)], draw_dist=6000)
    put('ifr_boost_sparks', sparks, 'df_hit_sparks', 'sparse spark spit from a nozzle (shared child)')
    heat = system(8, [sprites(SMOKE, anim=1)],
                  [move(0.05), decay(), fade_kill(0.05), grow(end=2.2), lock()],
                  [life(0.25, 0.4), radius(10, 16), spin(), alpha(0.06, 0.1), sphere(2.0, local=((400, 0, 0), (700, 0, 0))), color((40, 40, 48), (70, 70, 80))],
                  [emit(14)])
    put('ifr_boost_heat', heat, 'df_smoke_light', 'faint exhaust haze (a true refraction shimmer needs a normal-map texture: deferred)')


def qb_hover():
    qb = system(40, [sprites(FLARE, additive=True, overbright=3.0)],
                [decay(), move(0.06), fade_out(0.1, prop=False), grow(end=1.8), flicker(10, 20, 1.0, 2.0)],
                [sphere(24, speed=(400, 900)), life(0.18, 0.3), color((200, 230, 255), (255, 255, 255)), radius(18, 30), alpha(1.0)],
                [burst(18)], [child(P('ifr_qb_ring'))])
    put('ifr_qb_burst', qb, 'df_flare_burst', 'quick-boost burst: a radial puff of blue-white glow')
    ring = system(6, [sprites(FLARE, additive=True, overbright=2.0)],
                  [decay(), fade_out(0.2, prop=False), grow(start=0.3, end=3.0)],
                  [sphere(), life(0.3), color((120, 190, 255), (160, 210, 255)), radius(90), alpha(0.6)],
                  [burst(2)])
    put('ifr_qb_ring', ring, 'df_flare_balls', 'the expanding glow ring of a quick boost')
    hover = system(28, [sprites(FLARE, additive=True, overbright=2.2)],
                   [move(0.02, (0, 0, -200)), decay(), fade_in(), fade_out(), grow(end=0.4), lock()],
                   [sphere(40, speed=(40, 120), local=((0, 0, -300), (0, 0, -500))), life(0.2, 0.35), color((170, 215, 255), (240, 250, 255)), radius(10, 16), alpha(0.5, 0.8)],
                   [emit(60)], [child(P('ifr_hover_dust'))])
    put('ifr_hover', hover, 'df_thrust_idle', 'hover: downward glow wash under the mech')
    dust = system(16, [sprites(SMOKE, anim=1)],
                  [move(0.1, (0, 0, 20)), decay(), fade_kill(0.05), grow(end=2.5), tint((150, 140, 125, 40), end=0.3, ease=False)],
                  [life(0.7, 1.1), radius(30, 48), spin(), alpha(0.15, 0.25), sphere(60, speed=(60, 160)), color((190, 180, 160), (150, 140, 125))],
                  [emit(12)])
    put('ifr_hover_dust', dust, 'df_smoke_light', 'dust kicked up by hovering')


def muzzles():
    rifle = system(10, [sprites(FLARE, additive=True, overbright=3.0)],
                   [decay(), move(), fade_out(0.04, prop=False), grow(end=1.6), lock()],
                   [sphere(4, local=((300, 0, 0), (600, 0, 0))), life(0.05, 0.08), color((255, 235, 190), (255, 200, 120)), radius(22, 34), alpha(1.0)],
                   [burst(4)], [child(P('ifr_muzzle_core'))], sort=False)
    put('ifr_muzzle_rifle', rifle, 'df_flare_burst', 'rifle / smg / gatling / autocannon flash: 4 hot sprites thrown forward + a core flash')
    core = system(2, [sprites(FLARE, additive=True, overbright=3.5)],
                  [decay(), fade_out(0.03, prop=False), grow(end=0.5)],
                  [sphere(), life(0.06), color((255, 255, 240), (255, 240, 210)), radius(42), alpha(1.0)],
                  [burst(1)])
    put('ifr_muzzle_core', core, 'df_flare_balls', 'the single bright core of a muzzle flash')
    heavy = system(14, [sprites(FIRE, overbright=3.0, anim=40, add_self=True, fade_size=(0.5, 0.65))],
                   [decay(), move(0.1), fade_out(0.3), grow(end=1.8), tint((120, 40, 10), start=0.4), lock()],
                   [sphere(10, local=((500, 0, 0), (1100, 0, 0))), seq(3, 5), spin(), life(0.12, 0.2), color((255, 230, 170), (255, 150, 60)), radius(40, 60), alpha(0.9)],
                   [burst(8)], [child(P('ifr_muzzle_core')), child(P('ifr_muzzle_smoke'))], sort=False)
    put('ifr_muzzle_heavy', heavy, 'df_thrust_boost_flame + df_jet_boom', 'bazooka / cannon / shotgun flash: a fire tongue + core + smoke puff')
    smoke = system(8, [sprites(SMOKE, anim=1)],
                   [move(0.15, (0, 0, 40)), decay(), fade_kill(0.05), grow(start=0.6, end=2.5), tint((120, 120, 120, 40), end=0.3, ease=False)],
                   [life(0.6, 1.0), radius(24, 40), spin(), alpha(0.3, 0.45), sphere(8, local=((300, 0, 0), (600, 0, 0))), color((200, 200, 200), (160, 160, 160))],
                   [burst(5)])
    put('ifr_muzzle_smoke', smoke, 'df_jet_boom_smoke', 'muzzle smoke puff')
    tracer = system(32, [trails(STREAK, 320, 0.05, 1.5)],
                    [move(0.0), decay()],
                    [radius(5.0), init_float(TRAIL, 0.03), sphere(local=((11000, 0, 0), (11000, 0, 0))), life(0.42), color((255, 230, 150), (255, 200, 90))],
                    [burst(1)], draw_dist=20000)
    put('ifr_tracer', tracer, 'poc/df_cannon_tracer_fwd', 'a glowing streak fired along +X at 11000 u/s, one per Start (4600 u reach); rifle/autocannon tracers')


def impacts():
    metal_sparks = system(48, [sprites(SPARK, additive=True, overbright=2.0)],
                          [move(0.02, (0, 0, -500)), decay(), grow(end=0.3), tint((255, 120, 30), start=0.2, end=0.6), fade_out()],
                          [color((255, 250, 225), (255, 200, 120)), life(0.3, 0.6), sphere(6, speed=(250, 700)), radius(5, 10), alpha(1.0)],
                          [burst(22)], [child(P('ifr_impact_flash'))], draw_dist=12000)
    put('ifr_impact_metal', metal_sparks, 'df_hit_sparks', 'round on armour: 22 sparks + a flash (spark pool, 16)')
    flash = system(2, [sprites(FLARE, additive=True, overbright=3.0)],
                   [decay(), fade_out(0.04, prop=False), grow(end=1.5)],
                   [sphere(), life(0.08), color((255, 240, 200), (255, 255, 255)), radius(30), alpha(0.9)],
                   [burst(1)])
    put('ifr_impact_flash', flash, 'df_flare_balls', 'impact flash')
    ground = system(20, [sprites(SMOKE, anim=1)],
                    [move(0.12, (0, 0, 30)), decay(), fade_kill(0.05), grow(start=0.5, end=2.4), tint((140, 125, 100, 30), end=0.25, ease=False)],
                    [life(0.6, 1.0), radius(26, 44), spin(), alpha(0.35, 0.5), sphere(12, speed=(120, 320), bias=(1, 1, 2.0)), color((205, 190, 160), (160, 145, 120))],
                    [burst(9)], [child(P('ifr_impact_grit'))])
    put('ifr_impact_ground', ground, 'df_jet_boom_smoke', 'round on terrain: a dust puff + grit')
    grit = system(24, [sprites(DEBRIS, overbright=1.0)],
                  [move(0.01, (0, 0, -900)), decay(), fade_out(0.2)],
                  [color((150, 135, 110), (90, 80, 65)), life(0.4, 0.8), sphere(6, speed=(300, 700), bias=(1, 1, 2.5)), radius(3, 6), spin(), alpha(1.0)],
                  [burst(10)])
    put('ifr_impact_grit', grit, 'df_hit_sparks (debris texture)', 'grit thrown from a ground hit')
    sparks_long = system(40, [sprites(SPARK, additive=True, overbright=2.2)],
                         [move(0.03, (0, 0, -400)), decay(), grow(end=0.4), tint((120, 170, 255), start=0.2, end=0.7), fade_out(), lock()],
                         [color((235, 245, 255), (255, 255, 255)), life(0.25, 0.5), sphere(60, speed=(200, 600)), radius(4, 8), alpha(1.0)],
                         [emit(30, duration=2.0)])
    put('ifr_stagger_sparks', sparks_long, 'df_hit_sparks', 'blue-white electrical sparks for 2 s (the stagger time), from the mech')
    beam_hit = system(30, [sprites(FLARE, additive=True, overbright=3.2)],
                      [decay(), move(0.05), fade_out(0.08, prop=False), grow(end=1.4), flicker(14, 24, 1.0, 2.0)],
                      [sphere(10, speed=(100, 400)), life(0.1, 0.22), color((255, 120, 110), (255, 220, 200)), radius(14, 28), alpha(1.0)],
                      [burst(12)], [child(P('ifr_beam_sparks'))])
    put('ifr_laser_beam_impact', beam_hit, 'df_flare_burst', 'laser / rail beam end: a hot red-white flare burst + molten sparks')
    beam_sparks = system(24, [sprites(SPARK, additive=True, overbright=2.0)],
                         [move(0.02, (0, 0, -600)), decay(), grow(end=0.3), tint((255, 60, 20), start=0.1, end=0.5), fade_out()],
                         [color((255, 240, 220), (255, 180, 120)), life(0.3, 0.6), sphere(4, speed=(200, 600)), radius(3, 6), alpha(1.0)],
                         [burst(12)])
    put('ifr_beam_sparks', beam_sparks, 'df_hit_sparks', 'molten sparks from a beam hit')


def booms():
    def fireball(name, maxp, n, rmax, speed, rad, life_, children, src_note, scale=(0.5, 1.5)):
        x = system(maxp, [sprites(FIRE, overbright=3.0, anim=30, add_self=True, fade_size=(0.9, 1.3))],
                   [decay(), move(0.08), fade_in(), fade_out(0.6), grow(*scale), tint((90, 30, 10), start=0.35)],
                   [sphere(rmax, speed=speed), seq(3, 5), spin(), alpha(0.85, 1.0), radius(*rad), life(*life_), color((255, 225, 160), (255, 140, 60))],
                   [burst(n)], children, radius_=rad[1], bbox=((-1500, -1500, -1500), (1500, 1500, 1500)),
                   pre=[op('C_OP_SetControlPointPositions', m_vecCP1Pos=vec((0, 0, 10)))])
        put(name, x, 'df_jet_boom', src_note)

    def smoke(name, n, rmax, speed, rad, life_, src='df_jet_boom_smoke'):
        x = system(n + 2, [sprites(SMOKE, anim=1)],
                   [move(0.08, (0, 0, 25)), tint((24, 24, 24, 60), end=0.2, ease=False), grow(start=0.5, end=2.0), fade_kill(0.01)],
                   [life(*life_), radius(*rad), spin(), alpha(0.5, 0.7), sphere(rmax, speed=speed), color((62, 58, 54), (34, 32, 30))],
                   [burst(n)], bbox=((-32, -32, -10), (32, 32, 200)), draw_dist=800000)
        put(name, x, src, 'smoke of ' + name.replace('ifr_', '').replace('_smoke', ''))

    smoke('ifr_boom_small_smoke', 8, 60, (100, 300), (90, 150), (2.5, 3.5))
    fireball('ifr_boom_small', 12, 7, 50, (200, 500), (110, 180), (0.6, 1.0),
             [child(P('ifr_boom_small_smoke')), child(P('ifr_boom_sparks')), child('particles/explosions_fx/explosion_c4_flash02b_1k.vpcf')],
             'small splash (plasma, grenade, flak, hand missiles): 7 fire sprites + smoke + sparks + a stock flash (boom pool, 24)')
    smoke('ifr_boom_large_smoke', 14, 180, (200, 550), (240, 400), (4.0, 6.0))
    fireball('ifr_boom_large', 20, 12, 150, (350, 950), (300, 480), (0.9, 1.5),
             [child(P('ifr_boom_large_smoke')), child(P('ifr_boom_sparks')), child('particles/explosions_fx/explosion_c4_flash02b_1k.vpcf'),
              child('particles/explosions_fx/explosion_c4_distort01d_1k.vpcf'), child('particles/explosions_fx/explosion_c4_debris.vpcf'),
              child('particles/explosions_fx/explosion_c4_light.vpcf', detail='PARTICLEDETAIL_MEDIUM')],
             'large splash (bazooka, grenade cannon): fireball + smoke + stock C4 distortion / debris / light (gboom pool, 8)')
    sparks = system(40, [sprites(SPARK, additive=True, overbright=2.0)],
                    [move(0.02, (0, 0, -500)), decay(), grow(end=0.3), tint((255, 110, 30), start=0.2, end=0.6), fade_out()],
                    [color((255, 250, 225), (255, 200, 120)), life(0.5, 1.0), sphere(20, speed=(400, 1100)), radius(6, 12), alpha(1.0)],
                    [burst(20)], draw_dist=20000)
    put('ifr_boom_sparks', sparks, 'df_hit_sparks', 'embers thrown by an explosion (shared child)')
    smoke('ifr_mech_death_smoke', 18, 220, (250, 650), (300, 480), (5.0, 7.0))
    column = system(60, [sprites(SMOKE, anim=1)],
                    [move(0.03, (0, 0, 90)), tint((30, 30, 30, 70), end=0.2, ease=False), grow(start=0.6, end=2.6), fade_kill(0.05)],
                    [life(3.5, 5.0), radius(140, 220), spin(), alpha(0.45, 0.6), sphere(70, speed=(40, 120), local=((0, 0, 250), (0, 0, 450))), color((60, 56, 52), (30, 28, 26))],
                    [emit(14, duration=3.5)], bbox=((-600, -600, -10), (600, 600, 2500)), draw_dist=800000)
    put('ifr_mech_death_column', column, 'df_smoke_heavy', 'the rising smoke column of a dead mech (3.5 s)')
    debris = system(40, [sprites(DEBRIS, overbright=1.0)],
                    [move(0.02, (0, 0, -800)), decay(), fade_out(0.3), tint((40, 35, 30), start=0.3, end=0.8)],
                    [color((255, 160, 70), (120, 90, 60)), life(1.2, 2.2), sphere(40, speed=(500, 1300), bias=(1, 1, 1.8)), radius(8, 18), spin(), alpha(1.0)],
                    [burst(30)], draw_dist=20000)
    put('ifr_mech_death_debris', debris, 'df_hit_sparks (debris texture)', 'glowing debris chunks arcing out of a dead mech')
    fireball('ifr_mech_death', 30, 18, 200, (400, 1200), (420, 680), (1.2, 1.9),
             [child(P('ifr_mech_death_smoke')), child(P('ifr_mech_death_column')), child(P('ifr_mech_death_debris')), child(P('ifr_boom_sparks')),
              child('particles/explosions_fx/explosion_c4_flash02b_1k.vpcf'), child('particles/explosions_fx/explosion_c4_flash03b_1k.vpcf', detail='PARTICLEDETAIL_MEDIUM'),
              child('particles/explosions_fx/explosion_c4_distort01d_1k.vpcf'), child('particles/explosions_fx/explosion_c4_debris.vpcf'),
              child('particles/explosions_fx/explosion_c4_embers.vpcf'), child('particles/explosions_fx/explosion_c4_trails.vpcf', delay=0.05),
              child('particles/explosions_fx/explosion_c4_smoketrails.vpcf'), child('particles/explosions_fx/explosion_c4_light.vpcf', detail='PARTICLEDETAIL_MEDIUM')],
             'mech destroyed: big fireball + debris + smoke column + the stock C4 flash/distortion/trails (Dogfight df_jet_boom set)')


def trails_and_abilities():
    flame = system(30, [sprites(FLARE, additive=True, overbright=3.0)],
                   [decay(), move(), fade_in(), fade_out(), lock(), grow(end=0.4), flicker(12, 20, 0.5, 1.0)],
                   [sphere(local=((-600, 0, 0), (-420, 0, 0))), life(0.06, 0.1), radius(12, 18), color((255, 245, 220), (255, 200, 120)), alpha(0.9, 1.0)],
                   [emit(140)])
    put('ifr_missile_flame', flame, 'df_missile_flame', 'missile motor flame (blows along local -X, behind a missile prop facing +X)')
    smoke = system(110, [sprites(SMOKE, anim=1)],
                   [move(None, (0, 0, 10)), tint((190, 190, 190, 50), end=0.2, ease=False), grow(end=3.0), fade_kill(0.01)],
                   [life(1.4, 2.0), radius(22, 30), spin(), alpha(0.3, 0.45), sphere(), color((245, 245, 245), (215, 215, 215))],
                   [emit(60)], bbox=((-32, -32, -10), (32, 32, 200)), draw_dist=800000)
    put('ifr_missile_smoke', smoke, 'df_missile_smoke', 'missile smoke trail (life 1.4-2 s, 60/s: 128 missiles stay under 15k sprites)')
    motor = system(8, [], [lock()], [], [], [child(P('ifr_missile_flame')), child(P('ifr_missile_smoke'))],
                   bbox=((-32, -32, -24), (32, 32, 96)), draw_dist=800000)
    put('ifr_missile_trail', motor, 'df_missile_motor', 'missile trail parent: flame + smoke, parented to a pooled missile prop (trail pool, 128)')
    bubble = system(90, [sprites(FLARE, additive=True, overbright=1.6)],
                    [lock(), decay(), fade_in(), fade_out(), flicker(6, 12, 0.3, 0.6)],
                    [sphere(350, bias=(1, 1, 1)), life(0.5, 0.9), radius(28, 44), color((80, 160, 255), (160, 220, 255)), alpha(0.25, 0.45)],
                    [emit(70)], [child(P('ifr_shield_core'))], bbox=((-400, -400, -400), (400, 400, 400)))
    put('ifr_shield_bubble', bubble, 'df_thrust_boost (glow) ', 'pulse shield: a 350 u shell of blue glow motes + a soft core (Start/Stop with the 6 s bubble)')
    core = system(2, [sprites(FLARE, additive=True, overbright=1.2)],
                  [lock(), decay(), fade_in(0.3), fade_out(0.3), flicker(2, 4, 0.1, 0.2)],
                  [sphere(), life(6.5), radius(360), color((40, 90, 200), (60, 120, 230)), alpha(0.12)],
                  [burst(1)])
    put('ifr_shield_core', core, 'df_flare_balls', 'one large faint sphere glow inside the bubble (6.5 s)')
    repair = system(40, [sprites(FLARE, additive=True, overbright=2.0)],
                    [lock(), move(0.05, (0, 0, 90)), decay(), fade_in(0.15), fade_out(), grow(end=0.5)],
                    [sphere(110, local=((0, 0, 60), (0, 0, 140))), life(0.9, 1.4), radius(6, 12), color((90, 255, 140), (190, 255, 210)), alpha(0.6, 0.9)],
                    [emit(26)], bbox=((-200, -200, -50), (200, 200, 500)))
    put('ifr_repair', repair, 'df_thrust_boost (glow)', 'repair: green motes rising around the mech (Start for 6 s then Stop)')
    decoy = system(40, [sprites(FLARE, additive=True, overbright=3.0)],
                   [decay(), move(), fade_out(0.05, prop=False), grow(end=1.5), flicker(10, 20, 1.0, 2.0), lock()],
                   [sphere(), life(0.1, 0.15), color((255, 255, 255), (255, 236, 200)), radius(45, 65), init_float(ROT, 90.0, flip=True), alpha(1.0)],
                   [emit(60, duration=0.5)], [child(P('ifr_decoy_sparks')), child(P('ifr_decoy_smoke')), child(P('ifr_decoy_balls'))])
    put('ifr_decoy', decoy, 'df_flare_burst', 'decoy launcher: Dogfight flare burst (flash + sparks + smoke + two falling flare balls)')
    balls = system(2, [sprites(FLARE, additive=True, overbright=2.5)],
                   [decay(), move(0.01, (0, 0, -350)), fade_out(0.5, prop=False), flicker(10, 20, 1.0, 2.0)],
                   [sphere(speed=(250, 450), bias=(0.3, 1.0, 0.2), local_coords=True), life(2.6, 3.0), color((255, 255, 255), (255, 236, 200)), radius(30, 40), alpha(1.0)],
                   [burst(2)])
    put('ifr_decoy_balls', balls, 'df_flare_balls', 'two burning flares falling away')
    dsparks = system(60, [sprites(SPARK, additive=True, overbright=2.0)],
                     [move(0.02, (0, 0, -300)), decay(), grow(end=0.3), tint((255, 160, 40), start=0.2, end=0.6), fade_out()],
                     [color((255, 250, 225), (255, 200, 120)), life(0.6, 1.2), sphere(6, speed=(200, 500)), radius(4, 8), alpha(1.0)],
                     [emit(80, duration=0.5)])
    put('ifr_decoy_sparks', dsparks, 'df_flare_sparks', 'decoy sparks')
    dsmoke = system(30, [sprites(SMOKE, anim=1)],
                    [move(0.05, (0, 0, 15)), tint((200, 200, 200, 50), end=0.2, ease=False), grow(end=2.5), fade_kill(0.01)],
                    [life(1.5, 2.2), radius(26, 36), spin(), alpha(0.3, 0.45), sphere(10, speed=(40, 120)), color((245, 245, 245), (215, 215, 215))],
                    [emit(14, duration=0.6)])
    put('ifr_decoy_smoke', dsmoke, 'df_flare_smoke', 'decoy smoke puffs')


def pillars():
    for team, cmin, cmax in (('t', (255, 120, 40), (255, 190, 90)), ('ct', (60, 140, 255), (140, 200, 255)), ('neutral', (220, 220, 220), (255, 255, 255))):
        pillar = system(70, [sprites(FLARE, additive=True, overbright=1.8)],
                        [move(0.0), decay(), fade_in(0.2), fade_out(0.4), grow(end=0.6)],
                        [sphere(55, local=((0, 0, 500), (0, 0, 800))), life(2.6, 3.2), radius(50, 80), color(cmin, cmax), alpha(0.18, 0.3)],
                        [emit(20)], [child(P('ifr_capture_%s_base' % team))], bbox=((-200, -200, -10), (200, 200, 2800)), draw_dist=30000)
        put('ifr_capture_%s' % team, pillar, 'df_thrust_boost (glow)', 'capture point pillar, %s: additive motes rising 2000+ u (visible across the arena)' % team)
        base = system(12, [sprites(FLARE, additive=True, overbright=1.5)],
                      [lock(), decay(), fade_in(), fade_out(), flicker(3, 6, 0.2, 0.4)],
                      [sphere(90), life(1.2, 1.8), radius(90, 140), color(cmin, cmax), alpha(0.15, 0.25)],
                      [emit(6)])
        put('ifr_capture_%s_base' % team, base, 'df_thrust_boost (glow)', 'glowing base disc of the pillar')
    entry = system(36, [sprites(FIRE, overbright=3.2, anim=40, add_self=True, fade_size=(0.45, 0.6))],
                   [decay(), move(0.05), fade_in(), fade_out(0.5), lock(), grow(end=0.4), tint((255, 120, 30), start=0.4)],
                   [sphere(40, local=((0, 0, 700), (0, 0, 1100))), seq(3, 5), spin(), alpha(0.7, 0.9), radius(60, 90), life(0.15, 0.25), color((255, 250, 230), (255, 200, 120))],
                   [emit(120)], [child(P('ifr_drop_entry_glow')), child(P('ifr_drop_entry_smoke'))], sort=False)
    put('ifr_drop_entry', entry, 'df_thrust_boost_flame', 'drop-pod entry: white-orange plasma sheath streaming up (local +Z) off a falling pod, with glow and smoke')
    glow = system(4, [sprites(FLARE, additive=True, overbright=2.5)],
                  [lock(), decay(), fade_in(), fade_out(), flicker(8, 14, 0.4, 0.8)],
                  [sphere(), life(0.15, 0.25), radius(150, 200), color((255, 230, 190), (255, 255, 255)), alpha(0.5, 0.7)],
                  [emit(12)])
    put('ifr_drop_entry_glow', glow, 'df_thrust_boost', 'the hot glow around an entering pod')
    esmoke = system(40, [sprites(SMOKE, anim=1)],
                    [move(0.05, (0, 0, 60)), tint((120, 110, 100, 40), end=0.3, ease=False), grow(end=2.5), fade_kill(0.05)],
                    [life(1.0, 1.6), radius(50, 80), spin(), alpha(0.3, 0.45), sphere(30, local=((0, 0, 300), (0, 0, 600))), color((230, 220, 200), (170, 160, 150))],
                    [emit(24)], bbox=((-300, -300, -10), (300, 300, 3000)), draw_dist=800000)
    put('ifr_drop_entry_smoke', esmoke, 'df_missile_smoke', 'entry smoke trail')


STOCK = {
    'explosion_c4_500': 'particles/explosions_fx/explosion_c4_500.vpcf',
    'explosion_basic': 'particles/explosions_fx/explosion_basic.vpcf',
    'explosion_hegrenade_brief': 'particles/explosions_fx/explosion_hegrenade_brief.vpcf',
    'muzzle_assaultrifle': 'particles/weapons/cs_weapon_fx/weapon_muzzle_flash_assaultrifle.vpcf',
    'muzzle_assaultrifle_fallback': 'particles/weapons/cs_weapon_fx/weapon_muzzle_flash_assaultrifle_fallback.vpcf',
    'impact_metal': 'particles/impact_fx/impact_metal.vpcf',
    'impact_metal_cheap': 'particles/impact_fx/impact_metal_cheap.vpcf',
    'impact_dirt': 'particles/impact_fx/impact_dirt.vpcf',
    'impact_concrete': 'particles/impact_fx/impact_concrete.vpcf',
    'env_fire_medium_smoke': 'particles/burning_fx/env_fire_medium_smoke.vpcf',
    'env_sparks_directional': 'particles/ambient_fx/env_sparks_directional.vpcf',
    'weapon_tracers_50cal': 'particles/weapons/cs_weapon_fx/weapon_tracers_50cal.vpcf',
}
EFFECTS = {   # key the adapter / map generator uses -> file
    'boost_light': 'ifr_boost_light', 'boost_medium': 'ifr_boost_medium', 'boost_heavy': 'ifr_boost_heavy', 'qb_burst': 'ifr_qb_burst', 'hover': 'ifr_hover',
    'muzzle_rifle': 'ifr_muzzle_rifle', 'muzzle_heavy': 'ifr_muzzle_heavy', 'tracer': 'ifr_tracer',
    'impact_metal': 'ifr_impact_metal', 'impact_ground': 'ifr_impact_ground', 'boom_small': 'ifr_boom_small', 'boom_large': 'ifr_boom_large',
    'mech_death': 'ifr_mech_death', 'missile_trail': 'ifr_missile_trail', 'laser_beam_impact': 'ifr_laser_beam_impact', 'stagger_sparks': 'ifr_stagger_sparks',
    'shield_bubble': 'ifr_shield_bubble', 'repair': 'ifr_repair', 'decoy': 'ifr_decoy',
    'capture_t': 'ifr_capture_t', 'capture_ct': 'ifr_capture_ct', 'capture_neutral': 'ifr_capture_neutral', 'drop_entry': 'ifr_drop_entry',
}
POOLS = {
    'boost': {'count': 128, 'effect': 'ifr_boost_medium', 'note': 'two per mech, parented at claim time; the effect of an info_particle_system is fixed, so the pool is one class. Split as boost_light/heavy pools if the generator wants class flavour (variants below).', 'variants': {'light': 'ifr_boost_light', 'heavy': 'ifr_boost_heavy'}},
    'muzzle': {'count': 64, 'effect': 'ifr_muzzle_rifle', 'note': 'pulsed per shot (Start); heavy weapons may use muzzle_heavy on a second pool if wanted'},
    'boom': {'count': 24, 'effect': 'ifr_boom_small', 'note': 'teleport then Start; ~1 s'},
    'spark': {'count': 16, 'effect': 'ifr_impact_metal', 'note': 'teleport then Start; 0.6 s'},
    'gboom': {'count': 8, 'effect': 'ifr_boom_large', 'note': 'mech deaths may use ifr_mech_death on 4 of these, or a 7th pool "death"'},
    'trail': {'count': 128, 'effect': 'ifr_missile_trail', 'note': 'parented to the pooled missile prop; Start at launch, Stop at impact (the smoke lingers 2 s)'},
}


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    out = sys.argv[1]; pdir = os.path.join(out, 'particles', 'ifr'); os.makedirs(pdir, exist_ok=True); os.makedirs(os.path.join(out, '_gen'), exist_ok=True)
    boosters(); qb_hover(); muzzles(); impacts(); booms(); trails_and_abilities(); pillars()
    for name, text in FILES.items():
        open(os.path.join(pdir, name + '.vpcf'), 'w', encoding='utf-8', newline='\n').write(text)
    # every child we reference must exist (ours) or be stock
    refs = set()
    for text in FILES.values():
        for line in text.splitlines():
            if 'm_ChildRef' in line and DIR in line: refs.add(line.split('"')[1][len(DIR):-5])
    missing = sorted(r for r in refs if r not in FILES)
    if missing: sys.exit('particles: missing children %s' % missing)
    doc = {'version': 1, 'dir': DIR,
           'pools': {k: dict(v, effect=P(v['effect']), **({'variants': {a: P(b) for a, b in v['variants'].items()}} if 'variants' in v else {})) for k, v in POOLS.items()},
           'effects': {k: P(v) for k, v in EFFECTS.items()},
           'stock': STOCK,
           'files': {n: {'source': NOTES[n][0], 'note': NOTES[n][1]} for n in FILES},
           'notes': {'axes': 'boosters and muzzles emit along the entity\'s local +X; the missile flame along -X; hover, pillars and drop entry along +-Z',
                     'counts': 'per-mech live sprites: boost core 12 + flame <= 44 + sparks 24 + heat 8; the whole arena at 64 boosting mechs stays under 6k sprites',
                     'stock_children': 'boom_large and mech_death reference stock explosions_fx children (compiled with the map, as Dogfight did)'}}
    json.dump(doc, open(os.path.join(out, '_gen', 'fx_particles.json'), 'w', encoding='utf-8'), indent=1)
    print('particles: %d .vpcf files (%d top-level effects, %d pools, %d stock references) -> %s' % (len(FILES), len(EFFECTS), len(POOLS), len(STOCK), pdir))


if __name__ == '__main__':
    main()
