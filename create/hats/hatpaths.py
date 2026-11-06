"""Paths for the hat tools (catalog `paths`, environment overrides), like playermodels/fetch.paths."""
import os

DEFAULTS = {
    'steamcmd': r'C:\steamcmd\steamcmd.exe',
    'work': r'C:\source1\hats',
    'template': r'C:\source1\playermodels\template',        # the decompiled agent (read only): its skeleton and head
    'basegame': r'C:\source1\playermodels\basegame',        # HL2 / CS:S materials (read only)
    'out': r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\gmod_hats',
}
ENV = {'steamcmd': 'STEAMCMD', 'work': 'HATS_WORK', 'template': 'PM_TEMPLATE', 'basegame': 'PM_BASEGAME', 'out': 'HATS_OUT'}


def paths(cat=None):
    p = dict(DEFAULTS); p.update((cat or {}).get('paths', {}))
    for k, e in ENV.items():
        if os.environ.get(e): p[k] = os.environ[e]
    return p
