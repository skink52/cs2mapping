"""Move a cs_script source off the `Instance.*` calls Valve's typings mark deprecated, call by call, and keep its import line right.

  python tools/jsapi.py <script.js> [...]            report what would change and what needs a person (writes nothing)
  python tools/jsapi.py --write <script.js> [...]    rewrite the files in place (atomic; the old text is kept as <script>.js.bak_api)
  python tools/jsapi.py --json <script.js> [...]     the same report as JSON

Each rule comes from `create/test/point_script.d.ts` (the declarations) and `docs/reference/cs_script-notes.md` "API moves"; none is a
guess at a similar-looking name. A call is rewritten only when its written form is one the rule covers; anything else is listed as
"manual" with the reason and left exactly as it was.

  same parameters, new home     Instance.Msg -> Console.Log; ServerCommand / ClientCommand / RegisterCheatCommand -> Console.*;
                                FindEntitiesByName / FindEntitiesByClass -> Entities.FindByName / FindByClass; DisconnectOutput ->
                                Entities.DisconnectOutput; IsWarmupPeriod, IsFreezePeriod, IsTeamIntroPeriod, GetRoundsPlayed,
                                GetRoundRemainingTime, SetRoundRemainingTime, AddTeamMoney -> GameRules.*
  first of an array             Instance.FindEntityByName(n) -> Entities.FindByName(n)[0] (and ...ByClass): `undefined` when none, as before.
                                The typings do not say the old call returned the first match in the same order; no map here has
                                two entities under a name it looks up this way and depends on which one it gets.
  config object, renamed        Instance.EntFireAtName({ name, input, ... }) -> Entities.FireInput({ ... }) (same object)
  target moves out              Instance.EntFireAtTarget({ target: e, input, ... }) -> e.FireInput({ input, ... }) when `e` is a plain
                                name or a.b.c chain (it is evaluated once either way)
  positional to config          Instance.ConnectOutput(ent, "OnX", cb) -> Entities.ConnectOutput({ target: ent, output: "OnX", callback: cb })
  manual                        the positional EntFireAtName(name, input, data, delay) / EntFireAtTarget(ent, input, ...) forms (their
                                third argument is a value or an object and cannot be told apart from the text), a config passed as a
                                variable, OnBeforePlayerDamage (-> OnModifyPlayerDamage is a different event), any use that is not
                                a call, and any script that has its own variable called Entities / Console / GameRules.

This is a text change checked by the typings (`create/test/api.py --check`, `create/test/tscheck.sh`) and the stand-in engine. That is
"simulated": it does not show a script works in CS2. Python 3.9+, standard library.
"""
import json, os, re, sys

SAME = {'Msg': ('Console', 'Log'), 'ServerCommand': ('Console', 'ServerCommand'), 'ClientCommand': ('Console', 'ClientCommand'),
        'RegisterCheatCommand': ('Console', 'RegisterCheatCommand'),
        'FindEntitiesByName': ('Entities', 'FindByName'), 'FindEntitiesByClass': ('Entities', 'FindByClass'),
        'DisconnectOutput': ('Entities', 'DisconnectOutput'),
        'IsWarmupPeriod': ('GameRules', 'IsWarmupPeriod'), 'IsFreezePeriod': ('GameRules', 'IsFreezePeriod'),
        'IsTeamIntroPeriod': ('GameRules', 'IsTeamIntroPeriod'), 'GetRoundsPlayed': ('GameRules', 'GetRoundsPlayed'),
        'GetRoundRemainingTime': ('GameRules', 'GetRoundRemainingTime'), 'SetRoundRemainingTime': ('GameRules', 'SetRoundRemainingTime'),
        'AddTeamMoney': ('GameRules', 'AddTeamMoney')}
FIRST = {'FindEntityByName': ('Entities', 'FindByName'), 'FindEntityByClass': ('Entities', 'FindByClass')}
# what to tell a person: old Instance member -> the current spelling (used by create/test/api.py for its hints too)
REPLACEMENT = dict({k: '%s.%s(...) (same parameters)' % v for k, v in SAME.items()},
                   FindEntityByName='Entities.FindByName(name)[0]', FindEntityByClass='Entities.FindByClass(className)[0]',
                   EntFireAtName='Entities.FireInput({ name, input, value?, caller?, activator?, delay? })',
                   EntFireAtTarget='entity.FireInput({ input, value?, caller?, activator?, delay? })',
                   ConnectOutput='Entities.ConnectOutput({ target, output, callback })',
                   OnBeforePlayerDamage='Instance.OnModifyPlayerDamage(cb) (a different event: typed, after hitgroup multipliers, not called for zero damage)',
                   OnBeforeReload='Instance.OnScriptReload({ before, after })', OnReload='Instance.OnScriptReload({ before, after })')
