#!/usr/bin/env python3
"""Repository checks that need nothing but Python (and Node for the JavaScript syntax check). Used by CI and by hand.

  python ci/check_repo.py [check ...] [--json report.json]

Checks (all of them when none is named):
  python    every tracked .py compiles (syntax only; nothing is imported or run)
  node      every tracked .js / .mjs / .cjs passes `node --check` (skipped, and reported as skipped, when Node is not installed)
  json      every tracked .json parses
  hygiene   no tracked build output (__pycache__, .pyc, node_modules, .part / .tmp files), no file over 20 MB
  private   no user-profile path (C:\\Users\\<name>, /home/<name>, 8.3 short names) in tracked text: the repo rule is "no personal details"
  control   no control characters in tracked text (anything below space except tab, LF, CR; and DEL). They are almost always a
            Windows path whose backslash was eaten: backslash-a became a bell, backslash-b a backspace
  licence   the root and every projects/<name>/ carry both licence files with the standard notice, and no README says the repo's own
            code is MIT (it has been PolyForm Noncommercial 1.0.0 since 30 Oct 2026; "(MIT)" for third-party work is fine)
  docs      the stage C step list and the stage D pass list in docs/porting/pipeline.md and tools/README.md match tools/stage_c.py
            and tools/stage_d.py

The result is one line per problem, a summary line per check, and with --json a machine-readable report:
  {"checks": [{"name", "status": "pass"|"fail"|"skipped", "checked": n, "problems": [...], "note"}], "ok": bool}
Exit code 0 = no check failed (skipped checks do not fail), 1 = at least one failed.
Reads files only. Python 3.9+, stdlib.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 20 * 1024 * 1024
TEXT_EXT = {'.py', '.md', '.txt', '.js', '.mjs', '.cjs', '.json', '.bat', '.ps1', '.sh', '.cfg', '.css', '.xml', '.html', '.yml', '.yaml',
            '.vdf', '.kv3', '.qc', '.lua', '.ts', '.csv', '.ini', '.toml'}


def tracked() -> list[str]:
    out = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], capture_output=True, check=True).stdout
    return [p for p in out.decode('utf-8', 'replace').split('\0') if p]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8', errors='replace')


def check_python(files):
    probs, n = [], 0
    for f in files:
        if not f.endswith('.py'):
            continue
        n += 1
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')          # an old "\s" in a string is a warning, not a syntax error
                compile((ROOT / f).read_bytes(), f, 'exec', dont_inherit=True)
        except SyntaxError as e:
            probs.append('%s:%s: %s' % (f, e.lineno, e.msg))
        except ValueError as e:                          # null bytes
            probs.append('%s: %s' % (f, e))
    return n, probs, 'syntax only, on Python %d.%d' % sys.version_info[:2]


def check_node(files):
    node = shutil.which('node')
    js = [f for f in files if f.endswith(('.js', '.mjs', '.cjs'))]
    if not node:
        return None, [], 'node not found: %d files not checked' % len(js)
    probs = []
    for f in js:
        r = subprocess.run([node, '--check', str(ROOT / f)], capture_output=True, text=True)
        if r.returncode:
            lines = [ln for ln in r.stderr.strip().splitlines() if ln.strip()]
            msg = next((ln for ln in reversed(lines) if 'Error' in ln), lines[-1] if lines else 'failed')
            probs.append('%s: %s' % (f, msg.strip()))
    ver = subprocess.run([node, '--version'], capture_output=True, text=True).stdout.strip()
    return len(js), probs, 'node --check, Node %s' % ver


def check_json(files):
    probs, n = [], 0
    for f in files:
        if not f.endswith('.json'):
            continue
        n += 1
        try:
            json.loads((ROOT / f).read_text(encoding='utf-8-sig'))
        except (ValueError, UnicodeDecodeError) as e:
            if 'tsconfig' in f.rsplit('/', 1)[-1]:       # tsconfig files may hold comments: TypeScript reads them as JSONC
                try:
                    json.loads(re.sub(r'^\s*//.*$', '', read(f), flags=re.M))
                    continue
                except ValueError:
                    pass
            probs.append('%s: %s' % (f, e))
    return n, probs, ''


def check_hygiene(files):
    probs = []
    bad = re.compile(r'(^|/)(__pycache__|node_modules|\.pytest_cache|\.mypy_cache)(/|$)|\.(pyc|pyo|part|tmp)$|(^|/)(Thumbs\.db|\.DS_Store)$')
    for f in files:
        if bad.search(f):
            probs.append('%s: build output or cache, should not be tracked' % f)
            continue
        p = ROOT / f
        if p.is_file() and p.stat().st_size > MAX_BYTES:
            probs.append('%s: %.1f MB (limit %d MB)' % (f, p.stat().st_size / 1e6, MAX_BYTES >> 20))
    return len(files), probs, ''


PRIVATE = re.compile(r'(?i)\b[A-Z]:[\\/]+Users[\\/]+(?!<|%|\$|\{|\.\.\.|x{2,}|you\b|your|name\b|user(name)?\b|me\b|public\b|default\b|skink52\b|runneradmin\b|\*)[A-Za-z0-9._~ -]{2,}'
                     r'|/home/(?!<|\$|\{|user\b|you\b|runner\b|claude\b|\.\.\.)[a-z][a-z0-9._-]+/'
                     r'|\b[A-Z0-9]{6}~[0-9](\.[A-Z0-9]{1,3})?[\\/]AppData')


def check_private(files):
    probs, n = [], 0
    for f in files:
        if Path(f).suffix.lower() not in TEXT_EXT or f == 'ci/check_repo.py':
            continue
        n += 1
        for no, line in enumerate(read(f).splitlines(), 1):
            m = PRIVATE.search(line)
            if m:
                probs.append('%s:%d: user-profile path "%s..."' % (f, no, m.group(0)[:24]))
                break
    return n, probs, ''


CONTROL = re.compile(rb'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def check_control(files):
    probs, n = [], 0
    for f in files:
        if Path(f).suffix.lower() not in TEXT_EXT:
            continue
        n += 1
        data = (ROOT / f).read_bytes()
        m = CONTROL.search(data)
        if m:
            line = data.count(b'\n', 0, m.start()) + 1
            around = CONTROL.sub(b'?', data[max(0, m.start() - 24):m.start() + 12]).decode('utf-8', 'replace').replace('\n', ' ')
            probs.append('%s:%d: control character 0x%02x near "%s"' % (f, line, data[m.start()], around))
    return n, probs, ''


def check_licence(files):
    probs = []
    fs = set(files)
    homes = [''] + sorted({'/'.join(f.split('/')[:2]) + '/' for f in files if f.startswith('projects/') and f.count('/') >= 2})
    for h in homes:
        for name, must in (('LICENSE', ('PolyForm Noncommercial License 1.0.0', 'Required Notice: Copyright (c)')),
                           ('LICENSE-CC-BY-NC-4.0.txt', ('Attribution-NonCommercial 4.0 International',))):
            if h + name not in fs:
                probs.append('%s%s is missing' % (h, name))
                continue
            text = read(h + name)
            for m in must:
                if m not in text:
                    probs.append('%s%s: does not contain "%s"' % (h, name, m))
    own_mit = re.compile(r'(?i)\bMIT\b,? like the rest of the repo|\blicen[cs]ed (under )?(the )?MIT\b|\bMIT licen[cs]ed?\b(?! (stay|or CC))')
    n = 0
    for f in files:
        if not f.lower().endswith('readme.md'):
            continue
        n += 1
        for no, line in enumerate(read(f).splitlines(), 1):
            if own_mit.search(line) and 'before 30 Oct 2026' not in line and 'were MIT' not in line:
                probs.append('%s:%d: says the code is MIT; the repo licence is PolyForm Noncommercial 1.0.0 (see LICENSE)' % (f, no))
    return len(homes) * 2 + n, probs, '%d licence homes, %d READMEs' % (len(homes), n)


def _doc_list(text, start):
    m = re.search(r'`(' + re.escape(start) + r'[^`]*)`', text)
    return [x.strip() for x in m.group(1).replace('\n', ' ').split(',') if x.strip()] if m else None


def check_docs(files):
    probs = []
    c_src = read('tools/stage_c.py')
    m = re.search(r"steps = passes or \[([^\]]+)\]", c_src)
    if not m:
        return 0, ['tools/stage_c.py: could not find the default step list ("steps = passes or [...]")'], ''
    c_steps = re.findall(r"'(\w+)'", m.group(1))
    d_src = read('tools/stage_d.py')
    d_names = re.findall(r"'(\w+)' in passes", d_src)
    for t in re.findall(r"for p in \(([^)]*)\)", d_src):
        d_names += re.findall(r"'(\w+)'", t)
    d_set = set(d_names)
    for doc in ('docs/porting/pipeline.md', 'tools/README.md'):
        text = read(doc)
        got = _doc_list(text, 'merge, io,')
        if got is None:
            probs.append('%s: no stage C step list (a `merge, io, ...` code span)' % doc)
        elif got != c_steps:
            miss = [s for s in c_steps if s not in got]; extra = [s for s in got if s not in c_steps]
            probs.append('%s: stage C step list differs from stage_c.run(): %s' % (
                doc, '; '.join(x for x in ('missing ' + ', '.join(miss) if miss else '', 'not in the code: ' + ', '.join(extra) if extra else '',
                                           'order differs' if not miss and not extra else '') if x)))
        got = _doc_list(text, 'beams, lights,')
        if got is None:
            probs.append('%s: no stage D pass list (a `beams, lights, ...` code span)' % doc)
        else:
            miss = sorted(d_set - set(got)); extra = sorted(set(got) - d_set)
            if miss or extra:
                probs.append('%s: stage D pass list differs from stage_d.py: %s' % (
                    doc, '; '.join(x for x in ('missing ' + ', '.join(miss) if miss else '', 'not in the code: ' + ', '.join(extra) if extra else '') if x)))
    return 4, probs, '%d stage C steps, %d stage D passes' % (len(c_steps), len(d_set))


CHECKS = {'python': check_python, 'node': check_node, 'json': check_json, 'hygiene': check_hygiene, 'private': check_private,
          'control': check_control, 'licence': check_licence, 'docs': check_docs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Repository checks (see the module docstring)')
    ap.add_argument('checks', nargs='*', choices=[*CHECKS, []], help='default: all')
    ap.add_argument('--json', metavar='FILE')
    a = ap.parse_args(argv)
    files = tracked()
    files = [f for f in files if (ROOT / f).exists()]                 # a file deleted but not yet committed
    report = []
    for name in (a.checks or list(CHECKS)):
        n, probs, note = CHECKS[name](files)
        status = 'skipped' if n is None else 'fail' if probs else 'pass'
        for p in probs:
            print('%s: %s' % (name, p))
        print('[%s] %s: %s%s' % (status.upper(), name, '%d checked' % n if n is not None else 'not run', (' (%s)' % note) if note else ''))
        report.append({'name': name, 'status': status, 'checked': n, 'problems': probs, 'note': note})
    ok = not any(r['status'] == 'fail' for r in report)
    if a.json:
        Path(a.json).write_text(json.dumps({'ok': ok, 'checks': report}, indent=1), encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
