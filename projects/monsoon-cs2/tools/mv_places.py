"""mg_monsoon places: firebase, camp, flags, village, temple, crash site, bridge, paddies dressing, jungle scatter. (stage 4; filled in later)"""
import numpy as np
import layout as L


def terrain_holes(CX, CY, r):
    """cells left out of the terrain: tunnel portals (filled in with the tunnels)"""
    return np.zeros(CX.shape, bool)


def build(d, group, out, T, karst, clone):
    pass
