"""Moving and interactive brushes with the right keys and wiring: doors, buttons that open them, lifts, rotators, breakables, physics props,
damage / push / teleport zones, ladders (vmaplib map open; shapes from primitives.py).

  door(shape, name, move='+z', distance=None, speed=150, wait=4, locked=False, sound=None)     func_door; distance = its size along `move`
  button(shape, name, targets=[(target, input), ...], wait=1)                                 func_button pressed with E or a shot
  lift(shape, name, height, speed=120, start_at_bottom=True)    func_movelinear + Open / Close; an optional call button: button(..., [(name, 'Open')])
  rotator(shape, name, speed=60, axis='z', start_on=True)       func_rotating about the shape's centre
  breakable(shape, name='', health=50, material=0)              func_breakable (material 0 glass, 1 wood, 2 metal, 3 flesh, 4 cinder, 6 computer)
  physics_prop(model, origin, name='', mass=None)               prop_physics_override
  zone(shape, kind='hurt' | 'push' | 'teleport', **opts)        trigger_hurt (damage / s), trigger_push (speed, push_dir angles),
                                                                trigger_teleport (target = info_teleport_destination it also places)
  ladder(bottom_xyz, top_z, width=32, facing=(1, 0))            a climbable toolsinvisibleladder volume against a wall facing `facing`

Ported from physics.py of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): doors, buttons, lifts, rotation, physics props,
breakables, zones and ladders; fresh code. Their physics_probe (measuring props in the live game) is live-game.
"""
import primitives as P

AXES = {'+x': (1, 0, 0), '-x': (-1, 0, 0), '+y': (0, 1, 0), '-y': (0, -1, 0), '+z': (0, 0, 1), '-z': (0, 0, -1)}
TRIGGER = 'materials/tools/toolstrigger.vmat'


def _brush(cls, shape, group, **keys):
    import mechkit
    return mechkit._brush_loose(cls, shape, group, keys)


def _size_along(shape, d):
    vals = [sum(p[i] * d[i] for i in range(3)) for p in shape[0]]
    return max(vals) - min(vals)


def _angles_of(d):
    """Hammer's move direction as angles (pitch, yaw, roll)"""
    if d[2] > 0.5: return '-90 0 0'
    if d[2] < -0.5: return '90 0 0'
    import math
    return '0 %g 0' % math.degrees(math.atan2(d[1], d[0]))


def door(shape, name, move='+z', distance=None, speed=150, wait=4, locked=False, lip=2, group='physics'):
    d = AXES[move]
    dist = distance if distance is not None else _size_along(shape, d)
    lip_value = _size_along(shape, d) - dist + lip
    keys = dict(targetname=name, movedir=_angles_of(d), speed=speed, wait=wait, lip=lip_value, spawnflags=256 + (2048 if locked else 0))
    return _brush('func_door', shape, group, **keys)


def button(shape, name, targets=(), wait=1, group='physics'):
    e = _brush('func_button', shape, group, targetname=name, wait=wait, spawnflags=1024 + 1)     # use activates; don't move
    for t, inp in targets: P.connect(e, 'OnPressed', t, inp, check_output=False)
    return e


def lift(shape, name, height, speed=120, start_at_bottom=True, group='physics'):
    keys = dict(targetname=name, movedir='-90 0 0', movedistance=height, speed=speed, startposition=0 if start_at_bottom else 1)
    return _brush('func_movelinear', shape, group, **keys)


def rotator(shape, name, speed=60, axis='z', start_on=True, group='physics'):
    flags = {'z': 0, 'x': 4, 'y': 8}[axis] + (1 if start_on else 0)
    return _brush('func_rotating', shape, group, targetname=name, maxspeed=speed, spawnflags=flags, solidbsp=0)


def breakable(shape, name='', health=50, material=0, group='physics'):
    keys = dict(health=health, material=material, propdata=0)
    if name: keys['targetname'] = name
    return _brush('func_breakable', shape, group, **keys)


def physics_prop(model, origin, name='', mass=None, angles=(0, 0, 0), group='physics'):
    keys = {'model': model}
    if name: keys['targetname'] = name
    if mass: keys['massScale'] = mass
    return P.entity('prop_physics_override', origin, angles, group=group, strict=False, **keys)


def zone(shape, kind='hurt', name='', group='physics', damage=20, speed=600, push_dir=(0, 0, 0), destination=None, dest_angles=(0, 0, 0)):
    keys = {'spawnflags': 1}
    if name: keys['targetname'] = name
    if kind == 'hurt': return _brush('trigger_hurt', shape, group, damage=damage, damagetype=0, **keys)
    if kind == 'push': return _brush('trigger_push', shape, group, speed=speed, pushdir='%g %g %g' % tuple(push_dir), **keys)
    if kind == 'teleport':
        if destination is None: raise ValueError('teleport zones need destination=(x, y, z)')
        dest = (name or 'tp') + '_dest'
        P.entity('info_teleport_destination', destination, dest_angles, group=group, strict=False, targetname=dest)
        return _brush('trigger_teleport', shape, group, target=dest, **keys)
    raise ValueError('kind: hurt, push or teleport')


def ladder(bottom, top_z, width=32.0, facing=(1, 0), depth=4.0, group='physics'):
    """CS2 ladders are a toolsinvisibleladder brush (no entity) on the wall; `facing` points from the wall toward the climber"""
    x, y, z = bottom; fx, fy = facing
    if abs(fx) >= abs(fy):
        x0, x1 = sorted((x, x + depth * (1 if fx > 0 else -1))); y0, y1 = y - width / 2, y + width / 2
    else:
        y0, y1 = sorted((y, y + depth * (1 if fy > 0 else -1))); x0, x1 = x - width / 2, x + width / 2
    return P.add(P.box((x0, y0, z), (x1, y1, top_z), 'materials/tools/toolsinvisibleladder.vmat'), group)
