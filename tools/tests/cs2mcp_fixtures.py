"""Shared fixtures for the cs2-map-mcp port tests (test_fgdcheck, test_primitives, test_mapsanity, test_rcompile, test_mcp_server).

A small FGD in CS2's syntax and a generated .vmap (written by create/primitives.py on tools/box_template.vmap, our own template),
so the tests need neither CS2 nor any map content. tools/dmx.py and create/dmx.py share a module name, so maps are written in a
child process with create/ on the path and read back here with tools/.
"""
import json, os, subprocess, sys, tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
REPO = os.path.dirname(TOOLS)
CREATE = os.path.join(REPO, 'create')
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)

FGD_CORE = r'''
// a comment with "quotes" and a URL-like http://x
@mapsize(-16384, 16384)
@BaseClass = Targetname
[
	targetname(target_source) : "Name" : : "The name that other entities refer to this entity by, " +
		"continued over a line."
	input Kill(void) : "Removes this entity from the world."
	input FireUser1(void) : "Causes this entity's OnUser1 output to be fired."
	output OnUser1(void) : "Fired in response to FireUser1 input."
]
@BaseClass = Parentname [ parentname(target_destination) : "Parent" : "" : "" ]
@BaseClass = RenderFields
[
	rendermode(choices) : "Render Mode" : "kRenderNormal" = [ "kRenderNormal" : "Normal" "kRenderTransColor" : "Color" ]
	rendercolor(color255) : "Render Color" : "255 255 255"
	renderamt(integer) : "FX Amount" : 255
	old_key(string) : "Old" : ""
]
@PointClass base(Targetname, Parentname, RenderFields) studio() = prop_dynamic : "A prop that can animate."
[
	model(resource:model) : "World Model" : ""
	solid(intchoices) : "Collisions" : 6 = [ 0 : "Not Solid" 6 : "Use VPhysics" ]
	old_key(remove_key)
	input SetAnimation(string) : "Play an animation."
	output OnAnimationDone(void) : "Fired when an animation finishes."
]
@SolidClass base(Targetname) = trigger_multiple : "Fires its outputs when touched."
[
	spawnflags(flags) = [ 1 : "Clients" : 1  2 : "NPCs" : 0  4 : "Physics" : 0 ]
	wait(float) : "Delay Before Reset" : "1"
	filtername(filterclass) : "Filter Name" : ""
	StartDisabled(boolean) : "Start Disabled" : 0
	input Enable(void) : "Enable."
	input Disable(void) : "Disable."
	output OnTrigger(void) : "Fired when touched."
]
@PointClass base(Targetname) = logic_relay : "Relays a trigger."
[
	input Trigger(void) : "Trigger the relay."
	output OnTrigger(void) : "Fired when triggered."
]
@PointClass base(Targetname) = info_player_terrorist : "T spawn" [ enabled(boolean) : "Enabled" : 1 ]
@PointClass base(Targetname) = info_player_counterterrorist : "CT spawn" [ enabled(boolean) : "Enabled" : 1 ]
@PointClass base(Targetname) = light_environment : "The sun" [ brightness(float) : "Brightness" : "1.0" ]
@PointClass base(Targetname) = env_sky : "Old sky" [ ]
@PointClass base(Targetname) = info_ladder_dismount : "Ladder dismount" [ ]
@PointClass base(Targetname) volume_helper( box_mins, box_maxs ) = env_combined_light_probe_volume : "Probes"
[
	voxel_size(float) : "Voxel size" : "64"
]
'''

FGD_GAME = r'''
@exclude env_sky
@exclude info_ladder_dismount
@PointClass base(Targetname) = env_sky : "CS2 sky" [ skyname(resource:material) : "Sky Material" : "" ]
@OverrideClass = logic_relay [ input CancelPending(void) : "Cancel." ]
@AutoVisGroup = "Triggers" [ "Triggers" [ "trigger_multiple" ] ]
'''


def write(path, text, mode='w'):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f: f.write(text)


def fake_cs2(root):
    """a CS2 install with only the two FGDs (no compiler, no VPKs): CS2_ROOT=<root> makes the tools use it"""
    os.makedirs(os.path.join(root, 'game', 'core'), exist_ok=True)
    os.makedirs(os.path.join(root, 'game', 'csgo'), exist_ok=True)
    write(os.path.join(root, 'game', 'core', 'base.fgd'), FGD_CORE)
    write(os.path.join(root, 'game', 'csgo', 'csgo.fgd'), FGD_GAME)
    addon = os.path.join(root, 'content', 'csgo_addons', 'test_addon')
    os.makedirs(os.path.join(addon, 'maps'), exist_ok=True)
    os.makedirs(os.path.join(addon, 'models', 'test'), exist_ok=True)
    write(os.path.join(addon, 'models', 'test', 'crate.vmdl'), '<!-- test -->')
    return root


