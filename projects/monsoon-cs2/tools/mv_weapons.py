"""mg_monsoon era weapons: scripts/weapons.vdata for the addon (playtest 1 batch G, docs/WEAPONS.md).

usage: python mv_weapons.py [<addon content out>] [--base <stock weapons.vdata>] [--check]      default ../out/addon

Takes the stock decompile of CS2's weapons.vdata (Source 2 Viewer dev build; default C:/source2/projects/trenchwarfare/weapons.vdata,
25 Oct 2026, the file mg_trenchwarfare edits) and changes only the entries below: era stats for every class the script hands out, and
the world model of a class whose remodel is in the addon (models/weapons/mv/<name>/<name>.vmdl, built by tools/weapons/build_weapon.py
from tools/weapons_mv/*.json). A model that is not in the addon is never named (the stock model stays). Every edited key must already
exist in the entry, so a renamed key in a newer decompile fails loudly instead of being ignored. --check: report only, write nothing.
Writes <addon>/scripts/weapons.vdata and ../out/weapons.json (the table, for docs and tests). AI-generated (Claude) for skink52.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'C:/source2/projects/trenchwarfare/weapons.vdata'

# class -> (era name, side, {key: vdata value text}); the remodel's model path goes in 'model' (used only when it exists)
W = {
    'weapon_m4a1': ('M16A1', 'US rifleman', {
        'm_iMaxClip1': '20', 'm_nPrimaryReserveAmmoMax': '6', 'm_flCycleTime': '0.08', 'm_flRecoilMagnitude': '[ 21.0, 21.0 ]'}),
    'weapon_ak47': ('AK-47 / Type 56', 'NVA rifleman', {
        'm_nPrimaryReserveAmmoMax': '4'}),
    'weapon_m249': ('M60', 'US machine gunner', {
        'm_nDamage': '35', 'm_iMaxClip1': '100', 'm_flCycleTime': '0.1', 'm_flArmorRatio': '1.7', 'm_flMaxSpeed': '[ 190.0, 190.0 ]',
        'm_flRecoilMagnitude': '[ 27.0, 27.0 ]'}),
    'weapon_negev': ('RPD', 'NVA machine gunner', {
        'm_nDamage': '33', 'm_iMaxClip1': '100', 'm_flCycleTime': '0.086', 'm_flMaxSpeed': '[ 190.0, 190.0 ]', 'm_flRecoilMagnitude': '[ 24.0, 24.0 ]'}),
    'weapon_scar20': ('M14', 'US marksman', {
        'm_nDamage': '52', 'm_iMaxClip1': '20', 'm_nPrimaryReserveAmmoMax': '4', 'm_bIsFullAuto': 'false', 'm_flCycleTime': '0.15',
        'm_flArmorRatio': '1.7', 'm_nZoomLevels': '1', 'm_nZoomFOV1': '55', 'm_nZoomFOV2': '55', 'm_bHideViewModelWhenZoomed': 'false',
        'm_flMaxSpeed': '[ 220.0, 160.0 ]', 'm_flInaccuracyStand': '[ 0.008, 0.004 ]', 'm_flInaccuracyCrouch': '[ 0.006, 0.003 ]',
        'm_flRecoilMagnitude': '[ 32.0, 32.0 ]',
        'model': 'models/weapons/mv/m14/m14.vmdl'}),
    'weapon_galilar': ('SKS', 'NVA marksman', {
        'm_nDamage': '46', 'm_iMaxClip1': '10', 'm_nPrimaryReserveAmmoMax': '5', 'm_bIsFullAuto': 'false', 'm_flCycleTime': '0.14',
        'm_nZoomLevels': '1', 'm_nZoomFOV1': '60', 'm_flInaccuracyStand': '[ 0.007, 0.007 ]', 'm_flRecoilMagnitude': '[ 26.0, 26.0 ]'}),
    'weapon_hkp2000': ('M1911A1', 'US pistol', {
        'm_nDamage': '40', 'm_iMaxClip1': '7', 'm_nPrimaryReserveAmmoMax': '5', 'm_flCycleTime': '0.2', 'm_flRangeModifier': '0.85',
        'm_flArmorRatio': '0.95', 'm_flRecoilMagnitude': '[ 30.0, 30.0 ]',
        'model': 'models/weapons/mv/m1911/m1911.vmdl'}),
    'weapon_glock': ('TT-33', 'NVA pistol', {
        'm_nDamage': '34', 'm_iMaxClip1': '8', 'm_nPrimaryReserveAmmoMax': '5', 'm_bHasBurstMode': 'false', 'm_flCycleTime': '[ 0.17, 0.3 ]',
        'm_flArmorRatio': '1.2', 'm_flPenetration': '1.5'}),
    'weapon_nova': ('Ithaca 37', 'upgrade (both sides)', {
        'm_nDamage': '24', 'm_iMaxClip1': '5', 'm_nPrimaryReserveAmmoMax': '25', 'm_flCycleTime': '0.75'}),
    'weapon_m4a1_silencer': ('XM177E2', 'US upgrade', {
        'm_nDamage': '31', 'm_iMaxClip1': '20', 'm_nPrimaryReserveAmmoMax': '6', 'm_flCycleTime': '0.075', 'm_flMaxSpeed': '[ 230.0, 230.0 ]'}),
    'weapon_mac10': ('K-50M', 'NVA upgrade', {
        'm_nDamage': '30', 'm_iMaxClip1': '35', 'm_nPrimaryReserveAmmoMax': '4', 'm_flCycleTime': '0.067', 'm_flRange': '4000.0',
        'm_flRangeModifier': '0.82', 'm_flArmorRatio': '1.25', 'm_flMaxSpeed': '[ 235.0, 235.0 ]'}),
    'weapon_g3sg1': ('M21', 'US upgrade', {
        'm_nDamage': '85', 'm_iMaxClip1': '20', 'm_nPrimaryReserveAmmoMax': '3', 'm_bIsFullAuto': 'false', 'm_flCycleTime': '0.35',
        'm_flArmorRatio': '1.8', 'm_nZoomFOV1': '30', 'm_nZoomFOV2': '12', 'm_flRecoilMagnitude': '[ 34.0, 30.0 ]',
        'model': 'models/weapons/mv/m21/m21.vmdl'}),
    'weapon_ssg08': ('Mosin-Nagant M91/30 PU', 'NVA upgrade', {
        'm_nDamage': '110', 'm_iMaxClip1': '5', 'm_nPrimaryReserveAmmoMax': '4', 'm_flCycleTime': '1.5', 'm_flArmorRatio': '1.9',
        'm_nZoomFOV1': '35', 'm_nZoomFOV2': '15', 'm_flMaxSpeed': '[ 220.0, 110.0 ]'}),
}


def block(text, cls):
    """(start, end) of the entry's body: from the line after '\\t<cls> = ' to its closing '\\n\\t}'"""
    m = re.search(r'\n\t%s = \s*\n\t\{' % re.escape(cls), text)
    if not m: raise SystemExit('mv_weapons: no entry %s in the base vdata' % cls)
    end = text.find('\n\t}', m.end())
    return m.end(), end


