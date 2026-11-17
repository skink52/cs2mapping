"""Round 2 (18 Nov 2026), the user: "some models in the trenches aren't solid". Gives the trench props that had no physics a single
convex hull built from their own LOD0 render mesh (PhysicsHullFile, SingleHull, the same block tools/modelio.py writes), so players
no longer walk through the signs, the gong or the tool rack. Small clutter (casings, helmets, tins, lanterns), wire and the
decorative ladders stay non-solid on purpose (a hull on wire would also stop bullets; a leaning ladder's hull is a ramp out).

usage: python tools/add_hulls.py [--stage out/addon] [--content <content addon>]
  reads each vmdl from the staging folder, else the content addon; writes the staged copy (re-runnable: a vmdl that already has a
  PhysicsShapeList is left alone) and appends the vmdls to out/step16/deploy_files.txt. Level: compiled only after deploy."""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SOLID = ['sign_achtung', 'sign_airfield_de', 'sign_airfield_gb', 'sign_danger', 'sign_dressing_de', 'sign_dressing_gb', 'sign_firetrench_de',
         'sign_firetrench_gb', 'sign_mortars_de', 'sign_mortars_gb', 'sign_piccadilly', 'sign_sap_de', 'sign_sap_gb', 'sign_unter_den_linden',
         'sign_wood_de', 'sign_wood_gb']   # not tl_gong / tl_tools: a single convex hull made them blocks over the bay spawns (gate, 18 Nov)
SURF = {'tl_gong': 'metal'}

BLOCK = '''			{
				_class = "PhysicsShapeList"
				children =
				[
					{
						_class = "PhysicsHullFile"
						name = "%(n)s_hull0"
						parent_bone = ""
						surface_prop = "%(surf)s"
						collision_prop = "default"
						tool_material = ""
						recenter_on_parent_bone = false
						offset_origin = [ 0.0, 0.0, 0.0 ]
						offset_angles = [ 0.0, 0.0, 0.0 ]
						filename = "models/tw/%(n)s/%(n)s_lod0.smd"
						import_scale = 1.0
						faceMergeAngle = 10.0
						maxHullVertices = 0
						import_mode = "SingleHull"
						small_element_threshold = 0.0
						thin_element_threshold = 0.0
						optimization_algorithm = "QEM"
						disable_region_svm = false
						import_filter =
						{
							exclude_by_default = false
							exception_list = [  ]
						}
					},
				]
			},
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default=os.path.join(PROJ, 'out', 'addon'))
    ap.add_argument('--content', default=r'C:\source1\links\content_addons\mg_trenchwarfare')
    a = ap.parse_args()
    done, rels = [], []
    for n in SOLID:
        rel = 'models/tw/%s/%s.vmdl' % (n, n)
        src = os.path.join(a.stage, rel) if os.path.isfile(os.path.join(a.stage, rel)) else os.path.join(a.content, rel)
        if not os.path.isfile(src): print('missing', rel); continue
        t = open(src, encoding='utf-8').read()
        rels.append(rel)
        if 'PhysicsShapeList' in t: continue
        i = t.index('\t\t\t{\n\t\t\t\t_class = "RenderMeshList"')
        t = t[:i] + BLOCK % dict(n=n, surf=SURF.get(n, 'wood')) + t[i:]
        dst = os.path.join(a.stage, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'w', encoding='utf-8', newline='\n').write(t); done.append(n)
    lst = os.path.join(PROJ, 'out', 'step16', 'deploy_files.txt')
    have = open(lst, encoding='utf-8').read() if os.path.isfile(lst) else ''
    add = [r for r in rels if r not in have]
    if add:
        with open(lst, 'a', encoding='utf-8', newline='\n') as f: f.write('# round 2 E: hulls (tools/add_hulls.py); compile these vmdls\n' + '\n'.join(add) + '\n')
    print('add_hulls: %d vmdls given a hull, %d listed for deploy' % (len(done), len(add)))


if __name__ == '__main__':
    main()