GLOBALS = ('Instance', 'Entities', 'Console', 'GameRules')
IMPORT = re.compile(r'import\s*\{([^}]*)\}\s*from\s*(["\'])cs_script/point_script\2')
_REGEX_AFTER = set('(,=:[!&|?{};+-*%<>~^')
_REGEX_WORDS = {'return', 'typeof', 'case', 'in', 'of', 'delete', 'void', 'throw', 'else', 'do'}


def lex(src):
    """-> bytearray, 1 where the character is code and 0 inside a string, template text, comment or regex literal.
    `${ ... }` inside a template is code. Raises ValueError on text it cannot follow (an unterminated string or template)."""
    n = len(src); mask = bytearray(b'\x01') * n
    i = 0; prev = ''; word = ''; tpl = []                # tpl: brace depth inside each open `${`

    def blank(a, b): mask[a:b] = bytes(b - a)

    def template(i):                                      # i: first character of template text; -> index after it, True if `${` opened
        j = i
        while j < n:
            if src[j] == '\\': j += 2; continue
            if src[j] == '`': blank(i, j + 1); return j + 1, False
            if src[j] == '$' and j + 1 < n and src[j + 1] == '{': blank(i, j + 2); return j + 2, True
            j += 1
        raise ValueError('unterminated template literal')

    while i < n:
        c = src[i]
        if c in '"\'':
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == '\n': raise ValueError('unterminated string at offset %d' % i)
                j += 2 if src[j] == '\\' else 1
            if j >= n: raise ValueError('unterminated string at offset %d' % i)
            blank(i, j + 1); i = j + 1; prev, word = '"', ''
        elif c == '`':
            mask[i] = 0; i, opened = template(i + 1)
            if opened: tpl.append(0)
            prev, word = ('{' if opened else '"'), ''
        elif c == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i); j = n if j < 0 else j; blank(i, j); i = j
        elif c == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i + 2); j = n if j < 0 else j + 2; blank(i, j); i = j
        elif c == '/' and (prev == '' or prev in _REGEX_AFTER or word in _REGEX_WORDS):
            j = i + 1; cls = False
            while j < n and (src[j] != '/' or cls):
                if src[j] == '\n': raise ValueError('unterminated regex at offset %d' % i)
                if src[j] == '\\': j += 2; continue
                if src[j] == '[': cls = True
                elif src[j] == ']': cls = False
                j += 1
            while j + 1 < n and src[j + 1].isalpha(): j += 1
            blank(i, j + 1); i = j + 1; prev, word = '"', ''
        else:
            if c == '{' and tpl: tpl[-1] += 1
            elif c == '}' and tpl:
                if tpl[-1] == 0:
                    tpl.pop(); mask[i] = 0; i, opened = template(i + 1)
                    if opened: tpl.append(0)
                    prev, word = ('{' if opened else '"'), ''
                    continue
                tpl[-1] -= 1
            if c.isalnum() or c in '_$': word = (word + c) if (prev.isalnum() or prev in '_$') and prev != '' else c
            elif not c.isspace(): word = ''
            if not c.isspace(): prev = c
            i += 1
    if tpl: raise ValueError('unterminated ${ in a template literal')
    return mask


def call_args(src, mask, open_i):
    """src[open_i] is the "(" of a call -> (index of its ")", [(start, end) of each top-level argument]) or None when unbalanced."""
    depth = 0; args = []; start = open_i + 1
    for i in range(open_i + 1, len(src)):
        if not mask[i]:
            continue
        c = src[i]
        if c in '([{': depth += 1
        elif c in ')]}':
            if depth == 0:
                if c != ')': return None
                if src[start:i].strip(): args.append((start, i))
                return i, args
            depth -= 1
        elif c == ',' and depth == 0:
            args.append((start, i)); start = i + 1
    return None


