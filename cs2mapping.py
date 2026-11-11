#!/usr/bin/env python3
"""One front door for the repo's own checks. Thin: it runs existing scripts and reads the environment; it changes nothing.

  python cs2mapping.py doctor [--json]     is this PC set up? Python / Node, packages, every path and where its value came from,
                                           Valve's tools, and whether the PC copy of tools/ and autoport/ matches this clone
  python cs2mapping.py check               what CI runs: ci/check_repo.py, then ci/check_links.py
  python cs2mapping.py test                the unit tests: tools/tests, then autoport/tests
  python cs2mapping.py project-report <project> [--vmap FILE] [--json]
                                           one read-only report on a project or port: where it stands and git (create/context.py),
                                           its scripts against Valve's typings (create/test/api.py), and with --vmap a map's
                                           entities, references and wiring (tools/mapdigest.py), cross-checked: RunScriptInput
                                           names the map sends that no script answers. Static: "simulated", not "works in game".

doctor exit code: 0 = everything required is there, 1 = something required is missing (listed under PROBLEMS).
Optional things that are missing are listed as notes and do not fail it. Paths come from the environment variables in
docs/porting/setup.md ("Paths without editing files"), else the built-in defaults. Python 3.9+, stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
CS2_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'


def _env(name, default):
    v = os.environ.get(name)
    return (v, 'env ' + name) if v else (default, 'default')


def _version(cmd):
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        r = subprocess.run([exe] + cmd[1:], capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else 'present'
    except (OSError, subprocess.TimeoutExpired):
        return None


def _packages(req_file):
    """names listed in a requirements file (comments, -r lines and options skipped)"""
    out = []
    try:
        with open(os.path.join(REPO, 'requirements', req_file), encoding='utf-8') as f:
            for ln in f:
                ln = ln.split('#', 1)[0].strip()
                if ln and not ln.startswith('-'):
                    out.append(ln.split('=')[0].split('<')[0].split('>')[0].strip())
    except OSError:
        pass
    return out


def _same_text(a, b):
    """same bytes, ignoring CRLF / LF (a copy made on Windows may differ only in line endings)"""
    try:
        with open(a, 'rb') as f, open(b, 'rb') as g:
            return f.read().replace(b'\r\n', b'\n') == g.read().replace(b'\r\n', b'\n')
    except OSError:
        return False


def doctor():
    problems, notes = [], []
    rep = {'system': {'os': platform.platform(), 'python': platform.python_version()}, 'programs': {}, 'packages': {}, 'paths': {},
           'valve': {}, 'pc_copy': {}}
    if sys.version_info < (3, 9):
        problems.append('Python %s: the tools are run with 3.13; 3.9 is the least this script supports' % platform.python_version())

    for name, cmd, need in (('node', ['node', '--version'], False), ('tsc', ['tsc', '-v'], False), ('git', ['git', '--version'], False),
                            ('ffmpeg', ['ffmpeg', '-version'], False)):
        v = _version(cmd)
        rep['programs'][name] = v
        if not v:
            notes.append('%s not found (optional: %s)' % (name, {'node': 'script tests, compiled-material reading', 'tsc': 'script type-checks',
                                                                 'git': 'repo checks', 'ffmpeg': 'audio analysis, MP4 previews'}[name]))

    for group, required in (('porting.txt', True), ('porting-optional.txt', False), ('creation.txt', False), ('models.txt', False)):
        for pkg in _packages(group):
            try:
                ver = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                ver = None
            rep['packages'].setdefault(group, {})[pkg] = ver
            if ver is None:
                (problems if required else notes).append('Python package %s is not installed (%s): pip install -r requirements/%s -c requirements/constraints.txt'
                                                         % (pkg, 'required for porting' if required else 'optional', group))

    cs2, cs2_src = _env('CS2_ROOT', CS2_DEFAULT)
    s1, s1_src = _env('CS2MAP_SOURCE1', r'C:\source1')
    port, port_src = _env('CS2PORT', os.path.join(s1, 'cs2port'))
    clone, clone_src = _env('CS2MAPPING', os.path.join(s1, 'cs2mapping'))
    store, store_src = _env('CS2MAP_BACKUPS', os.path.join(port, 'map_backups'))
    for key, path, src, required, what in (
            ('cs2_root', cs2, cs2_src, True, 'the CS2 install'),
            ('source1', s1, s1_src, True, 'the Source 1 workspace (decompiled maps, BSPSource)'),
            ('cs2port', port, port_src, True, 'the pipeline folder (tools, logs, working root)'),
            ('repo_clone', clone, clone_src, False, 'the clone autoport reads TTT files from'),
            ('map_backups', store, store_src, False, 'the map backup store (made on first save)')):
        ok = os.path.isdir(path)
        rep['paths'][key] = {'path': path, 'from': src, 'exists': ok}
        if not ok:
            (problems if required else notes).append('%s: %s does not exist (%s; set %s to change it)'
                                                     % (what, path, src, {'cs2_root': 'CS2_ROOT', 'source1': 'CS2MAP_SOURCE1', 'cs2port': 'CS2PORT',
                                                                          'repo_clone': 'CS2MAPPING', 'map_backups': 'CS2MAP_BACKUPS'}[key]))

    for key, rel, required, what in (
            ('resourcecompiler', r'game\bin\win64\resourcecompiler.exe', True, 'Workshop Tools (the compiler)'),
            ('import_scripts', r'game\csgo\import_scripts\import_map_community.py', True, "Valve's map importer"),
            ('csgo_content', r'csgo\gameinfo.txt', True, 'extracted CS:GO content in <CS2>\\csgo'),
            ('cs2_vpk', r'game\csgo\pak01_dir.vpk', True, "CS2's pak01_dir.vpk"),
            ('content_addons', r'content\csgo_addons', True, 'the addon source folder'),
            ('vpk_signatures', r'game\bin\win64\vpk.signatures', False, None)):
        p = os.path.join(cs2, rel)
        ok = os.path.exists(p)
        rep['valve'][key] = ok
        if key == 'vpk_signatures':
            if ok:
                notes.append('vpk.signatures is present: the importer fails while it exists (run_import.bat renames it each run)')
        elif not ok and os.path.isdir(cs2):
            (problems if required else notes).append('%s not found: %s' % (what, p))
    for key, p, what in (('bspsource', os.path.join(s1, 'bspsrc-windows', 'bin', 'java.exe'), 'BSPSource (its Windows image)'),
                         ('addon_template', os.path.join(port, 'tools', 'addon_template', 'content'), 'tools\\addon_template (copied from the CS2 install)'),
                         ('csgo_vpk', os.path.join(s1, 'pak01_dir.vpk'), "CS:GO's pak01_dir.vpk")):
        ok = os.path.exists(p)
        rep['valve'][key] = ok
        if not ok and os.path.isdir(port):
            problems.append('%s not found: %s' % (what, p))

    # the PC copy is what runs: compare it with this clone
    differ, missing, n = [], [], 0
    for area in ('tools', 'autoport'):
        src = os.path.join(REPO, area); dst = os.path.join(port, area)
        if not os.path.isdir(dst) or os.path.normcase(os.path.abspath(dst)) == os.path.normcase(src):
            continue
        for fn in sorted(os.listdir(src)):
            a = os.path.join(src, fn)
            if not os.path.isfile(a) or not fn.endswith(('.py', '.bat', '.md', '.vmap', '.vpost')):
                continue
            n += 1
            b = os.path.join(dst, fn)
            if not os.path.exists(b):
                missing.append(area + '/' + fn)
            elif not _same_text(a, b):
                differ.append(area + '/' + fn)
    rep['pc_copy'] = {'compared': n, 'differ': differ, 'missing': missing}
    if differ or missing:
        notes.append('the PC copy under %s is not this clone: %d differ, %d missing (%s%s). Copy them across (docs/porting/setup.md)'
                     % (port, len(differ), len(missing), ', '.join((differ + missing)[:6]), ', ...' if len(differ + missing) > 6 else ''))

    rep['problems'] = problems; rep['notes'] = notes; rep['ok'] = not problems
    return rep


def show(rep):
    print('cs2mapping doctor  (%s, Python %s)' % (rep['system']['os'], rep['system']['python']))
    print('\nPrograms');  [print('  %-8s %s' % (k, v or 'not found')) for k, v in rep['programs'].items()]
    print('\nPython packages')
    for group, pk in rep['packages'].items():
        print('  %-22s %s' % (group, ', '.join('%s %s' % (k, v or 'MISSING') for k, v in pk.items())))
    print('\nPaths')
    for k, v in rep['paths'].items():
        print('  %-12s %s  [%s]%s' % (k, v['path'], v['from'], '' if v['exists'] else '  MISSING'))
    print('\nValve tools and content');  print('  ' + ', '.join('%s %s' % (k, 'yes' if v else 'no') for k, v in rep['valve'].items()))
    c = rep['pc_copy']
    print('\nPC copy of tools/ and autoport/: %d files compared, %d differ, %d missing' % (c['compared'], len(c['differ']), len(c['missing'])))
    if rep['notes']:
        print('\nNotes');  [print('  - ' + n) for n in rep['notes']]
    print('\nPROBLEMS' if rep['problems'] else '\nOK: everything required for porting is in place.')
    for p in rep['problems']:
        print('  - ' + p)


def run(cmds):
    for c in cmds:
        print('> ' + ' '.join(c[1:]), flush=True)
        r = subprocess.run(c, cwd=REPO)
        if r.returncode:
            return r.returncode
    return 0


def project_report(project, vmap=None):
    """One report on a project or port from the three read-only helpers, each still usable alone:
    create/context.py (where it stands), create/test/api.py (its scripts against the typings), tools/mapdigest.py (a map's entities
    and wiring, when --vmap names one). Nothing is written and nothing here runs CS2: the report's level is "simulated" at best."""
    for d in ('create', os.path.join('create', 'test'), 'tools'):
        p = os.path.join(REPO, d)
        if p not in sys.path: sys.path.insert(0, p)
    import context, api
    root = context.find_project(project)
    snap = context.snapshot(root)
    rep = {'project': snap['project'], 'path': snap['path'], 'level': 'simulated', 'manual_check_required': True,
           'status_file': snap['status_file'], 'where': [{'title': w['title'], 'line': w['line']} for w in snap['where']],
           'git': snap['git'], 'tests': snap['tests']['commands'], 'overrides': snap['overrides'], 'warnings': []}
    decls = api.parse(os.path.join(REPO, 'create', 'test', 'point_script.d.ts')); allow = api.load_allow(api.ALLOW)
    scripts = []; answered = set()
    for s in snap['scripts']:
        f = os.path.join(root, s['file'])
        try: unknown, dep = api.check(decls, f)
        except OSError: continue
        kept = [t for _, t in dep if api.allowed(allow, f, t.split(' is deprecated')[0])]
        scripts.append({'file': s['file'], 'bytes': s['bytes'], 'invalid': [t for _, t in unknown],
                        'deprecated': [t for _, t in dep if t not in kept], 'allowed_deprecated': len(kept)})
    answered = set(snap['script_facts'].get('inputs', [])); prefixes = set()
    for s in snap['scripts']:                              # names built at run time: OnScriptInput("Cmd_" + i, ...) answers every Cmd_*
        try:
            with open(os.path.join(root, s['file']), encoding='utf-8', errors='replace') as fh: src = fh.read()
        except OSError: continue
        prefixes |= set(re.findall(r'OnScriptInput\(\s*["\']([^"\']+)["\']\s*\+', src)) | set(re.findall(r'OnScriptInput\(\s*`([^`$]+)\$\{', src))
    rep['scripts'] = scripts
    rep['api'] = {'invalid': sum(len(s['invalid']) for s in scripts), 'deprecated': sum(len(s['deprecated']) for s in scripts),
                  'allowed_deprecated': sum(s['allowed_deprecated'] for s in scripts)}
    if rep['api']['invalid']: rep['warnings'].append('%d script call(s) the typings do not declare' % rep['api']['invalid'])
    if rep['api']['deprecated']: rep['warnings'].append('%d deprecated script call(s) with no allowlist reason' % rep['api']['deprecated'])
    if snap['git']['uncommitted']: rep['warnings'].append('%d uncommitted file(s) in the folder: someone may be working here' % len(snap['git']['uncommitted']))
    if vmap:
        import mapdigest
        d = mapdigest.digest(vmap, limit=0)
        sm = d['summary']
        rep['map'] = {'file': d['map'], 'bytes': d['bytes'], 'entities': sm['entities_in_map'], 'classes': len(sm['by_class']),
                      'top_classes': dict(list(sm['by_class'].items())[:12]), 'meshes': sm['meshes'], 'bounds': sm.get('bounds'),
                      'dangling_targets': sm['dangling_targets'], 'duplicate_names': len(sm.get('duplicate_names') or {}),
                      'references': sm.get('reference_counts', {}), 'scripts': sm.get('references', {}).get('scripts', {}),
                      'script_inputs': sm['script_inputs']}
        missing = sorted(n for n in set(sm['script_inputs']) - answered if not any(n.startswith(p) for p in prefixes)) if scripts else []
        if missing: rep['map']['inputs_no_script_answers'] = missing; rep['warnings'].append('the map sends %d RunScriptInput name(s) no script here answers (literal OnScriptInput names only; names built at run time are not seen)' % len(missing))
        if sm['dangling_targets']: rep['warnings'].append('%d output target(s) no entity in the file is named (may be named at run time)' % len(sm['dangling_targets']))
    return rep


