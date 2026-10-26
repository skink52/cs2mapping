"""merge_snd.py: puts generated sound events into the addon's soundevents_addon.vsndevts, keeping everything else in it.

usage: merge_snd.py <template.vsndevts> <ours.vsndevts> --tag NAME [-o OUT]
  template  the addon's file (the stock template, or the live addon file that already has an older block of ours)
  ours      the generated events (a complete .vsndevts or bare events); rewritten in place unless -o is given
  --tag     names the block: // ---- NAME sound events (generated) ---- ... // ---- end NAME ----
Re-runnable: an existing NAME block is replaced, nothing outside it is touched. Fails if the template already has
one of our event names outside the block. See sndevents.py for writing the events.

From space-racer-cs2/tools/sounds.py (MIT), made project-neutral (replaces the FreeDM-only merge).
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sndevents


def main(argv=None):
    ap = argparse.ArgumentParser(description='Merge generated sound events into the addon soundevents file.')
    ap.add_argument('template'); ap.add_argument('ours')
    ap.add_argument('--tag', required=True); ap.add_argument('-o', '--out')
    a = ap.parse_args(argv)
    tpl = open(a.template, encoding='utf-8').read() if os.path.exists(a.template) else ''
    ours = open(a.ours, encoding='utf-8').read()
    try:
        text = sndevents.merge(tpl, ours, a.tag)
    except ValueError as e:
        sys.exit('merge_snd: %s' % e)
    out = a.out or a.ours
    open(out, 'w', encoding='utf-8', newline='\n').write(text)
    n = len(sndevents.event_names(sndevents.body_of(text, a.tag)))
    print('merged %d %s events into %s' % (n, a.tag, out))


if __name__ == '__main__':
    main()
