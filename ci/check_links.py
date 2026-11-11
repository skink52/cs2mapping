#!/usr/bin/env python3
"""Check the relative links in the repo's tracked Markdown files.

  python ci/check_links.py [--anchors] [--baseline FILE] [--json out.json] [path ...]

For every `[text](target)` and `<img src=...>` in a tracked .md file: the target must be a tracked file or folder, with the
same letter case (GitHub and Linux are case-sensitive; Windows is not, so a wrong case only shows up after pushing).
`--anchors` also checks `#heading` fragments against the target file's headings (GitHub's slug rules).
`--baseline FILE` lists known broken links, one `file: link` per line (lines starting with # are comments): they are reported as "known" and do not
fail the run, so CI only fails on new breakage. A baseline line that is no longer broken is reported so it can be removed.
Skipped: http(s)/mailto links, links inside code fences and inline code, and targets outside the repo.

Exit code 0 = no broken links, 1 = broken links (listed), 2 = could not run (not a git checkout).
Python 3.9+, stdlib only. Reads files; changes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path, PurePosixPath

LINK = re.compile(r'(?<!\\)\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')
IMG = re.compile(r'<(?:img|a)\b[^>]*?\b(?:src|href)="([^"]+)"', re.I)
FENCE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE = re.compile(r'`[^`\n]*`')
HEADING = re.compile(r'^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$')


def tracked(root: Path) -> list[str]:
    try:
        out = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print(f'check_links: cannot list tracked files ({e})', file=sys.stderr)
        raise SystemExit(2)
    return [p for p in out.decode('utf-8', 'replace').split('\0') if p]


def slug(heading: str) -> str:
    """GitHub's heading anchor: markup stripped, lower case, punctuation dropped, spaces to hyphens."""
    h = re.sub(r'!?\[((?:[^\]\\]|\\.)*)\]\([^)]*\)', r'\1', heading)   # links / images -> their text
    h = re.sub(r'<[^>]+>', '', h)
    h = h.replace('`', '').replace('*', '')
    h = h.strip().lower()
    h = re.sub(r'[^\w\- ]', '', h, flags=re.UNICODE)
    return h.replace(' ', '-')


def anchors_of(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    fence = False
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if FENCE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        m = HEADING.match(line)
        if m:
            s = slug(m.group(2))
            n = seen.get(s, 0)
            seen[s] = n + 1
            out.add(s if n == 0 else f'{s}-{n}')
        for a in re.findall(r'<a\s+(?:name|id)="([^"]+)"', line):
            out.add(a.lower())
    return out


def links_in(path: Path):
    fence = False
    for no, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        if FENCE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        bare = INLINE_CODE.sub('', line)
        for rx in (LINK, IMG):
            for m in rx.finditer(bare):
                yield no, m.group(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='*', help='limit to these files / folders (repo-relative); default: every tracked .md')
    ap.add_argument('--anchors', action='store_true', help='also check #fragments against the target headings')
    ap.add_argument('--baseline', metavar='FILE', help='known broken links (file: link per line) that do not fail the run')
    ap.add_argument('--json', metavar='FILE', help='write the result as JSON')
    ap.add_argument('--root', default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args(argv)

    root = Path(a.root)
    files = tracked(root)
    fileset = set(files)
    dirset = {str(p) for f in files for p in PurePosixPath(f).parents if str(p) != '.'}
    lower = {}
    for f in list(fileset) + list(dirset):
        lower.setdefault(f.lower(), f)
    want = [p.replace('\\', '/').rstrip('/') for p in a.paths]
    mds = [f for f in files if f.lower().endswith('.md')
           and (not want or any(f == w or f.startswith(w + '/') for w in want))]

    broken = []
    checked = 0
    anchor_cache: dict[str, set[str]] = {}
    for md in mds:
        base = PurePosixPath(md).parent
        for no, raw in links_in(root / md):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*:', raw) or raw.startswith('//'):
                continue                                   # http:, mailto:, steam: ...
            target, _, frag = raw.partition('#')
            target = urllib.parse.unquote(target)
            frag = urllib.parse.unquote(frag)
            if target.startswith('/'):
                rel = target.lstrip('/')
            elif target == '':
                rel = md
            else:
                parts: list[str] = []
                escaped = False
                for part in (base / target).parts:
                    if part == '..':
                        if parts:
                            parts.pop()
                        else:
                            escaped = True
                    elif part != '.':
                        parts.append(part)
                if escaped:
                    continue                               # points outside the repo: not ours to check
                rel = '/'.join(parts)
            rel = rel.rstrip('/')
            checked += 1
            why = None
            if rel == '':
                pass                                       # the repo root
            elif rel in fileset or rel in dirset:
                if a.anchors and frag and rel.lower().endswith('.md') and rel in fileset:
                    if rel not in anchor_cache:
                        anchor_cache[rel] = anchors_of(root / rel)
                    if frag.lower() not in anchor_cache[rel]:
                        why = f'no heading for #{frag}'
            elif rel.lower() in lower:
                why = f'wrong letter case (tracked as {lower[rel.lower()]})'
            elif (root / rel).exists():
                why = 'exists on disk but is not tracked by git (ignored or never added)'
            else:
                why = 'no such file'
            if why:
                broken.append({'file': md, 'line': no, 'link': raw, 'problem': why})

    known_keys = set()
    if a.baseline:
        for ln in Path(a.baseline).read_text(encoding='utf-8').splitlines():
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                known_keys.add(ln)
    known = [b for b in broken if f"{b['file']}: {b['link']}" in known_keys]
    broken = [b for b in broken if f"{b['file']}: {b['link']}" not in known_keys]
    stale = sorted(known_keys - {f"{b['file']}: {b['link']}" for b in known}) if not want else []
    for b in broken:
        print(f"{b['file']}:{b['line']}: {b['link']}  -> {b['problem']}")
    for k in stale:
        print(f'baseline entry no longer broken, remove it: {k}')
    print(f'check_links: {len(mds)} files, {checked} relative links, {len(broken)} broken, {len(known)} known (baseline)')
    if a.json:
        Path(a.json).write_text(json.dumps({'check': 'markdown-links', 'files': len(mds), 'links': checked,
                                            'anchors_checked': bool(a.anchors), 'broken': broken, 'known': known}, indent=1),
                                encoding='utf-8')
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
