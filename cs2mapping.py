#!/usr/bin/env python3
"""One front door for the repo's own checks. Thin: it runs existing scripts and reads the environment; it changes nothing.

  python cs2mapping.py doctor [--json]     is this PC set up? Python / Node, packages, every path and where its value came from,
                                           Valve's tools, and whether the PC copy of tools/ and autoport/ matches this clone
  python cs2mapping.py check               what CI runs: ci/check_repo.py, then ci/check_links.py
  python cs2mapping.py test                the unit tests: tools/tests, then autoport/tests

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


def main(argv=None):
    ap = argparse.ArgumentParser(prog='cs2mapping', description='doctor, check, test (see the module docstring)')
    ap.add_argument('cmd', choices=['doctor', 'check', 'test'])
    ap.add_argument('--json', action='store_true', help='doctor: print the report as JSON')
    a = ap.parse_args(argv)
    py = sys.executable
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
