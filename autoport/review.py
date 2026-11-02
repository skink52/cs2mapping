"""The feedback line from Claude (or anyone) to the running pipeline: python autoport.py review <command>

  list                          every map's status and how many items hold it back
  show <addon>                  everything known about one map, with the files to look at
  ready <addon> --note "..."    fixed: clear the held items and build it
  accept <addon> --note "..."   already built and fine as it is: clear the items with no rebuild
  redo <addon> <step> --note .. rerun from a step (changes to tools or the map's inputs), then it is checked again
  hold <addon> --note "..."     stop a map from building until someone clears it
  skip <addon> --note "..."     give up on this map
  close <addon> --note "..."    finished and recorded: drop it from the list

These hand the command to the worker, starting one if none is running, so a map marked ready builds without anyone else doing anything.
"""
import argparse, json, os, sys
from common import *

def counts(st):
    n = {}
    for i in open_issues(st, HOLD_KINDS): n[i['kind']] = n.get(i['kind'], 0) + 1
    return ', '.join('%d %s' % (v, k) for k, v in sorted(n.items()))

def cmd_list():
    w = worker_pid()
    print('Worker: %s' % ('running (pid %d)' % w if w else 'not running; a review command starts one'))
    print('%-34s %-10s %-10s %s' % ('Map', 'Status', 'Type', 'Holding it back'))
    for a in all_addons():
        st = load_state(a)
        if st['status'] != 'closed': print('%-34s %-10s %-10s %s' % (a, st['status'], st['profile'], counts(st)))
    pending = [f for f in os.listdir(INBOX) if f.endswith('.json')] if os.path.isdir(INBOX) else []
    if pending: print('%d commands waiting for the worker' % len(pending))
    print('Log: %s\nCleanup list: %s' % (today_log(), CLEANUP))

def cmd_show(addon):
    st = load_state(addon)
    print('%s: %s (%s)' % (addon, st['status'], st['profile']))
    print('BSP: %s' % st.get('bsp', ''))
    if st['failed']: print('FAILED AT %s' % st['failed'])
    print('Steps done: %s' % ', '.join(st['done']))
    print('Seconds: %s' % ', '.join('%s %s' % kv for kv in st['seconds'].items()))
    for kind in ALL_KINDS:
        items = open_issues(st, (kind,))
        if items:
            print('\n%s%s:' % (kind.upper(), ' (holds the build)' if kind in HOLD_KINDS else ''))
            for i in items: print('  [%s] %s' % (i['step'] or '-', i['text']))
    cleared = [i for i in st['issues'] if i['cleared']]
    if cleared:
        print('\nCLEARED:')
        for i in cleared: print('  %s -> %s' % (i['text'][:120], i['cleared']))
    c = os.path.join(CS2, 'content', 'csgo_addons', addon, 'maps')
    print('\nFiles:')
    for p in (os.path.join(c, addon + '.vmap'), os.path.join(c, addon + '_cleanup_log.txt'), os.path.join(c, addon + '_cleanup_report.txt'), os.path.join(c, addon + '_dropped_io.txt'),
              os.path.join(S1, 'maps', addon + '.vmf'), os.path.join(PORT, 'logs', addon + '_build.log'), os.path.join(PORT, 'logs', addon + '_assets.log'), st.get('run_dir', '')):
        if p and os.path.exists(p): print('  ' + p)

def main(argv):
    ap = argparse.ArgumentParser(prog='autoport.py review', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['list', 'show', 'ready', 'accept', 'redo', 'hold', 'skip', 'close'])
    ap.add_argument('addon', nargs='?'); ap.add_argument('step', nargs='?'); ap.add_argument('--note', default='')
    a = ap.parse_args(argv)
    if a.command == 'list': return cmd_list()
    if not a.addon: ap.error('which map?')
    if not os.path.exists(state_path(a.addon)): sys.exit('No map called %s. Try: review list' % a.addon)
    if a.command == 'show': return cmd_show(a.addon)
    if not a.note: ap.error('--note is required, so the log says why')
    if a.command == 'redo' and a.step not in STEPS: ap.error('redo needs a step: ' + ' '.join(STEPS))
    post_command({'cmd': a.command, 'addon': a.addon, 'step': a.step, 'note': a.note})
    log('review', a.addon, a.command, a.note)
    if worker_pid(): print('Sent to the running worker (pid %d).' % worker_pid())
    else:
        start_worker(); print('Started a worker in a new window to carry this out.')
    print('Check progress with: python %s review list' % os.path.join(HERE, 'autoport.py'))
