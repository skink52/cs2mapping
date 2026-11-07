"""Bulk export of League of Legends champions (base skin, T-pose) as GLB from modelviewer.lol, through the site's own Export
button (no private API), one at a time with a pause between champions.

    python lol_export.py <out dir> [--only ahri,briar] [--all] [--delay 6] [--headed] [--limit N]

For each champion on /champions: open its base skin (/model-viewer?id=<key>000), choose the T-Pose animation, Export .glb with
"Minimal Size" (current animation only), save as <out>/<champion>.glb. Champions already in <out> are skipped, so a stopped run
picks up where it left off. Non-humanoid champions (no CS2 player skeleton fit: dragons, blobs, quadrupeds) are skipped unless
--all. Writes <out>/export_log.json (champion -> ok / reason). Uses the installed Microsoft Edge through Playwright
(pip install playwright; no browser download). Ad requests are blocked (an automated visit is not a real ad view).
The models are Riot Games' property (the site's terms): private testing only, not for redistribution.
"""
import json, os, re, sys, time

SITE = 'https://modelviewer.lol'
NOT_HUMANOID = {'anivia', 'aurelionsol', 'chogath', 'kogmaw', 'rammus', 'skarner', 'velkoz', 'malphite', 'maokai', 'ornn', 'reksai',
                'zac', 'kindred', 'nunuwillump', 'nunu', 'corki', 'kled', 'yuumi', 'tahmkench', 'smolder', 'bard', 'galio'}
AD_HOSTS = re.compile(r'googlesyndication|doubleclick|adservice|googletagservices|google-analytics|googletagmanager|amazon-adsystem|'
                      r'adnxs|pubmatic|rubiconproject|criteo|taboola|outbrain|fundingchoices|ezoic|nitropay|venatus|playwire')


def key(name): return re.sub(r'[^a-z0-9]', '', name.lower())


def main():
    from playwright.sync_api import sync_playwright
    a = sys.argv[1:]
    out = a[0]; os.makedirs(out, exist_ok=True)
    only = set(key(x) for x in a[a.index('--only') + 1].split(',')) if '--only' in a else None
    delay = float(a[a.index('--delay') + 1]) if '--delay' in a else 6.0
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else 0
    logp = os.path.join(out, 'export_log.json')
    log = json.load(open(logp, encoding='utf-8')) if os.path.exists(logp) else {}
    with sync_playwright() as p:
        br = p.chromium.launch(channel='msedge', headless='--headed' not in a)
        ctx = br.new_context(accept_downloads=True, viewport={'width': 1400, 'height': 900})
        ctx.route('**/*', lambda r: r.abort() if AD_HOSTS.search(r.request.url) else r.continue_())
        pg = ctx.new_page()
        pg.goto(SITE + '/champions', wait_until='networkidle')
        champs = []
        for el in pg.locator('a[href^="/champions/"]').all():
            href, name = el.get_attribute('href'), el.inner_text().strip()
            if name and href.count('/') == 2 and (href, name) not in champs: champs.append((href, name))
        print('%d champions listed' % len(champs), flush=True)
        done = 0
        for href, name in champs:
            k = key(name)
            if only and k not in only: continue
            if not only and '--all' not in a and k in NOT_HUMANOID: log.setdefault(k, 'skipped: not humanoid'); continue
            dst = os.path.join(out, k + '.glb')
            if os.path.exists(dst): continue
            if limit and done >= limit: break
            t0 = time.time(); step = 'open'
            try:
                pg.goto(SITE + href, wait_until='networkidle')
                link = pg.locator('a[href*="model-viewer?id="]').first.get_attribute('href')
                base = re.sub(r'id=(\d+)', lambda m: 'id=%d' % (int(m.group(1)) // 1000 * 1000), link)
                pg.goto(SITE + base, wait_until='networkidle')
                combo = pg.locator('button[role=combobox]').first
                combo.wait_for(timeout=60000)
                pg.wait_for_timeout(1500)
                step = 'animation picker'; combo.click()
                pg.keyboard.type('t-pose', delay=40)
                opt = pg.get_by_role('option', name=re.compile(r't-?pose', re.I)).first
                step = 'T-Pose option'; opt.wait_for(timeout=10000); opt.click()
                pg.wait_for_timeout(1500)
                if not re.search(r't-?pose', combo.inner_text(), re.I): raise RuntimeError('T-Pose not selected (shows %r)' % combo.inner_text())
                step = 'Export .glb'; btn = pg.get_by_role('button', name='Export .glb')
                if not btn.is_visible(): pg.get_by_text('Export', exact=True).first.click(); pg.wait_for_timeout(500)
                btn.click()
                dlg = pg.locator('[role=alertdialog], [role=dialog]').last
                step = 'Minimal Size'; dlg.get_by_text('Minimal Size').click()
                step = 'Export (dialog)'
                with pg.expect_download(timeout=300000) as dl:
                    dlg.get_by_role('button', name='Export', exact=True).click()
                dl.value.save_as(dst)
                log[k] = 'ok %.1f MB (%s)' % (os.path.getsize(dst) / 1e6, base)
                done += 1
                print('[%d] %s: %s (%.0f s)' % (done, name, log[k], time.time() - t0), flush=True)
            except Exception as e:
                log[k] = 'failed at %s: %s' % (step, str(e).splitlines()[0][:200])
                try: pg.screenshot(path=os.path.join(out, 'failed_%s.png' % k))
                except Exception: pass
                print('    %s: %s' % (name, log[k]), flush=True)
                pg.keyboard.press('Escape')
            json.dump(log, open(logp, 'w', encoding='utf-8'), indent=1)
            time.sleep(delay)
        br.close()
    json.dump(log, open(logp, 'w', encoding='utf-8'), indent=1)
    print('done: %d exported, %d in %s' % (done, len([f for f in os.listdir(out) if f.endswith('.glb')]), out))


if __name__ == '__main__':
    main()