def _props(src, mask, a, b):
    """The top-level `key: value` / shorthand entries of the object literal src[a:b] (a at "{", b after "}") -> [(key, text)] or None."""
    depth = 0; out = []; start = a + 1; end = None
    for i in range(a + 1, b):
        if not mask[i]: continue
        c = src[i]
        if c in '([{': depth += 1
        elif c in ')]}':
            if depth == 0: end = i; break
            depth -= 1
        elif c == ',' and depth == 0:
            out.append(src[start:i]); start = i + 1
    if end is None or src[end] != '}' or src[end + 1:b].strip(): return None
    if src[start:end].strip(): out.append(src[start:end])
    props = []
    for p in out:
        t = p.strip()
        m = re.match(r'([A-Za-z_$][\w$]*)\s*:(?!:)', t)
        if m: props.append((m.group(1), t))
        elif re.fullmatch(r'[A-Za-z_$][\w$]*', t): props.append((t, t))
        else: return None                                  # a spread, a computed key, a method: not a form the rules cover
    return props


def migrate(src):
    """-> (new source, done [{'line', 'old', 'new'}], manual [{'line', 'call', 'why'}]). Raises ValueError if the source cannot be lexed."""
    mask = lex(src)
    code = ''.join(ch if mask[i] else ' ' for i, ch in enumerate(src))
    clash = sorted(set(re.findall(r'\b(?:const|let|var|function|class)\s+(Entities|Console|GameRules)\b', code))
                   | set(re.findall(r'[(,]\s*(Entities|Console|GameRules)\s*[,)=]', code)) - set(GLOBALS[:0]))
    imp = IMPORT.search(src)
    imported = set(re.findall(r'[A-Za-z_]\w*', imp.group(1))) if imp else set()
    clash = [c for c in clash if c not in imported]
    edits, done, manual = [], [], []
    line = lambda i: src.count('\n', 0, i) + 1
    names = '|'.join(sorted(set(SAME) | set(FIRST) | {'EntFireAtName', 'EntFireAtTarget', 'ConnectOutput', 'OnBeforePlayerDamage', 'OnBeforeReload', 'OnReload'}, key=len, reverse=True))
    for m in re.finditer(r'\bInstance\s*\.\s*(%s)\b(\s*\()?' % names, code):
        name = m.group(1); call = 'Instance.' + name

        def skip(why): manual.append({'line': line(m.start()), 'call': call, 'why': why})
        if 'Instance' not in imported: continue                              # not the API's Instance
        if clash: skip('the script has its own %s' % ', '.join(clash)); continue
        if not m.group(2): skip('used as a value, not called'); continue
        open_i = m.end() - 1
        span = call_args(src, mask, open_i)
        if span is None: skip('could not find the end of the call'); continue
        close, args = span

        def put(new_head, new_args=None, tail=''):
            old = src[m.start():close + 1]
            new = new_head + '(' + (src[open_i + 1:close] if new_args is None else new_args) + ')' + tail
            edits.append((m.start(), close + 1, new)); done.append({'line': line(m.start()), 'old': ' '.join(old.split())[:160], 'new': ' '.join(new.split())[:160]})
        if name in SAME: put('%s.%s' % SAME[name])
        elif name in FIRST:
            if len(args) != 1: skip('expected one argument'); continue
            put('%s.%s' % FIRST[name], tail='[0]')
        elif name == 'EntFireAtName':
            if len(args) == 1 and src[args[0][0]:args[0][1]].lstrip().startswith('{'): put('Entities.FireInput')
            else: skip('positional form or a config held in a variable: write Entities.FireInput({ name, input, value, delay }) by hand')
        elif name == 'EntFireAtTarget':
            a0 = src[args[0][0]:args[0][1]] if len(args) == 1 else ''
            if not a0.lstrip().startswith('{'): skip('positional form or a config held in a variable: write entity.FireInput({ input, ... }) by hand'); continue
            a = args[0][0] + (len(a0) - len(a0.lstrip())); b = args[0][0] + len(a0.rstrip())
            props = _props(src, mask, a, b)
            tgt = [t for k, t in (props or []) if k == 'target']
            if props is None or len(tgt) != 1: skip('could not read the config object'); continue
            expr = tgt[0].split(':', 1)[1].strip() if ':' in tgt[0] else tgt[0]
            if not re.fullmatch(r'[A-Za-z_$][\w$]*(\s*\.\s*[A-Za-z_$][\w$]*)*', expr): skip('the target is an expression, not a plain name: write entity.FireInput by hand'); continue
            put(expr + '.FireInput', '{ ' + ', '.join(t for k, t in props if k != 'target') + ' }')
        elif name == 'ConnectOutput':
            if len(args) != 3: skip('expected (target, output, callback)'); continue
            t, o, cb = (src[x:y].strip() for x, y in args)
            put('Entities.ConnectOutput', '{ target: %s, output: %s, callback: %s }' % (t, o, cb))
        else:
            skip(REPLACEMENT.get(name, 'no rule'))
    edits_order = list(edits)
    inner = [e for e in edits if not any(o is not e and e[0] <= o[0] and o[1] <= e[1] for o in edits)]    # a call inside another: inner first
    out = src
    for a, b, new in reversed(inner): out = out[:a] + new + out[b:]
    if len(inner) < len(edits):                            # then the calls that held them, on the new text (rewrites add no lines)
        spans = {(a, b) for a, b, _ in inner}
        first = [d for d, e in zip(done, edits_order) if (e[0], e[1]) in spans]
        out, more, manual = migrate(out)
        return out, sorted(first + more, key=lambda d: d['line']), manual
    return (ensure_imports(out) if edits else out), done, manual


