"""The launch screen: read a map list, find each BSP, check for duplicates and the machine's readiness, then confirm."""
import fnmatch, glob, hashlib, json, os, re, shutil, sys, urllib.parse, urllib.request
from common import CS2, HERE, PORT, REPO, S1, TOOLS, log, read
import ports, profiles

BSP_DIRS = [os.path.join(S1, 'bspsrc-windows', 'mg maps'), os.path.join(S1, 'bspsrc-windows', "bsp's")]

def read_map_list():
    print('Paste or type the maps to port, on one line or several, then press Enter on an empty line.')
    print('Names, paths, folders, wildcards (mg_*) and @file.txt all work.')
    lines = []
    while True:
        try: line = input('maps> ' if not lines else '   > ')
        except EOFError: break
        if not line.strip():
            if lines: break
            continue
        lines.append(line)
    return tokens(lines)

def tokens(lines):
    """Split on commas, semicolons and spaces, but keep quoted paths and real paths with spaces whole."""
    out = []
    for line in lines:
        line = line.strip()
        if os.path.exists(line.strip('"')): out.append(line.strip('"')); continue
        out += [a or b for a, b in re.findall(r'"([^"]+)"|([^\s,;]+)', line)]
    return out

def bsp_index():
    return [p for d in BSP_DIRS for p in glob.glob(os.path.join(d, '**', '*.bsp'), recursive=True)]

def stem(p): return os.path.splitext(os.path.basename(p))[0]

def find(token, index):
    """Every BSP this name could mean, best kind of match first."""
    t = token.lower()
    if t.endswith('.bsp'): t = t[:-4]
    if any(c in t for c in '*?'): return [p for p in index if fnmatch.fnmatch(stem(p).lower(), t)]
    exact = [p for p in index if stem(p).lower() == t]
    if exact: return exact
    clean = [p for p in index if ports.clean_name(stem(p)).lower() == ports.clean_name(t).lower()]
    if clean: return clean
    return [p for p in index if t in stem(p).lower()]

def resolve(names, interactive):
    """names -> BSP paths. Whatever can't be found goes to the dated log and is returned as well."""
    index = bsp_index(); bsps = []; missing = []
    for tok in names:
        if tok.startswith('@'):
            more, miss = resolve(tokens(read(tok[1:]).splitlines()), interactive); bsps += more; missing += miss; continue
        if os.path.isdir(tok): bsps += sorted(glob.glob(os.path.join(tok, '*.bsp'))); continue
        if os.path.isfile(tok): bsps.append(os.path.abspath(tok)); continue
        hits = find(tok, index)
        wild = any(c in tok for c in '*?')
        if not hits:
            missing.append(tok); log('missing', None, 'launch', 'No BSP found for "%s" under %s' % (tok, ' or '.join(BSP_DIRS)))
        elif len(hits) == 1 or wild: bsps += hits
        else: bsps.append(choose(tok, hits, interactive))
    seen = set(); unique = []
    for b in bsps:
        k = os.path.normcase(os.path.abspath(b))
        if k not in seen: seen.add(k); unique.append(b)
    return unique, missing

def choose(tok, hits, interactive):
    hits = sorted(hits, key=os.path.getmtime, reverse=True)
    if interactive:
        print('"%s" could mean:' % tok)
        for i, p in enumerate(hits): print('  %d) %s' % (i + 1, p))
        try:
            a = input('Which one? [1] ').strip()
            if a.isdigit() and 1 <= int(a) <= len(hits): return hits[int(a) - 1]
        except EOFError: pass
    else: log('unknown', None, 'launch', '"%s" matches %d BSPs, using the newest: %s' % (tok, len(hits), hits[0]))
    return hits[0]

def addon_name(bsp, names): return names.get(stem(bsp), ports.clean_name(stem(bsp)))

# ------------------------------------------------------------------ duplicates
def fetch(url, data=None, timeout=15):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')

