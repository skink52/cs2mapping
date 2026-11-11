"""Fixes the CS2 model compiler insists on, for the .vmdl files cs_mdl_import writes from CS:GO models.

  python vmdlfix.py <addon content folder or .vmdl> [...] [--no-backup]

A changed file is first copied to <file>.bak_<stamp> beside it (checked), then replaced through a temp file; --no-backup skips the copy.

- Bodygroup choices with no name: cs_mdl_import leaves them empty, and resourcecompiler then refuses the whole model ("Invalid empty body group
  choice name in bodygroup 'X'. Non-empty choice names are required."), so every prop using it is missing in game (ttt_island17: the 23
  woodwall030b_window01a_bars window bars and door01_left). Each gets "choice<N>", N being its index; maps switch bodygroups by index, so nothing
  that used them changes.
Prints one line per changed file. Re-runnable.
"""
import os, re, sys

def name_choices(text):
    lines = text.split('\n'); out = []; changed = 0; n = 0
    for i, line in enumerate(lines):
        out.append(line)
        if re.search(r'_class = "BodyGroup"\s*$', line): n = 0
        m = re.match(r'(\s*)_class = "BodyGroupChoice"\s*$', line)
        if not m: continue
        ind = m.group(1); has_name = False
        for nxt in lines[i + 1:]:
            if not nxt.startswith(ind) or nxt.strip().startswith('}') and len(nxt) - len(nxt.lstrip()) < len(ind): break
            if len(nxt) - len(nxt.lstrip()) == len(ind) and nxt.strip().startswith('name ='):
                has_name = not re.search(r'name = ""', nxt); break
        if not has_name:
            if i + 1 < len(lines) and re.match(re.escape(ind) + r'name = ""', lines[i + 1]): lines[i + 1] = ind + 'name = "choice%d"' % n
            else: out.append(ind + 'name = "choice%d"' % n)
            changed += 1
        n += 1
    return '\n'.join(out), changed

def files(args):
    for a in args:
        if os.path.isdir(a):
            for dp, _, fs in os.walk(a):
                for f in fs:
                    if f.lower().endswith('.vmdl'): yield os.path.join(dp, f)
        else: yield a

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    import safepath
    nobak = '--no-backup' in sys.argv; args = [a for a in sys.argv[1:] if a != '--no-backup']
    total = 0
    for p in files(args):
        text = open(p, encoding='utf-8', errors='surrogateescape').read()
        new, n = name_choices(text)
        if n:
            r = safepath.write_atomic(p, new.encode('utf-8', errors='surrogateescape'), backup=None if nobak else 'sibling'); total += n
            if r['backup']: print('  backup: ' + r['backup'])
            print('%s: named %d bodygroup choices' % (p, n))
    print('vmdlfix: %d bodygroup choices named' % total)
