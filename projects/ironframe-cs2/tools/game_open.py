"""game_open.py: is CS2 running in tools mode (Hammer) on this addon right now?

A deploy changes the addon's script and HUD files. A CS2 started with `-tools -addon <addon>` watches those files and reloads them
the moment they change: the script starts again and the round in progress is lost (11 Nov 2026: a deploy landed in the middle of
skink52's game). tools/deploy_dunes.sh asks this first and holds the deploy when the answer is yes.

usage:  python -I tools/game_open.py <addon>      exit 3 = open (one line says so), exit 0 = not open or cannot tell
        IF_DEPLOY_OPEN=1 in the environment: always exit 0 (deploy anyway; the person at the game said so)
"""
import os, subprocess, sys


def main():
    addon = sys.argv[1] if len(sys.argv) > 1 else ''
    if not addon: sys.exit(__doc__)
    if os.environ.get('IF_DEPLOY_OPEN'): return 0
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command',
                              "Get-CimInstance Win32_Process -Filter \"Name='cs2.exe'\" | ForEach-Object { $_.CommandLine }"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        print('game_open: could not list processes (%s): not holding the deploy' % type(e).__name__); return 0
    for line in out.splitlines():
        l = line.lower()
        if '-tools' in l and addon.lower() in l:
            print('HELD: CS2 is open in tools mode on %s. A deploy now would reload the script and end the round being played.' % addon)
            print('      Close the map (or the game) and deploy again, or set IF_DEPLOY_OPEN=1 to deploy anyway.')
            return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
