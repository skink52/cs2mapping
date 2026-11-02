"""Names shared by every generator and the script build. Override with NT_NAME / NT_MAP in the environment."""
import os
NAME = os.environ.get('NT_NAME', 'nanite')               # script maps/scripts/<NAME>.js, HUD panorama/<NAME>.xml
MAP = os.environ.get('NT_MAP', 'mg_nanite_temple')        # maps/<MAP>.vmap, the addon folder has the same name
ADDON = os.environ.get('NT_ADDON', MAP)
PREFIX = 'nt'                                             # entity names nt_*, models/nt, materials/nt
GROUP = 'nt_gen'                                          # vis group of everything the generator writes
SCRIPT_PATH = 'maps/scripts/%s.vjs' % NAME
HUD_PATH = 'panorama/layout/custom_game/%s.vxml' % NAME
