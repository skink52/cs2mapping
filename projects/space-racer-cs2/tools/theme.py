"""Which game the generators build: SPR_THEME=space (Space Racer, the default), neon (Neon Racer) or depth (Depth
Racer). All three share the game code in src/; everything that differs (tracks, look, names, music) is picked here.
Neon and Depth are one family (NEON is true for both): flight sections, the glowing pixel look, electronic music;
DEPTH switches that family to the deep sea (its palette, skies, scenery, creatures and music)."""
import os, importlib

THEME = os.environ.get('SPR_THEME', 'space')
DEPTH = THEME == 'depth'
NEON = THEME in ('neon', 'depth')
TITLE = {'neon': 'NEON RACER', 'depth': 'DEPTH RACER'}.get(THEME, 'SPACE RACER')
NAME = {'neon': 'neon_racer', 'depth': 'depth_racer'}.get(THEME, 'space_racer')
MAP = 'mg_' + NAME
_DEFS = {'neon': 'trackdefs_neon', 'depth': 'trackdefs_depth'}.get(THEME, 'trackdefs')

def defs():
    """the theme's track designs module (TRACKS, THEMES, HALF)"""
    return importlib.import_module(_DEFS)