def apply(text, addon):
    rows, bad = [], []
    for cls, (name, side, keys) in W.items():
        a, b = block(text, cls)
        body = text[a:b]
        done = {}
        for k, v in keys.items():
            if k == 'model':
                if os.path.exists(os.path.join(addon, *v.split('/'))):
                    k, v = 'm_szWorldModel', 'resource_name:"%s"' % v
                else: done['model'] = 'stock (%s not built)' % v; continue
            rx = re.compile(r'(\n\t\t%s = )([^\n]*)' % re.escape(k))
            if not rx.search(body): bad.append('%s: key %s not in the entry' % (cls, k)); continue
            old = rx.search(body).group(2)
            body = rx.sub(lambda m: m.group(1) + v, body, count=1)
            done[k] = '%s -> %s' % (old.strip(), v)
        text = text[:a] + body + text[b:]
        rows.append(dict(cls=cls, name=name, side=side, edits=done))
    return text, rows, bad


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    addon = os.path.abspath(args[0] if args else os.path.join(HERE, '..', 'out', 'addon'))
    base = argv[argv.index('--base') + 1] if '--base' in argv else BASE
    if '--base' in argv: args = [a for a in args if a != base]
    text = open(base, encoding='utf-8').read()
    if not text.startswith('<!-- kv3'): raise SystemExit('mv_weapons: %s is not a kv3 text vdata' % base)
    out, rows, bad = apply(text, addon)
    for r in rows:
        print('%-22s %-24s %-22s %s' % (r['cls'], r['name'], r['side'], ', '.join('%s %s' % (k.replace('m_', ''), v) for k, v in r['edits'].items())))
    for b in bad: print('PROBLEM:', b)
    if bad: sys.exit(1)
    if '--check' in argv: return
    dst = os.path.join(addon, 'scripts', 'weapons.vdata'); os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8', newline='\n').write(out)
    json.dump(rows, open(os.path.join(HERE, '..', 'out', 'weapons.json'), 'w'), indent=1)
    print('wrote %s (%d entries edited, %d bytes)' % (dst, len(rows), len(out)))


if __name__ == '__main__':
    main(sys.argv[1:])
