"""Deliver the Hellmatch ZE build into the CS2 addon folders (content + game), reusing Hellmatch's compiled files.

  python tools/deploy.py [--dry-run] [--cs2 "<CS2 install>"]

Reads build/copy_plan.json (tools/hm_assets.py plan) and copies, through tools/safepath.py (every overwritten file backed up and
checked first, a manifest for rollback in build/deploy/):
  content\\csgo_addons\\mg_hellescape  <- out/addon (sources; _gen excluded) + the Hellmatch-only sources ZE needs (sprite models,
                                         their materials) from the Hellmatch content addon
  game\\csgo_addons\\mg_hellescape     <- out/game + Hellmatch's compiled files for sources that are byte-identical in ZE, so the
                                         map build compiles only what is new
Refuses to run while cs2.exe is running (never write into an addon a running Hammer/CS2 has open). Hellmatch's addons are read only.
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, '..', '..', 'tools'))
import safepath  # noqa: E402
sys.path.insert(0, HERE)
import names  # noqa: E402

args = sys.argv[1:]
dry = '--dry-run' in args
cs2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
if '--cs2' in args: cs2 = args[args.index('--cs2') + 1]
addon = safepath.addon_name(names.MAP)
content = os.path.join(cs2, 'content', 'csgo_addons', addon)
game = os.path.join(cs2, 'game', 'csgo_addons', addon)

if not dry:
    # refuse while CS2 from THIS install runs (tools mode or a game that may have the addon open); a separate dedicated server
    # install (e.g. C:\cs2server) never has this addon open, so it doesn't block a deploy
    ps = "Get-CimInstance Win32_Process -Filter \"Name='cs2.exe'\" | ForEach-Object { $_.ExecutablePath }"
    try:
        paths = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True).stdout.splitlines()
    except OSError:
        paths = ['(unknown: could not list processes)' + cs2]
    if any(os.path.normcase(cs2) in os.path.normcase(x.strip()) for x in paths if x.strip()):
        sys.exit('cs2.exe from %s is running: close CS2/Hammer before deploying (nothing was copied)' % cs2)

plan_file = json.load(open(os.path.join(ROOT, 'build', 'copy_plan.json')))
hm_c, hm_g = plan_file['hellmatch_content'], plan_file['hellmatch_game']
out_addon, out_game = os.path.join(ROOT, 'out', 'addon'), os.path.join(ROOT, 'out', 'game')

pairs_c, pairs_g = {}, {}
for dp, dns, fns in os.walk(out_addon):
    dns[:] = [d for d in dns if not (dp == out_addon and d == '_gen')]
    for fn in fns:
        rel = os.path.relpath(os.path.join(dp, fn), out_addon)
        pairs_c[os.path.normpath(os.path.join(content, rel))] = os.path.join(dp, fn)
for dp, dns, fns in os.walk(out_game):
    for fn in fns:
        rel = os.path.relpath(os.path.join(dp, fn), out_game)
        pairs_g[os.path.normpath(os.path.join(game, rel))] = os.path.join(dp, fn)
for rel in plan_file['copy_from_hellmatch_content']:
    pairs_c.setdefault(os.path.normpath(os.path.join(content, rel)), os.path.normpath(os.path.join(hm_c, rel)))
for rel in plan_file['copy_from_hellmatch_game']:
    pairs_g.setdefault(os.path.normpath(os.path.join(game, rel)), os.path.normpath(os.path.join(hm_g, rel)))
for e in plan_file['copy_compiled_identical']:
    for rel in e['compiled']:
        pairs_g.setdefault(os.path.normpath(os.path.join(game, rel)), os.path.normpath(os.path.join(hm_g, rel)))

missing = [s for s in list(pairs_c.values()) + list(pairs_g.values()) if not os.path.isfile(s)]
if missing:
    print('%d source files missing, skipped (first: %s)' % (len(missing), missing[0]))
pairs = [(s, d) for d, s in list(pairs_c.items()) + list(pairs_g.items()) if os.path.isfile(s)]
os.makedirs(content, exist_ok=True); os.makedirs(game, exist_ok=True)
plan = safepath.plan_pairs(pairs, [content, game])
# Hellmatch's files are only seed copies: once in the addon (and maybe recompiled there by the map build) they are left alone,
# so a deploy never swaps them back and forces a recompile; ZE's own build output is always updated
hm_roots = tuple(os.path.normcase(os.path.normpath(r)) for r in (hm_c, hm_g))
plan = [p for p in plan if not (p['op'] == 'modify' and os.path.normcase(os.path.normpath(p['src'])).startswith(hm_roots))]
s = safepath.summarise(plan)
print('deploy %s: create %d, modify %d, same %d, %.1f MB to write%s' % (addon, s['create'], s['modify'], s['same'], s['bytes_written'] / 1e6, ' (dry run)' if dry else ''))
bdir = os.path.join(ROOT, 'build', 'deploy')
os.makedirs(bdir, exist_ok=True)
safepath.apply_plan(plan, os.path.join(bdir, 'backup'), os.path.join(bdir, 'manifest.json'), dry_run=dry, label='hellmatch-ze deploy',
                    roots=[content, game])
print('done' if not dry else 'dry run: nothing written')