def ensure_imports(js):
    """Make the cs_script import line name every API global the code uses (Instance, Entities, Console, GameRules). Names already
    there, and their order, are kept; a script without the import line gets one. Unused names are left alone."""
    try: mask = lex(js)
    except ValueError: mask = None
    code = js if mask is None else ''.join(ch if mask[i] else ' ' for i, ch in enumerate(js))
    used = [g for g in GLOBALS if re.search(r'(?<![\w$.])%s\s*\.' % g, code)]
    m = IMPORT.search(js)
    if not m:
        return ('import { %s } from "cs_script/point_script";\n\n' % ', '.join(used) + js) if used else js
    names = [x.strip() for x in m.group(1).split(',') if x.strip()]
    have = {re.split(r'\s+as\s+', x)[0] for x in names} | {re.split(r'\s+as\s+', x)[-1] for x in names}
    add = [g for g in used if g not in have]
    if not add: return js
    first = [x for x in names if x in GLOBALS]; rest = [x for x in names if x not in GLOBALS]
    return js[:m.start()] + 'import { %s } from %scs_script/point_script%s' % (', '.join(first + add + rest), m.group(2), m.group(2)) + js[m.end():]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Move cs_script sources off deprecated Instance.* calls (reports by default)')
    ap.add_argument('scripts', nargs='+'); ap.add_argument('--write', action='store_true'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    report = []; bad = 0
    for p in a.scripts:
        with open(p, encoding='utf-8', newline='') as f: src = f.read()
        try: new, done, manual = migrate(src)
        except ValueError as ex:
            report.append({'file': p, 'error': str(ex), 'done': [], 'manual': []}); bad += 1; continue
        wrote = False
        if a.write and new != src:
            import safepath
            with open(p + '.bak_api', 'w', encoding='utf-8', newline='') as f: f.write(src)
            safepath.write_atomic(p, new.encode('utf-8')); wrote = True
        report.append({'file': p, 'done': done, 'manual': manual, 'written': wrote})
    if a.json: print(json.dumps(report, indent=1))
    else:
        for r in report:
            if r.get('error'): print('%s: NOT TOUCHED: %s' % (r['file'], r['error'])); continue
            for d in r['done']: print('%s:%d: %s  ->  %s' % (r['file'], d['line'], d['old'], d['new']))
            for d in r['manual']: print('%s:%d: MANUAL %s: %s' % (r['file'], d['line'], d['call'], d['why']))
        print('jsapi: %d file%s, %d call%s %s, %d manual%s' % (len(report), '' if len(report) == 1 else 's', sum(len(r['done']) for r in report),
              '' if sum(len(r['done']) for r in report) == 1 else 's', 'rewritten' if a.write else 'would be rewritten', sum(len(r['manual']) for r in report),
              (', %d could not be read' % bad) if bad else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