def show_report(r):
    print('%s  (%s)   level: %s, never "works in game"' % (r['project'], r['path'], r['level']))
    for w in r['where']: print('  where it stands: %s  [%s line %d]' % (w['title'], r['status_file'], w['line']))
    print('  git: %s, %d uncommitted, last: %s' % (r['git']['branch'], len(r['git']['uncommitted']), (r['git']['recent'] or ['none'])[0]))
    print('  scripts: %d   api: %d invalid, %d deprecated, %d deprecated kept by the allowlist' % (len(r['scripts']), r['api']['invalid'], r['api']['deprecated'], r['api']['allowed_deprecated']))
    for s in r['scripts']:
        for t in s['invalid'] + s['deprecated']: print('    %s: %s' % (s['file'], t[:150]))
    if 'map' in r:
        m = r['map']
        print('  map %s: %d entities in %d classes, %d meshes, %d dangling targets, %d duplicate names; references %s' % (
            m['file'], m['entities'], m['classes'], m['meshes'], len(m['dangling_targets']), m['duplicate_names'], m['references'] or 'none'))
        if m.get('inputs_no_script_answers'): print('    RunScriptInput names no script answers: ' + ', '.join(m['inputs_no_script_answers'][:20]))
    for c in r['tests'][:6]: print('  test: ' + c)
    for w in r['warnings']: print('  WARNING: ' + w)
    if not r['warnings']: print('  no warnings from the static checks')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='cs2mapping', description='doctor, check, test, project-report (see the module docstring)')
    ap.add_argument('cmd', choices=['doctor', 'check', 'test', 'project-report'])
    ap.add_argument('project', nargs='?', help='project-report: a folder under projects/ or ports/ (name or path)')
    ap.add_argument('--vmap', help='project-report: a .vmap to digest as well (read only)')
    ap.add_argument('--json', action='store_true', help='doctor, project-report: print the report as JSON')
    a = ap.parse_args(argv)
    py = sys.executable
    if a.cmd == 'project-report':
        if not a.project: ap.error('project-report needs a project (python create/context.py --list)')
        rep = project_report(a.project, a.vmap)
        print(json.dumps(rep, indent=1)) if a.json else show_report(rep)
        return 0
    if a.cmd == 'doctor':
        rep = doctor()
        print(json.dumps(rep, indent=1)) if a.json else show(rep)
        return 0 if rep['ok'] else 1
    if a.cmd == 'check':
        return run([[py, 'ci/check_repo.py'], [py, 'ci/check_links.py', '--anchors', '--baseline', 'ci/known_broken_links.txt']])
    return run([[py, '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py'],
                [py, '-m', 'unittest', 'discover', '-s', 'autoport/tests', '-p', 'test_*.py']])


if __name__ == '__main__':
    sys.exit(main())
