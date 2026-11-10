"""Names shared by every generator and the script build. IF_ARENA picks the map (dunes | sprawl | orbital); IF_NAME / IF_MAP override."""
import os
ARENA = os.environ.get('IF_ARENA', 'dunes')
ARENAS = {'dunes': 'Dunes', 'sprawl': 'Sprawl', 'orbital': 'Orbital'}
if ARENA not in ARENAS:
    raise SystemExit('IF_ARENA must be one of %s' % ', '.join(ARENAS))
TITLE = 'IRONFRAME: ' + ARENAS[ARENA]
NAME = os.environ.get('IF_NAME', 'ironframe')              # script maps/scripts/<NAME>.js, HUD panorama/<NAME>.xml (same on every map)
MAP = os.environ.get('IF_MAP', 'mg_ironframe_' + ARENA)    # maps/<MAP>.vmap; the addon folder has the same name
ADDON = os.environ.get('IF_ADDON', MAP)
PREFIX = 'ifr'                                             # entity names ifr_*, models/ifr, materials/ifr, sounds/ifr
GROUP = 'ifr_gen'                                          # vis group of everything the generator writes
SCRIPT_PATH = 'maps/scripts/%s.vjs' % NAME
HUD_PATH = 'panorama/layout/custom_game/%s.vxml' % NAME