def search_terms(addon):
    """The map's own name without prefix or version, then its first word (ttt_island17_pezversion also searches island17)."""
    words = [w for w in re.sub(r'^[a-z]{2,4}_', '', addon.lower()).split('_') if w]
    terms = [' '.join(words)]
    if len(words) > 1 and len(words[0]) >= 5: terms.append(words[0])
    return terms

def squash(s): return re.sub(r'[^a-z0-9]', '', s.lower())

def online_ports(addon):
    """CS2 ports of this map on the Steam Workshop and GameBanana. Returns (hits, problem): a failed search is reported, never read as "no port exists"."""
    hits = []; problems = []
    for term in search_terms(addon):
        try:
            html = fetch('https://steamcommunity.com/workshop/browse/?appid=730&section=readytouseitems&browsesort=textsearch&searchtext=' + urllib.parse.quote(term))
            ids = list(dict.fromkeys(re.findall(r'filedetails/\?id=(\d+)', html)))[:20]
            if ids:
                body = {'itemcount': len(ids)}; body.update({'publishedfileids[%d]' % i: x for i, x in enumerate(ids)})
                items = json.loads(fetch('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/', urllib.parse.urlencode(body).encode()))['response']['publishedfiledetails']
                for it in items:
                    # app 730 also holds old CS:GO items, so only CS2-era uploads or ones tagged Cs2 count as ports
                    tags = [t.get('tag', '').lower() for t in it.get('tags', [])]
                    if it.get('result') == 1 and squash(term) in squash(it.get('title', '')) and ('cs2' in tags or it.get('time_created', 0) > 1695772800):
                        hits.append('%s (Steam, %d subscribers): https://steamcommunity.com/sharedfiles/filedetails/?id=%s' % (it['title'], it.get('lifetime_subscriptions', 0), it['publishedfileid']))
        except Exception as e: problems.append('Steam: %s' % e)
        try:
            d = json.loads(fetch('https://gamebanana.com/apiv11/Util/Search/Results?_nPerpage=15&_nPage=1&_sSearchString=' + urllib.parse.quote(term)))
            for r in d.get('_aRecords', []):
                if 'Counter-Strike 2' in str((r.get('_aGame') or {}).get('_sName', '')) and squash(term) in squash(r.get('_sName', '')):
                    hits.append('%s (GameBanana): %s' % (r['_sName'], r.get('_sProfileUrl', '')))
        except Exception as e: problems.append('GameBanana: %s' % e)
    return list(dict.fromkeys(hits)), '; '.join(dict.fromkeys(problems))

# ------------------------------------------------------------------ preflight
def file_hash(p): return hashlib.md5(open(p, 'rb').read()).hexdigest()

