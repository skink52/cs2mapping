"""vpcf66 writer: generated particles in the format the CS2 particle editor saves.

Older layouts (vpcf1 with C_INIT_CreateWithinSphere / C_INIT_RandomLifeTime / C_INIT_RandomRadius, m_hTexture straight on the renderer,
m_bAdditive) are dropped when the file is opened in the particle editor: a trail saved in the editor came back with no initializers and
drew nothing. These structs copy the editor's own field lists. Method from github.com/Ninja-Chris/cs2-slop-porting 3.5 (MIT).
Particle attribute fields for init_float: 1 lifetime, 3 radius, 4 rotation, 5 rotation speed, 7 alpha.
"""

HDR = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} '
       'format:vpcf66:version{dd571be4-586e-4f41-8b2d-5bbc969e1c53} -->\n')
LIFE, RADIUS, ROT, ROTSPEED, ALPHA = 1, 3, 4, 5, 7


def f(v):
    v = float(v)
    return ('%.4f' % v).rstrip('0').rstrip('.') if v != int(v) else '%.1f' % v


def pf(ind, ptype='PF_TYPE_LITERAL', **ov):
    d = [('m_nType', '"%s"' % ptype), ('m_nMapType', '"PF_MAP_TYPE_DIRECT"'), ('m_flLiteralValue', '0.0'), ('m_NamedValue', '""'),
         ('m_nControlPoint', '0'), ('m_nScalarAttribute', '3'), ('m_nVectorAttribute', '6'), ('m_nVectorComponent', '0'),
         ('m_bReverseOrder', 'false'), ('m_flRandomMin', '0.0'), ('m_flRandomMax', '1.0'), ('m_bHasRandomSignFlip', 'false'),
         ('m_nRandomSeed', '-1'), ('m_nRandomMode', '"PF_RANDOM_MODE_CONSTANT"'), ('m_strSnapshotSubset', '""'), ('m_flLOD0', '0.0'),
         ('m_flLOD1', '0.0'), ('m_flLOD2', '0.0'), ('m_flLOD3', '0.0'), ('m_nNoiseInputVectorAttribute', '0'), ('m_flNoiseOutputMin', '0.0'),
         ('m_flNoiseOutputMax', '1.0'), ('m_flNoiseScale', '0.1'), ('m_vecNoiseOffsetRate', '[ 0.0, 0.0, 0.0 ]'), ('m_flNoiseOffset', '0.0'),
         ('m_nNoiseOctaves', '1'), ('m_nNoiseTurbulence', '"PF_NOISE_TURB_NONE"'), ('m_nNoiseType', '"PF_NOISE_TYPE_PERLIN"'),
         ('m_nNoiseModifier', '"PF_NOISE_MODIFIER_NONE"'), ('m_flNoiseTurbulenceScale', '1.0'), ('m_flNoiseTurbulenceMix', '0.5'),
         ('m_flNoiseImgPreviewScale', '1.0'), ('m_bNoiseImgPreviewLive', 'true'), ('m_flNoCameraFallback', '0.0'),
         ('m_bUseBoundsCenter', 'false'), ('m_nInputMode', '"PF_INPUT_MODE_CLAMPED"'), ('m_flMultFactor', '1.0'), ('m_flInput0', '0.0'),
         ('m_flInput1', '1.0'), ('m_flOutput0', '0.0'), ('m_flOutput1', '1.0'), ('m_flNotchedRangeMin', '0.0'),
         ('m_flNotchedRangeMax', '1.0'), ('m_flNotchedOutputOutside', '0.0'), ('m_flNotchedOutputInside', '1.0'),
         ('m_nRoundType', '"PF_ROUND_TYPE_NEAREST"'), ('m_nBiasType', '"PF_BIAS_TYPE_STANDARD"'), ('m_flBiasParameter', '0.0')]
    out = ['{'] + ['\t%s = %s' % (k, ov.get(k, v)) for k, v in d]
    out += ['\tm_Curve = ', '\t{', '\t\tm_spline = [  ]', '\t\tm_tangents = [  ]', '\t\tm_vDomainMins = [ 0.0, 0.0 ]',
            '\t\tm_vDomainMaxs = [ 0.0, 0.0 ]', '\t}', '\tm_flCompareValue = 0.0', '}']
    return [ind + x for x in out]


