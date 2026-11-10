"""An arena's own post-processing file, made from the addon template's basic_linear_post.vpost (Valve's file: not kept in git,
so the values are patched into a copy at deploy time).

    python -I tools/arenas/post.py <template .vpost> <out .vpost> <look>

Looks (only the bloom layer changes; tone mapping stays the template's, the exposure range is the post_processing_volume's):
  sprawl  neon night: the bloom starts lower and is a little stronger, so signs, screens, windows, beams and thruster flames
          glow; the widest blur is tinted slightly violet (wet-air look). Unseen in game when written (11 Nov 2026): if it
          washes out, raise m_flBloomThreshold toward the template's 2.842.
A value that is not found in the template is reported and the file is not written.
"""
import re, sys

LOOKS = {
    'sprawl': {'m_flBloomStrength': 2.3, 'm_flBloomThreshold': 2.1, 'm_flBloomThresholdWidth': 1.8, 'm_flScreenBloomStrength': 0.16,
               'tint_last': (0.96, 0.92, 1.08)},
}


def make(src, dst, look):
    s = open(src, encoding='utf-8').read()
    L = dict(LOOKS[look]); tint = L.pop('tint_last', None)
    for k, v in L.items():
        s, n = re.subn(r'(%s\s*=\s*)[-0-9.eE]+' % re.escape(k), lambda m: m.group(1) + repr(float(v)), s, count=1)
        if n != 1: sys.exit('post.py: %s not in %s' % (k, src))
    if tint:
        m = re.search(r'm_vBlurTint\s*=\s*\[(.*?)\n\t\t\t\t\]', s, re.S)
        if not m: sys.exit('post.py: m_vBlurTint not in %s' % src)
        rows = re.findall(r'\[[^\[\]]*\]', m.group(1))
        if not rows: sys.exit('post.py: no tint rows')
        body = m.group(1)
        i = body.rindex(rows[-1])
        body = body[:i] + '[ %s, %s, %s ]' % tint + body[i + len(rows[-1]):]
        s = s[:m.start(1)] + body + s[m.end(1):]
    open(dst, 'w', encoding='utf-8', newline='\n').write(s)
    print('post %s -> %s' % (look, dst))


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[3] not in LOOKS: sys.exit(__doc__)
    make(sys.argv[1], sys.argv[2], sys.argv[3])