def preflight(need_ttt=False):
    """(errors, warnings) about this PC, found now rather than an hour into a run."""
    err = []; warn = []
    for mod in ('numpy', 'scipy', 'PIL'):
        try: __import__(mod)
        except ImportError: err.append('Python library %s is missing: python -m pip install numpy scipy Pillow' % mod)
    must = [(os.path.join(S1, 'bspsrc-windows', 'bin', 'java.exe'), 'BSPSource'), (os.path.join(TOOLS, 'prep.py'), 'cs2port tools'), (os.path.join(TOOLS, 'addon_template', 'content'), 'tools\\addon_template (see autoport/README.md)'),
            (os.path.join(PORT, 'run_import.bat'), 'run_import.bat'), (os.path.join(PORT, 'build_maps.ps1'), 'build_maps.ps1'), (os.path.join(PORT, 'import_map_auto.py'), 'import_map_auto.py (run make_import_map_auto.py)'),
            (os.path.join(CS2, 'csgo', 'gameinfo.txt'), 'extracted CS:GO content'), (os.path.join(CS2, 'game', 'bin', 'win64', 'resourcecompiler.exe'), 'Workshop Tools'),
            (os.path.join(CS2, 'game', 'csgo', 'import_scripts', 'post_import_cleanup.py'), 'import_scripts\\post_import_cleanup.py'), (os.path.join(CS2, 'game', 'csgo', 'pak01_dir.vpk'), "CS2's pak01_dir.vpk"), (os.path.join(S1, 'pak01_dir.vpk'), "CS:GO's pak01_dir.vpk")]
    if need_ttt: must.append((os.path.join(REPO, 'projects', 'cs2mapTTT', 'tools', 'ttt_convert.py'), 'cs2mapTTT in the repo clone'))
    err += ['Missing: %s (%s)' % (what, p) for p, what in must if not os.path.exists(p)]
    if not shutil.which('py'): err.append('The py launcher is not on PATH (run_import.bat uses it)')
    free = shutil.disk_usage(PORT).free / 1e9
    if free < 15: err.append('Only %.0f GB free on the C drive; a map can use over 10 GB' % free)
    if not shutil.which('node'): warn.append('node is not installed, so vmatc.py and the script mock tests won\'t run')
    rt = os.path.join(REPO, 'tools')
    if os.path.isdir(rt):
        stale = [f for f in os.listdir(rt) if os.path.isfile(os.path.join(rt, f)) and (not os.path.exists(os.path.join(TOOLS, f)) or file_hash(os.path.join(rt, f)) != file_hash(os.path.join(TOOLS, f)))]
        if stale: warn.append('cs2port\\tools differs from the repo in: ' + ', '.join(sorted(stale)[:8]))
    ra = os.path.join(REPO, 'autoport')
    if os.path.isdir(ra) and os.path.normcase(ra) != os.path.normcase(HERE):
        stale = [f for f in os.listdir(ra) if f.endswith(('.py', '.bat')) and (not os.path.exists(os.path.join(HERE, f)) or file_hash(os.path.join(ra, f)) != file_hash(os.path.join(HERE, f)))]
        if stale: warn.append('The autoport copy that is running differs from the repo in: ' + ', '.join(sorted(stale)))
    return err, warn

# ------------------------------------------------------------------ the plan
class Plan:
    def __init__(s, bsp, addon):
        s.bsp, s.addon = bsp, addon; s.profile = profiles.detect(addon); s.local = []; s.online = []; s.problem = ''; s.go = True; s.force = False

def build_plan(bsps, names, check_online=True):
    plans = []
    existing = read(os.path.join(PORT, 'existing_ports.txt'))
    for b in bsps:
        p = Plan(b, addon_name(b, names))
        p.local = [l for _, l in ports.check(existing, [stem(b)])[stem(b)][1] if profiles.counts_as_duplicate(p.profile, l)]
        if check_online and p.profile.other_ports_matter:
            print('  checking %s online...' % p.addon, flush=True)
            p.online, p.problem = online_ports(p.addon)
        plans.append(p)
    return plans

def show_plan(plans, missing):
    print()
    print('%-36s %-16s %s' % ('Addon', 'Type', 'Extra steps'))
    for p in plans:
        print('%-36s %-16s %s' % (p.addon, p.profile.label, p.profile.needs or '-'))
        print('   from %s' % p.bsp)
        for l in p.local: print('   ALREADY LISTED: %s' % l)
        for h in p.online: print('   ONLINE PORT: %s' % h)
        if p.problem: print('   online check failed, so duplicates are unknown: %s' % p.problem)
    for t in missing: print('NOT FOUND: %s (noted in the log)' % t)
    print()

def confirm(plans, missing):
    """Interactive launches only. Returns False to cancel. Maps with a known port need a yes each."""
    show_plan(plans, missing)
    for p in plans:
        if p.local or p.online:
            try: p.go = input('%s already has a port. Port it anyway? [y/N] ' % p.addon).strip().lower().startswith('y')
            except EOFError: p.go = False
            p.force = p.go and bool(p.local)
            if not p.go: log('review', p.addon, 'launch', 'Left out: an existing port was found')
    go = [p for p in plans if p.go]
    if not go: print('Nothing to port.'); return False
    try: a = input('Port %d map%s? This runs unattended from here. [Y/n] ' % (len(go), '' if len(go) == 1 else 's')).strip().lower()
    except EOFError: a = 'y'
    return not a.startswith('n')