def pvec(ind, v):
    out = ['{', '\tm_nType = "PVEC_TYPE_LITERAL"', '\tm_vLiteralValue = [ %s, %s, %s ]' % tuple(f(x) for x in v),
           '\tm_LiteralColor = [ 0, 0, 0 ]', '\tm_NamedValue = ""', '\tm_bFollowNamedValue = false', '\tm_nVectorAttribute = 6',
           '\tm_vVectorAttributeScale = [ 1.0, 1.0, 1.0 ]', '\tm_nControlPoint = 0', '\tm_nDeltaControlPoint = 0',
           '\tm_vCPValueScale = [ 1.0, 1.0, 1.0 ]', '\tm_vCPRelativePosition = [ 0.0, 0.0, 0.0 ]', '\tm_vCPRelativeDir = [ 1.0, 0.0, 0.0 ]']
    for comp in ('m_FloatComponentX', 'm_FloatComponentY', 'm_FloatComponentZ', 'm_FloatInterp'):
        out.append('\t%s = ' % comp); out += ['\t' + x for x in pf('')]
    out += ['\tm_flInterpInput0 = 0.0', '\tm_flInterpInput1 = 1.0', '\tm_vInterpOutput0 = [ 0.0, 0.0, 0.0 ]',
            '\tm_vInterpOutput1 = [ 1.0, 1.0, 1.0 ]', '\tm_Gradient = ', '\t{', '\t\tm_Stops = [  ]', '\t}',
            '\tm_vRandomMin = [ 0.0, 0.0, 0.0 ]', '\tm_vRandomMax = [ 0.0, 0.0, 0.0 ]', '}']
    return [ind + x for x in out]


def init_float(lo, hi, field, flip=False, ind='\t\t'):
    out = [ind + '{', ind + '\t_class = "C_INIT_InitFloat"', ind + '\tm_InputValue = ']
    out += pf(ind + '\t', 'PF_TYPE_RANDOM_UNIFORM', m_flRandomMin=f(lo), m_flRandomMax=f(hi), m_bHasRandomSignFlip='true' if flip else 'false')
    return out + [ind + '\tm_nOutputField = %d' % field, ind + '},']


def sphere(vmin=(0, 0, 0), vmax=(0, 0, 0), rmin=0.0, rmax=0.0, smin=0.0, smax=0.0, ind='\t\t'):
    out = [ind + '{', ind + '\t_class = "C_INIT_CreateWithinSphereTransform"']
    if smax: out += [ind + '\tm_fSpeedMin = %s' % f(smin), ind + '\tm_fSpeedMax = %s' % f(smax)]
    if rmax:
        out += [ind + '\tm_fRadiusMin = ']; out += pf(ind + '\t', m_flLiteralValue=f(rmin))
        out += [ind + '\tm_fRadiusMax = ']; out += pf(ind + '\t', m_flLiteralValue=f(rmax))
    if any(vmin) or any(vmax):
        out.append(ind + '\tm_LocalCoordinateSystemSpeedMin = '); out += pvec(ind + '\t', vmin)
        out.append(ind + '\tm_LocalCoordinateSystemSpeedMax = '); out += pvec(ind + '\t', vmax)
    return out + [ind + '},']


def renderer(tex, kind='C_OP_RenderSprites', additive=False, selfillum=None, refract=None, extra=()):
    ind = '\t\t\t'
    out = ['\t\t{', ind + '_class = "%s"' % kind]
    if additive: out.append(ind + 'm_nOutputBlendMode = "PARTICLE_OUTPUT_BLEND_MODE_ADD"')
    if selfillum is not None:
        out.append(ind + 'm_flSelfIllumAmount = '); out += pf(ind, m_flLiteralValue=f(selfillum))
    if refract is not None:
        out += [ind + 'm_bRefract = true', ind + 'm_flRefractAmount = '] + pf(ind, m_flLiteralValue=f(refract))
        out += [ind + 'm_nRefractBlurRadius = 1', ind + 'm_nRefractBlurType = "BLURFILTER_BOX"']
    out += [ind + x for x in extra]
    out += [ind + 'm_vecTexturesInput =', ind + '[', ind + '\t{', ind + '\t\tm_hTexture = resource:"%s"' % tex, ind + '\t},', ind + ']', '\t\t},']
    return out


def op(cls, **kv):
    return ['\t\t{', '\t\t\t_class = "%s"' % cls] + ['\t\t\t%s = %s' % (k, v) for k, v in kv.items()] + ['\t\t},']


def system(maxp, color, radius, renderers, rate, inits, ops):
    r, g, b, a = color
    return HDR + '\n'.join([
        '{', '\t_class = "CParticleSystemDefinition"', '\tm_nBehaviorVersion = 12', '\tm_nMaxParticles = %d' % maxp,
        '\tm_ConstantColor = [ %d, %d, %d, %d ]' % (r, g, b, a), '\tm_flConstantRadius = %s' % f(radius),
        '\tm_Renderers =', '\t['] + renderers + ['\t]',
        '\tm_Emitters =', '\t['] + op('C_OP_ContinuousEmitter', m_flEmitRate='%.2f' % rate) + ['\t]',
        '\tm_Initializers =', '\t['] + inits + ['\t]',
        '\tm_Operators =', '\t['] + ops + ['\t]', '}']) + '\n'


def fade(t_in=0.5, t_out=0.5):
    return op('C_OP_FadeAndKill', m_flStartFadeInTime='0.0', m_flEndFadeInTime=f(t_in), m_flStartFadeOutTime=f(1 - t_out),
              m_flEndFadeOutTime='1.0', m_flStartAlpha='0.0', m_flEndAlpha='0.0')