def catalog():
    import fgdcat
    return fgdcat.Catalog.from_texts([FGD_CORE, FGD_GAME])


# The test map. Floor box 0..512 x 0..512, top at z 0. Spawns: T at z 8 (fine), T at z 0 (on the floor plane), T at z 8 under a
# 40-unit-high slab (no headroom), CT floating 400 over the void. A relay and trigger with good and bad I/O and keys.
BUILD = r'''
import json, os, sys
sys.path.insert(0, CREATE)
import vmapgen, vmaplib, primitives as P
sys.path.append(TOOLS)
import fgdcat
P.CATALOG = fgdcat.Catalog.from_texts([FGD_CORE, FGD_GAME])
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
P.add(P.box((0, 0, -32), (512, 512, 0), 'materials/dev/reflectivity_50.vmat'), group='t')
P.add(P.box((300, 300, 40), (380, 380, 56)), group='t')
P.add(P.stairs((0, 600, 0), (128, 664, 64), 8), group='t')
P.add(P.revolve([(0, 0), (16, 0), (12, 96), (0, 120)], 12, (700, 0, 0)), group='t')
P.entity('info_player_terrorist', (100, 100, 8), group='t')
P.entity('info_player_terrorist', (200, 100, 0), group='t')
P.entity('info_player_terrorist', (340, 340, 8), group='t')
P.entity('info_player_counterterrorist', (2000, 2000, 400), group='t')
P.entity('light_environment', (0, 0, 256), group='t')
P.entity('env_combined_light_probe_volume', (256, 256, 64), group='t', box_mins='-256 -256 -96', box_maxs='256 256 96')
relay = P.entity('logic_relay', (64, 64, 32), group='t', targetname='relay1')
P.connect(relay, 'OnTrigger', 'door_nowhere', 'Open')             # dangling
P.connect(relay, 'OnTrigger', 'relay1', 'CancelPending')          # OK (OverrideClass input)
trig = P.brush_entity('trigger_multiple', P.box((10, 10, 0), (60, 60, 72), 'materials/tools/toolstrigger.vmat'), group='t',
                      targetname='trig1', filtername='no_such_filter')
P.connect(trig, 'OnTrigger', 'relay1', 'Trigger')                 # OK
P.connect(trig, 'OnTrigger', 'relay1', 'Explode')                 # bad input
P.connect(trig, 'OnTriggered', 'relay1', 'Trigger', check_output=False)   # bad output
P.entity('prop_dynamic', (128, 128, 0), group='t', model='models/test/crate.vmdl')
P.entity('prop_dynamic', (160, 128, 0), group='t', model='models/test/missing.vmdl', strict=False, solid='3', renderamt='abc',
         rendercolor='300 0 0', old_key='x', bogus='1')
P.entity('env_sky', (0, 0, 300), group='t', skyname='materials/test/sky.vmat')
vmaplib.ent('info_ladder_dismount', (0, 0, 0), group='t')
vmaplib.ent('prop_physics_respawnable', (0, 0, 0), group='t')
vmapgen.finish(d, OUT, group='t', first_run_cleanup=True)
'''


def make_map(out, build=None):
    """write the test map (or the map the `build` code makes; it sees CREATE, TOOLS, OUT, FGD_*) to out in a child process"""
    code = 'CREATE=%r\nTOOLS=%r\nOUT=%r\nFGD_CORE=%r\nFGD_GAME=%r\n' % (CREATE, TOOLS, out, FGD_CORE, FGD_GAME) + (build or BUILD)
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=CREATE, timeout=120)
    if r.returncode != 0: raise RuntimeError('map build failed:\n' + r.stdout + r.stderr)
    return out


def temp_root():
    """a fake CS2 root with the test map at content/csgo_addons/test_addon/maps/test_map.vmap; -> (root, vmap path)"""
    root = fake_cs2(tempfile.mkdtemp(prefix='cs2mcp_'))
    vmap = make_map(os.path.join(root, 'content', 'csgo_addons', 'test_addon', 'maps', 'test_map.vmap'))
    return root, vmap
